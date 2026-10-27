"""Step 3b, part 3: video scores per episode and camera, decoded inside the container.

Two commands:

score (inside the container only: it decodes untrusted video). Reads every dataset under
/data/video (read-only) plus ours under /data/ours (read-only), and for each episode and
camera computes sharpness, brightness, frozen frames, and ResNet-18 embeddings of the first
and middle frames. Writes /data/out/video_scores.parquet and /data/out/versions.json.

summarize (on the Mac, no decoding). Reads those two files and writes the committed
results: per-dataset scores, our episodes, similarity to our scene, near-duplicate scenes.

Run (does not touch the arm): see the Dockerfile for the container command, then
    uv run python projects/03-ray-curation/src/score_video.py summarize
"""

import argparse
import json
import os
import time
from pathlib import Path

os.environ["RAY_USAGE_STATS_ENABLED"] = "0"
os.environ["RAY_ENABLE_UV_RUN_RUNTIME_ENV"] = "0"

CONFIG = Path("projects/03-ray-curation/configs/scoring_stage2.yaml")
RESULTS = Path("projects/03-ray-curation/results")
OURS_ID = "causalerror/so101-toy-to-bowl"


# ---------------------------------------------------------------- score (container)

def list_episodes(root: Path, repo_id: str) -> list[dict]:
    """One item per (episode, camera): the video file and the episode's time span in it."""
    import pandas as pd

    info = json.loads((root / "meta/info.json").read_text())
    fps = info["fps"]
    cams = [k for k, v in info["features"].items() if k.startswith("observation.images.") and v.get("dtype") == "video"]
    items = []
    if str(info.get("codebase_version", "")).startswith("v3"):
        eps = pd.concat([pd.read_parquet(p) for p in sorted(root.glob("meta/episodes/*/*.parquet"))])
        for _, e in eps.iterrows():
            for k in cams:
                path = info["video_path"].format(video_key=k, chunk_index=int(e[f"videos/{k}/chunk_index"]),
                                                 file_index=int(e[f"videos/{k}/file_index"]))
                items.append({"repo_id": repo_id, "episode_index": int(e["episode_index"]), "camera": k.removeprefix("observation.images."),
                              "path": str(root / path), "start": float(e[f"videos/{k}/from_timestamp"]),
                              "end": float(e[f"videos/{k}/to_timestamp"]), "fps": fps})
    else:  # v2.1: one file per episode and camera, starting at 0
        lines = (root / "meta/episodes.jsonl").read_text().splitlines()
        for e in (json.loads(x) for x in lines if x.strip()):
            idx = int(e["episode_index"])
            for k in cams:
                path = info["video_path"].format(video_key=k, episode_chunk=idx // info["chunks_size"], episode_index=idx)
                items.append({"repo_id": repo_id, "episode_index": idx, "camera": k.removeprefix("observation.images."),
                              "path": str(root / path), "start": 0.0, "end": e["length"] / fps, "fps": fps})
    return items


class Scorer:
    """Ray Data callable class: the model is loaded once per worker, not once per episode."""

    def __init__(self, weights: str, cfg: dict):
        import torch
        import torchvision

        torch.set_num_threads(1)
        self.torch, self.cfg = torch, cfg
        model = torchvision.models.resnet18()
        model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
        model.fc = torch.nn.Identity()
        self.model = model.eval()
        self.lap = torch.tensor([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]]).view(1, 1, 3, 3)
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)

    def __call__(self, item: dict) -> dict:
        out = {k: item[k] for k in ("repo_id", "episode_index", "camera")}
        try:
            out.update(self.score(item))
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {str(e).splitlines()[0][:160] if str(e) else ''}"
        return out

    def score(self, item: dict) -> dict:
        import torch.nn.functional as F
        from torchcodec.decoders import VideoDecoder

        torch, c = self.torch, self.cfg
        dec = VideoDecoder(item["path"], seek_mode="approximate")
        start, end, step = item["start"], item["end"], 1.0 / item["fps"]
        last = max(start, end - 2 * step)
        n = c["spread_frames"]
        spread = [start + (last - start) * i / (n - 1) for i in range(n)]
        mid = start + (last - start) / 2
        consecutive = [min(mid + i * step, last) for i in range(c["consecutive_frames"])]
        frames = dec.get_frames_played_at(seconds=spread + consecutive).data.float()  # (N, 3, H, W), 0-255
        gray = (0.299 * frames[:, 0] + 0.587 * frames[:, 1] + 0.114 * frames[:, 2]).unsqueeze(1)

        sp = gray[:n]
        sharp = F.conv2d(sp, self.lap).flatten(1).var(dim=1)
        diffs = (gray[n + 1:] - gray[n:-1]).abs().flatten(1).mean(dim=1)
        with torch.no_grad():
            x = frames[[0, n // 2]] / 255.0
            h, w = x.shape[-2:]
            scale = c["embed_size"] / min(h, w)
            x = F.interpolate(x, size=(round(h * scale), round(w * scale)), mode="bilinear", antialias=True)
            top, left = (x.shape[-2] - c["embed_size"]) // 2, (x.shape[-1] - c["embed_size"]) // 2
            x = x[..., top:top + c["embed_size"], left:left + c["embed_size"]]
            emb = self.model((x - self.mean) / self.std)
        return {
            "height": int(frames.shape[-2]), "width": int(frames.shape[-1]),
            "sharpness": float(sharp.median()), "brightness": float(sp.mean()),
            "motion_diff": float(diffs.mean()), "frozen_fraction": float((diffs < c["frozen_diff"]).float().mean()),
            "emb_first": emb[0].tolist(), "emb_mid": emb[1].tolist(),
        }


def cmd_score(args, cfg) -> None:
    import platform
    import subprocess

    import pandas as pd
    import ray

    video, ours, out = Path("/data/video"), Path("/data/ours"), Path("/data/out")
    roots = [(json.loads((d / "manifest.json").read_text())["repo_id"], d)
             for d in sorted(video.iterdir()) if (d / "manifest.json").exists()]
    roots = [(OURS_ID, ours)] + ([] if args.only_ours else roots[: args.limit])
    items, failed = [], []
    for repo_id, root in roots:
        try:
            items += list_episodes(root, repo_id)
        except Exception as e:
            failed.append({"repo_id": repo_id, "error": f"listing: {type(e).__name__}: {str(e)[:160]}"})
    print(f"{len(roots)} datasets, {len(items)} episode-camera items; listing failed for {len(failed)}", flush=True)

    ray.init(num_cpus=cfg["scoring"]["num_cpus"], include_dashboard=False)
    t0 = time.time()
    try:
        rows = (ray.data.from_items(items)
                .map(Scorer, fn_constructor_kwargs={"weights": "/data/weights/resnet18-f37072fd.pth", "cfg": cfg["scoring"]},
                     concurrency=cfg["scoring"]["num_cpus"], num_cpus=1)
                .take_all())
    finally:
        ray.shutdown()
    seconds = time.time() - t0
    pd.DataFrame(rows + failed).to_parquet(out / "video_scores.parquet", index=False)

    import torch
    import torchcodec
    import torchvision

    ffmpeg = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[:1]
    (out / "versions.json").write_text(json.dumps({
        "ffmpeg": ffmpeg[0] if ffmpeg else "unknown", "torchcodec": torchcodec.__version__, "torch": torch.__version__,
        "torchvision": torchvision.__version__, "ray": ray.__version__, "machine": platform.machine(),
        "image_digest": os.environ.get("IMAGE_DIGEST", "not set"), "num_cpus": cfg["scoring"]["num_cpus"],
        "seconds": seconds, "items": len(items), "datasets": len(roots), "only_ours": args.only_ours, "limit": args.limit,
    }, indent=2))
    print(f"Scored {len(rows)} items in {seconds:.0f} s ({len(rows) / max(seconds, 1e-9) * 60:,.0f} per minute)")


# ---------------------------------------------------------------- summarize (Mac)

def cosine(a, b):
    """a @ b.T for unit vectors. NumPy's matmul on Apple's Accelerate raises spurious divide, overflow
    and invalid flags here even when every result is finite, so the flags are silenced and the result
    is checked instead."""
    import numpy as np

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        out = a @ b.T
    if not np.isfinite(out).all():
        raise ValueError("non-finite cosine similarity: check the embeddings")
    return out


def role(camera: str) -> str:
    return "wrist" if "wrist" in camera.lower() else "fixed"


def cmd_summarize(args, cfg) -> None:
    import subprocess

    import numpy as np
    import pandas as pd

    src = Path(args.scores_dir)
    df = pd.read_parquet(src / "video_scores.parquet")
    versions = json.loads((src / "versions.json").read_text())
    if "error" not in df:
        df["error"] = None
    ok = df[df["error"].isna() & df["emb_first"].notna()].copy()
    ok["role"] = ok["camera"].map(role)

    # Similarity to our scene: cosine distance of each first frame to the nearest of ours, per camera role.
    # Our own episodes are compared with the other 44 (leave one out), for scale.
    ok["dist_to_ours"] = np.nan
    ok["scene_dup_elsewhere"] = False
    for r in ("wrist", "fixed"):
        part = ok[ok.role == r]
        if part.empty:
            continue
        e = np.stack(part["emb_first"].to_numpy())
        e = e / np.linalg.norm(e, axis=1, keepdims=True)
        is_ours = (part.repo_id == OURS_ID).to_numpy()
        sim = cosine(e, e[is_ours]) if is_ours.any() else None
        if sim is not None:
            if is_ours.sum() > 1:
                sim[np.where(is_ours)[0], np.arange(is_ours.sum())] = -np.inf  # leave one out
            ok.loc[part.index, "dist_to_ours"] = 1 - sim.max(axis=1)
        # Near-duplicate scenes across datasets (the same scene re-uploaded or re-recorded).
        full = cosine(e, e)
        same = part.repo_id.to_numpy()[:, None] == part.repo_id.to_numpy()[None, :]
        full[same] = -np.inf
        ok.loc[part.index, "scene_dup_elsewhere"] = (1 - full.max(axis=1)) < cfg["scoring"]["scene_dup_distance"]

    full_out = Path("outputs/p03_video_scores_full.parquet")
    ok.to_parquet(full_out, index=False)

    score_cols = ["sharpness", "brightness", "motion_diff", "frozen_fraction", "dist_to_ours"]
    RESULTS.mkdir(parents=True, exist_ok=True)
    ok[ok.repo_id == OURS_ID].drop(columns=["emb_first", "emb_mid"]).to_csv(
        RESULTS / "scores_video_ours.csv", index=False, float_format="%.4f")

    per = ok.groupby(["repo_id", "role"])[score_cols].median().unstack("role")
    per.columns = [f"median_{s}_{r}" for s, r in per.columns]
    per.insert(0, "episodes", ok.groupby("repo_id")["episode_index"].nunique())
    per.insert(1, "scene_dup_elsewhere", ok.groupby("repo_id")["scene_dup_elsewhere"].mean().round(3))
    spread = {}
    for rid, g in ok[ok.role == "fixed"].groupby("repo_id"):
        e = np.stack(g["emb_first"].to_numpy())
        e = e / np.linalg.norm(e, axis=1, keepdims=True)
        spread[rid] = float(1 - cosine(e, e)[np.triu_indices(len(e), 1)].mean()) if len(e) > 1 else np.nan
    per["scene_spread_fixed"] = pd.Series(spread)
    per.to_csv(RESULTS / "scores_video_by_dataset.csv", float_format="%.4f")

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain", "projects/03-ray-curation/src", "projects/03-ray-curation/configs",
                       "projects/03-ray-curation/Dockerfile"], capture_output=True, text=True).stdout.strip():
        commit += " plus uncommitted changes to the code, config or Dockerfile"
    ours, public = ok[ok.repo_id == OURS_ID], ok[ok.repo_id != OURS_ID]
    errors = df[df["error"].notna()]
    lines = [
        "# Video scores for the shortlist: summary (step 3b)",
        "",
        "Decoded inside the container (`projects/03-ray-curation/Dockerfile`: no network, videos mounted read-only), "
        "summarized on the Mac by `src/score_video.py` with `configs/scoring_stage2.yaml`.",
        "",
        f"- Code: git commit `{commit}`; image digest `{versions['image_digest']}`",
        f"- Versions in the container: {versions['ffmpeg']}; torchcodec {versions['torchcodec']}; torch {versions['torch']}; "
        f"Ray {versions['ray']}; {versions['machine']}, {versions['num_cpus']} CPUs",
        f"- Datasets: {versions['datasets']} (ours included)" + ("; our dataset only" if versions["only_ours"] else "")
        + (f"; first {versions['limit']} public only" if versions["limit"] else ""),
        f"- Episode-camera items: {versions['items']}; scored {len(ok)}; failed {len(errors)}",
        "- Failures: " + (", ".join(f"{k} {v}" for k, v in errors["error"].str.split(":").str[0].value_counts().items()) or "none"),
        f"- Decoding and scoring: {versions['seconds'] / 60:.1f} min, {len(df) / max(versions['seconds'], 1e-9) * 60:,.0f} items per minute",
        f"- Episode-camera items whose first frame nearly matches a scene in another dataset: {int(ok['scene_dup_elsewhere'].sum())}",
        "",
        "## Distributions",
        "",
        "Median, with the 10th to 90th percentile in brackets, per camera role (`wrist`, or `fixed` for any other camera). "
        "`dist_to_ours` for our own episodes is to the nearest of our other 44.",
        "",
        "| Score | Role | Ours | Public | Ours in public |",
        "|---|---|---|---|---|",
    ]
    for c in score_cols:
        for r in ("wrist", "fixed"):
            o, p = ours[ours.role == r][c].dropna(), public[public.role == r][c].dropna()

            def fmt(s):
                return f"{s.median():.3g} [{s.quantile(0.1):.3g} to {s.quantile(0.9):.3g}]" if len(s) else "-"
            rank = f"{(p < o.median()).mean() * 100:.0f}%" if len(o) and len(p) else "-"
            lines.append(f"| `{c}` | {r} | {fmt(o)} | {fmt(p)} | {rank} |")
    lines += [
        "",
        "## Notes",
        "",
        "- `sharpness`: variance of the Laplacian (higher is sharper), median over 5 frames. `brightness`: mean gray level, 0 to 255.",
        "- `motion_diff` and `frozen_fraction`: change between 10 consecutive frames at the middle of the episode. "
        "A frozen camera has a low `motion_diff` while the joints move (compare with 3a's idle fraction).",
        "- `dist_to_ours`: cosine distance of ResNet-18 ImageNet features of the first frame to the nearest of our episodes. "
        "Lower means a scene that looks more like ours. It is a proxy; it says nothing about the task.",
        "- No public frames are committed or uploaded. Full table (with embeddings): `outputs/p03_video_scores_full.parquet`, "
        "uploaded privately to the Hub.",
    ]
    (RESULTS / "scoring_stage2.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {full_out}, {RESULTS / 'scores_video_ours.csv'}, {RESULTS / 'scores_video_by_dataset.csv'}, "
          f"{RESULTS / 'scoring_stage2.md'}")


def main() -> None:
    import yaml

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=CONFIG)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("score", help="decode and score (inside the container only)")
    p.add_argument("--only-ours", action="store_true")
    p.add_argument("--limit", type=int, default=None, help="first N public datasets only")
    q = sub.add_parser("summarize", help="write results from the container's output (on the Mac)")
    q.add_argument("--scores-dir", default="outputs/p03_video_scores")
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    if args.cmd == "score":
        if not Path("/data/video").exists():
            raise SystemExit("score runs inside the container only (it decodes untrusted video); see the Dockerfile.")
        cmd_score(args, cfg)
    else:
        cmd_summarize(args, cfg)


if __name__ == "__main__":
    main()
