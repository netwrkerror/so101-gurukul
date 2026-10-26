"""Step 3, stage 1: score every task-relevant episode from its joint data only (no video).

For our dataset and each task-relevant compatible dataset in the catalog, download only
`meta/info.json` and `data/*.parquet` at a pinned commit, then compute per-episode scores
with Ray Data: length, idle fraction, hesitations, jerk, gripper open events, the gap
between commanded (leader) and measured (follower) joints, and a fingerprint to find copies.

Downloaded files are only parsed as data: pyarrow reads the parquet columns and json reads
info.json. Nothing is unpickled and no downloaded code is run.

Run from the repo root (does not touch the arm):
    uv run python projects/03-ray-curation/src/score_trajectories.py --plan        # sizes only, no download
    uv run python projects/03-ray-curation/src/score_trajectories.py --only-ours   # our 45 episodes
    uv run python projects/03-ray-curation/src/score_trajectories.py               # everything
Outputs:
    projects/03-ray-curation/results/scores_ours.csv          (our 45 episodes, committed)
    projects/03-ray-curation/results/scores_by_dataset.csv    (one row per dataset, committed)
    projects/03-ray-curation/results/scoring_stage1.md        (throughput and distributions)
    outputs/p03_episode_scores.parquet                        (every episode, local; later private on the Hub)
"""

import argparse
import csv
import json
import os
import time
from pathlib import Path

# Must be set before Ray is imported (see src/ray_check.py and DECISIONS.md, 2026-10-25).
os.environ["RAY_USAGE_STATS_ENABLED"] = "0"
os.environ["RAY_ENABLE_UV_RUN_RUNTIME_ENV"] = "0"

import ray  # noqa: E402
import yaml  # noqa: E402

CONFIG = Path("projects/03-ray-curation/configs/scoring_stage1.yaml")
RESULTS = Path("projects/03-ray-curation/results")
ALL_SCORES = Path("outputs/p03_episode_scores.parquet")
PLAN_TABLE = Path("outputs/p03_plan.csv")
SCORES = ["length_s", "idle_fraction", "hesitations", "hesitation_s", "jerk", "gripper_open_events", "action_state_gap"]


def local_name(repo_id: str) -> str:
    return repo_id.replace("/", "__")


def with_retries(fn):
    from huggingface_hub.errors import HfHubHTTPError

    for attempt in range(5):
        try:
            return fn()
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            # The Hub's Xet file transfer reports rate limiting as a RuntimeError mentioning 429.
            transient = (isinstance(e, HfHubHTTPError) and status in (429, 500, 502, 503, 504, None)) or "429" in str(e)
            if transient and attempt < 4:
                time.sleep(2 ** (attempt + 2))
                continue
            raise


def error_kind(error: str) -> str:
    """Group errors without request IDs."""
    if "429" in error:
        return "rate limited (429)"
    if error.startswith("HfHubHTTPError"):
        return "HfHubHTTPError (no status code)"
    return error


def joint_ranges(files: list[Path]) -> tuple[list[float], list[float]]:
    """0.5th and 99.5th percentile of each action joint over the whole dataset."""
    import numpy as np
    import pyarrow.parquet as pq

    acts = [as_matrix(pq.read_table(f, columns=["action"]).column("action")) for f in files]
    a = np.concatenate(acts)
    return np.percentile(a, 0.5, axis=0).tolist(), np.percentile(a, 99.5, axis=0).tolist()


def as_matrix(column):
    """A list-of-6-floats parquet column as an (n, 6) float array."""
    import numpy as np

    flat = column.combine_chunks().flatten().to_numpy(zero_copy_only=False)
    return np.asarray(flat, dtype=np.float64).reshape(-1, 6)


@ray.remote(num_cpus=0.05)
def prepare(repo_id: str, cfg: dict, plan_only: bool) -> dict:
    """Plan (and unless plan_only, download) one dataset. Never raises: problems become an error field."""
    try:
        return _prepare(repo_id, cfg, plan_only)
    except Exception as e:
        return {"repo_id": repo_id, "error": f"{type(e).__name__}: {str(e).splitlines()[0][:120] if str(e) else ''}"}


def _prepare(repo_id: str, cfg: dict, plan_only: bool) -> dict:
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download

    dest = Path(cfg["download_dir"]) / local_name(repo_id)
    manifest_path = dest / "manifest.json"
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text())
        if m.get("complete"):
            return m | {"cached": True}

    info = with_retries(lambda: HfApi().dataset_info(repo_id, files_metadata=True))
    files = [s for s in info.siblings if s.rfilename.startswith("data/") and s.rfilename.endswith(".parquet")]
    m = {"repo_id": repo_id, "revision": info.sha, "data_files": len(files),
         "data_bytes": sum(s.size or 0 for s in files), "largest_file_bytes": max((s.size or 0 for s in files), default=0)}
    if not files:
        return m | {"error": "no data parquet files"}
    # LeRobot merges only datasets whose features have the same dtype; ours stores cameras as video.
    meta = json.loads(Path(with_retries(lambda: hf_hub_download(repo_id, "meta/info.json", repo_type="dataset",
                                                                 revision=info.sha, local_dir=dest))).read_text())
    cam_dtypes = {v.get("dtype") for k, v in meta.get("features", {}).items() if k.startswith("observation.images.")}
    m.update(episodes=meta.get("total_episodes"), camera_dtypes=";".join(sorted(str(d) for d in cam_dtypes)))
    if cam_dtypes != {"video"}:
        return m | {"error": "cameras not stored as video (cannot merge with ours)"}
    if m["largest_file_bytes"] > cfg["caps"]["file_mb"] * 1e6:
        return m | {"error": f"a data file is larger than {cfg['caps']['file_mb']} MB"}
    if plan_only:
        return m

    with_retries(lambda: snapshot_download(repo_id, repo_type="dataset", revision=info.sha, local_dir=dest,
                                           allow_patterns=["meta/info.json", "data/*"]))
    local = sorted(dest.glob("data/**/*.parquet"))
    lo, hi = joint_ranges(local)
    meta = json.loads((dest / "meta/info.json").read_text())
    m.update(fps=meta.get("fps"), codebase_version=meta.get("codebase_version"), lo=lo, hi=hi,
             files=[str(p) for p in local], complete=True)
    manifest_path.write_text(json.dumps(m))
    return m


def prepare_ours(cfg: dict) -> dict:
    root = Path(os.path.expanduser(cfg["ours"]["root"]))
    files = sorted(root.glob("data/**/*.parquet"))
    lo, hi = joint_ranges(files)
    meta = json.loads((root / "meta/info.json").read_text())
    try:
        from huggingface_hub import HfApi
        revision = HfApi().dataset_info(cfg["ours"]["repo_id"]).sha
    except Exception:
        revision = "unknown (local copy)"
    return {"repo_id": cfg["ours"]["repo_id"], "revision": revision, "fps": meta["fps"],
            "codebase_version": meta["codebase_version"], "lo": lo, "hi": hi, "files": [str(p) for p in files],
            "data_bytes": sum(p.stat().st_size for p in files), "complete": True}


def score_file(item: dict) -> list[dict]:
    """Ray Data flat_map: one parquet file in, one row per episode out."""
    import numpy as np
    import pyarrow.parquet as pq

    try:
        t = pq.read_table(item["path"], columns=["episode_index", "frame_index", "action", "observation.state"])
        ep = t.column("episode_index").to_numpy()
        fr = t.column("frame_index").to_numpy()
        act, state = as_matrix(t.column("action")), as_matrix(t.column("observation.state"))
    except Exception as e:
        return [{"repo_id": item["repo_id"], "file": item["path"], "episode_index": -1,
                 "error": f"{type(e).__name__}: {str(e)[:120]}"}]
    rows = []
    for e in np.unique(ep):
        idx = np.where(ep == e)[0]
        idx = idx[np.argsort(fr[idx])]
        row = {"repo_id": item["repo_id"], "file": Path(item["path"]).name, "episode_index": int(e), "frames": len(idx)}
        try:
            row.update(episode_scores(act[idx], state[idx], item))
        except Exception as ex:
            row["error"] = f"{type(ex).__name__}: {str(ex)[:120]}"
        rows.append(row)
    return rows


def episode_scores(act, state, item: dict) -> dict:
    import hashlib

    import numpy as np

    s = item["scores"]
    fps = float(item["fps"])
    lo, hi = np.array(item["lo"]), np.array(item["hi"])
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    a, x = (act - lo) / span, (state - lo) / span  # both on the action range, so the gap is comparable
    if not np.isfinite(x).all() or not np.isfinite(a).all():
        raise ValueError("non-finite joint values")
    n = len(x)
    out = {"length_s": n / fps}
    # Whole episode, raw values: a copy matches exactly. (The first 30 frames alone matched episodes that only
    # share a resting start pose.)
    fp = np.round(act, s["fingerprint_decimals"]).astype(np.float32)
    out["fingerprint"] = hashlib.sha1(fp.tobytes()).hexdigest()[:16]
    k = s["smooth_frames"]
    if n < k + 4:
        return out | {"error": "too short to score"}

    kernel = np.ones(k) / k
    xs = np.stack([np.convolve(x[:, j], kernel, mode="valid") for j in range(6)], axis=1)
    speed = np.abs(np.diff(xs, axis=0)) * fps  # per joint, range per second
    moving = speed.max(axis=1) > s["idle_speed"]
    out["idle_fraction"] = float(1 - moving.mean())

    # Hesitations: idle runs of at least hesitation_min_s between the first and last motion.
    hes, hes_frames = 0, 0
    if moving.any():
        first, last = np.argmax(moving), len(moving) - 1 - np.argmax(moving[::-1])
        run = 0
        for m in moving[first:last + 1]:
            if not m:
                run += 1
                continue
            if run >= s["hesitation_min_s"] * fps:
                hes, hes_frames = hes + 1, hes_frames + run
            run = 0
    out["hesitations"], out["hesitation_s"] = hes, hes_frames / fps

    # Jerk: third derivative of the smoothed body joints (gripper excluded), median while moving.
    jerk = np.linalg.norm(np.diff(xs[:, :5], n=3, axis=0), axis=1) * fps ** 3
    mv = moving[2:]  # align: diff n=3 is two frames shorter than diff n=1
    out["jerk"] = float(np.median(jerk[mv])) if mv.any() else 0.0

    # Gripper open events from the commanded gripper (the operator's intent), with hysteresis.
    opened, events = a[0, 5] > s["gripper_high"], 0
    for g in a[:, 5]:
        if not opened and g > s["gripper_high"]:
            opened, events = True, events + 1
        elif opened and g < s["gripper_low"]:
            opened = False
    out["gripper_open_events"] = events

    out["action_state_gap"] = float(np.abs(a[:, :5] - x[:, :5]).mean())  # body joints; the gripper stalls on the object
    return out


def candidates(cfg: dict) -> list[str]:
    with open(cfg["catalog"]) as f:
        return sorted(r["repo_id"] for r in csv.DictReader(f) if r["relevant"] == "True")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--plan", action="store_true", help="only list sizes on the Hub; download nothing")
    parser.add_argument("--only-ours", action="store_true", help="score our dataset only (no network needed)")
    parser.add_argument("--limit", type=int, default=None, help="use only the first N public datasets (for a test)")
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())

    public = [] if args.only_ours else candidates(cfg)[: args.limit]
    ray.init(num_cpus=cfg["ray"]["num_cpus"], include_dashboard=True, dashboard_host="127.0.0.1")
    print(f"Ray {ray.__version__} started. Dashboard: http://127.0.0.1:8265")
    try:
        t0 = time.time()
        manifests = run_prepare(public, cfg, args.plan)
        download_s = time.time() - t0
        if args.plan:
            report_plan(manifests, cfg)
            return
        ours = prepare_ours(cfg)
        ready = [ours] + [m for m in manifests if m.get("complete")]
        items = [{"repo_id": m["repo_id"], "path": p, "fps": m["fps"], "lo": m["lo"], "hi": m["hi"], "scores": cfg["scores"]}
                 for m in ready for p in m["files"]]
        t1 = time.time()
        rows = ray.data.from_items(items).flat_map(score_file, num_cpus=1).take_all()
        score_s = time.time() - t1
    finally:
        ray.shutdown()
    write_outputs(rows, ready, manifests, cfg, download_s, score_s, ours["repo_id"], args)


def run_prepare(public: list[str], cfg: dict, plan_only: bool) -> list[dict]:
    """Plan every dataset first; download only if the planned total is within the cap."""
    plans = run_tasks(public, cfg, plan_only=True)
    if plan_only:
        return plans
    fresh_gb = sum(m.get("data_bytes", 0) for m in plans if not m.get("cached") and not m.get("error")) / 1e9
    if fresh_gb > cfg["caps"]["total_gb"]:
        raise SystemExit(f"Stopped before downloading: {fresh_gb:.1f} GB planned, above the {cfg['caps']['total_gb']} GB cap.")
    print(f"Downloading {fresh_gb:.2f} GB")
    todo = [m["repo_id"] for m in plans if not m.get("error")]
    return run_tasks(todo, cfg, plan_only=False) + [m for m in plans if m.get("error")]


def run_tasks(repo_ids: list[str], cfg: dict, plan_only: bool) -> list[dict]:
    pending, done, queue = [], [], list(repo_ids)
    while queue or pending:
        while queue and len(pending) < cfg["caps"]["max_in_flight"]:
            pending.append(prepare.remote(queue.pop(0), cfg, plan_only))
        ready, pending = ray.wait(pending, num_returns=1)
        done.append(ray.get(ready[0]))
        if len(done) % 50 == 0 or not (queue or pending):
            print(f"{'planned' if plan_only else 'downloaded'} {len(done)}/{len(repo_ids)}", flush=True)
    return done


def report_plan(manifests: list[dict], cfg: dict) -> None:
    from collections import Counter

    import pandas as pd

    table = pd.DataFrame(manifests)
    table["kb_per_episode"] = table["data_bytes"] / table["episodes"].where(table["episodes"] > 0) / 1e3
    table.sort_values("data_bytes", ascending=False).to_csv(PLAN_TABLE, index=False, float_format="%.1f")
    print(f"Wrote {PLAN_TABLE}")
    for label, part in (("would be downloaded", table[table["error"].isna()] if "error" in table else table),
                        ("skipped", table[table["error"].notna()] if "error" in table else table.iloc[:0])):
        if len(part):
            print(f"{label}: {len(part)} datasets, {part['data_bytes'].sum() / 1e9:.2f} GB, "
                  f"median {part['kb_per_episode'].median():.0f} KB per episode")
    ok = [m for m in manifests if not m.get("error")]
    total = sum(m["data_bytes"] for m in ok) / 1e9
    print(f"\nDatasets: {len(manifests)}; plannable: {len(ok)}; data files: {sum(m['data_files'] for m in ok)}")
    print(f"Total parquet to download: {total:.2f} GB (cap {cfg['caps']['total_gb']} GB)")
    print(f"Largest file: {max((m['largest_file_bytes'] for m in ok), default=0) / 1e6:.0f} MB")
    print("Errors:", dict(Counter(error_kind(m["error"]) for m in manifests if m.get("error"))) or "none")


def write_outputs(rows, ready, manifests, cfg, download_s, score_s, ours_id, args) -> None:
    import pandas as pd

    df = pd.DataFrame(rows)
    for c in SCORES + ["error", "fingerprint"]:
        if c not in df:
            df[c] = None
    # A fingerprint shared with another dataset marks a likely copy.
    fp = df.dropna(subset=["fingerprint"]).groupby("fingerprint")["repo_id"].nunique()
    df["copy_elsewhere"] = df["fingerprint"].map(fp).fillna(1) > 1
    df = df.sort_values(["repo_id", "episode_index"])
    ALL_SCORES.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(ALL_SCORES, index=False)

    RESULTS.mkdir(parents=True, exist_ok=True)
    df[df.repo_id == ours_id].drop(columns=["file"]).to_csv(RESULTS / "scores_ours.csv", index=False, float_format="%.4f")

    by_m = {m["repo_id"]: m for m in ready}
    ok = df[df["error"].isna()]
    per = ok.groupby("repo_id")[SCORES].median()
    per.columns = [f"median_{c}" for c in per.columns]
    per.insert(0, "episodes_scored", ok.groupby("repo_id").size())
    per.insert(1, "episodes_failed", df[df["error"].notna()].groupby("repo_id").size().reindex(per.index).fillna(0).astype(int))
    per.insert(2, "episodes_copied_elsewhere", ok.groupby("repo_id")["copy_elsewhere"].sum())
    per["revision"] = [by_m[r]["revision"] for r in per.index]
    per["codebase_version"] = [by_m[r]["codebase_version"] for r in per.index]
    per["action_low"] = [";".join(f"{v:.1f}" for v in by_m[r]["lo"]) for r in per.index]
    per["action_high"] = [";".join(f"{v:.1f}" for v in by_m[r]["hi"]) for r in per.index]
    per.to_csv(RESULTS / "scores_by_dataset.csv", float_format="%.4f")

    write_summary(df, ours_id, manifests, download_s, score_s, cfg, args)
    print(f"Wrote {ALL_SCORES} ({len(df)} episodes), {RESULTS / 'scores_ours.csv'}, "
          f"{RESULTS / 'scores_by_dataset.csv'} and {RESULTS / 'scoring_stage1.md'}")


def write_summary(df, ours_id, manifests, download_s, score_s, cfg, args) -> None:
    import subprocess
    from collections import Counter

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain", "projects/03-ray-curation/src", "projects/03-ray-curation/configs"],
                      capture_output=True, text=True).stdout.strip():
        commit += " plus uncommitted changes to the code or config"
    ok = df[df["error"].isna()]
    ours, public = ok[ok.repo_id == ours_id], ok[ok.repo_id != ours_id]
    fresh = [m for m in manifests if m.get("complete") and not m.get("cached")]
    lines = [
        "# Episode scores from joint data: summary (step 3, stage 1)",
        "",
        "Built by `src/score_trajectories.py` with `configs/scoring_stage1.yaml`. No video was downloaded.",
        "",
        f"- Code: git commit `{commit}`; run on the dev machine (local Ray, {cfg['ray']['num_cpus']} CPUs)"
        + (f"; first {args.limit} public datasets only" if args.limit else "") + ("; our dataset only" if args.only_ours else ""),
        f"- Datasets: ours plus {len(manifests)} public; ready {sum(1 for m in manifests if m.get('complete'))}; "
        f"failed {sum(1 for m in manifests if m.get('error'))}",
        "- Failures by type: " + (", ".join(f"{k} {v}" for k, v in Counter(error_kind(m['error']) for m in manifests if m.get('error')).most_common())
                                  or "none"),
        f"- Episodes scored: {len(ok)} (ours {len(ours)}, public {len(public)}); failed or too short: {len(df) - len(ok)}",
        f"- Download: {download_s / 60:.1f} min for {len(fresh)} datasets, "
        f"{sum(m['data_bytes'] for m in fresh) / 1e9:.2f} GB (datasets already downloaded are not re-fetched)",
        f"- Scoring: {score_s:.0f} s, {len(df) / max(score_s, 1e-9) * 60:,.0f} episodes per minute",
        "- Episodes with an exact copy in another dataset (every action identical): "
        f"{int(ok['copy_elsewhere'].sum())}",
        "",
        "## Distributions",
        "",
        "Median, with the 10th to 90th percentile in brackets. \"Ours in public\" is the percentile of our median among public episodes.",
        "",
        "| Score | Ours | Public | Ours in public |",
        "|---|---|---|---|",
    ]
    for c in SCORES:
        def fmt(s):
            return f"{s.median():.3g} [{s.quantile(0.1):.3g} to {s.quantile(0.9):.3g}]" if len(s) else "-"
        rank = f"{(public[c] < ours[c].median()).mean() * 100:.0f}%" if len(public) and len(ours) else "-"
        lines.append(f"| `{c}` | {fmt(ours[c].dropna())} | {fmt(public[c].dropna())} | {rank} |")
    lines += [
        "",
        "## Notes",
        "",
        "- Joint values are scaled to 0 to 1 per dataset (its own 0.5th to 99.5th action percentiles). Units differ between "
        "datasets (degrees in ours); the raw ranges are in `scores_by_dataset.csv`.",
        "- `jerk` and `action_state_gap` leave out the gripper. `gripper_open_events` uses the commanded gripper.",
        "- These are proxies for quality, not quality itself. Step 4 checks them against a manual review.",
    ]
    (RESULTS / "scoring_stage1.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
