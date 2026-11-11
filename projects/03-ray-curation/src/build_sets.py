"""Step 5a, part 2: build S2 and S3 as LeRobot datasets, inside the isolated container.

Reads outputs/p03_sets/plan.json (written by src/curate_plan.py). For each public source dataset,
in parallel Ray tasks:
  1. assemble a local copy at the planned revision (data from step 3a, meta and videos from step 3b),
  2. convert LeRobot v2.1 to v3.0 with LeRobot's own converter (offline),
  3. keep only the planned episodes (LeRobot's delete_episodes),
  4. drop cameras other than the mapped wrist and front cameras (remove_feature),
  5. rename cameras to `wrist` and `front`, joint names and robot_type to ours (metadata only),
  6. re-encode every video to our settings (reencode_dataset), then align the remaining video
     metadata with ours, so LeRobot's merge accepts it.
Then it merges ours plus every source (merge_datasets), recomputes statistics, and validates: the
features equal ours, the set loads, and the first frame of every source decodes.

This decodes untrusted video, so it refuses to run outside the container. Run (does not touch the arm):
see the Dockerfile header. Outputs (in the writable mount, outputs/p03_sets/ on the Mac):
    <set>/            the merged LeRobot dataset, ready to upload privately
    <set>_build.json  per-source results, the validation, versions, and timing
"""

import argparse
import json
import os
import shutil
import time
from pathlib import Path

os.environ["RAY_USAGE_STATS_ENABLED"] = "0"
os.environ["RAY_ENABLE_UV_RUN_RUNTIME_ENV"] = "0"
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # no network in the container; never try the Hub

OUT = Path("/data/out")
PUBLIC_DATA = Path("/data/public")   # step 3a downloads: meta/info.json and data/
PUBLIC_VIDEO = Path("/data/video")   # step 3b downloads: meta/ and videos/
OURS = Path("/data/ours")
# What a video file actually is, as probed by LeRobot when it writes the info. These must equal ours.
FILE_KEYS = ("video.codec", "video.pix_fmt", "video.height", "video.width", "video.fps", "video.channels")


def local_name(repo_id: str) -> str:
    return repo_id.replace("/", "__")


def rename_in_place(root: Path, cams: dict[str, str], ours_info: dict) -> None:
    """Rename camera keys (old -> new), set joint names and robot_type to ours. v3.0 metadata only."""
    import pandas as pd

    info_path = root / "meta/info.json"
    info = json.loads(info_path.read_text())
    full = {f"observation.images.{o}": f"observation.images.{n}" for o, n in cams.items() if o != n}
    # Two steps through temporary names, so a rename never overwrites a camera not yet renamed.
    tmp = {old: f"{new}__tmp" for old, new in full.items()}
    for step in (tmp, {f"{new}__tmp": new for new in full.values()}):
        info["features"] = {step.get(k, k): v for k, v in info["features"].items()}
        for old, new in step.items():
            if (root / "videos" / old).exists():
                (root / "videos" / old).rename(root / "videos" / new)
        for f in sorted((root / "meta/episodes").rglob("*.parquet")):
            df = pd.read_parquet(f)
            df.columns = [next((c.replace(f"/{o}/", f"/{n}/", 1) for o, n in step.items() if f"/{o}/" in c), c)
                          for c in df.columns]
            df.to_parquet(f, index=False)
        stats_path = root / "meta/stats.json"
        if stats_path.exists():
            stats = json.loads(stats_path.read_text())
            stats_path.write_text(json.dumps({step.get(k, k): v for k, v in stats.items()}, indent=4))
    for k in ("action", "observation.state"):
        info["features"][k]["names"] = ours_info["features"][k]["names"]
    info["robot_type"] = ours_info["robot_type"]
    info_path.write_text(json.dumps(info, indent=4))


def align_video_info(root: Path, ours_info: dict) -> list[str]:
    """After re-encoding, report fields that differ from ours, then copy our video feature definitions.

    The caller stops on a difference in what the files actually are (codec, pixel format, size, fps),
    so the copied metadata never claims something the files are not.
    """
    from lerobot.configs import VIDEO_ENCODER_INFO_KEYS

    info_path = root / "meta/info.json"
    info = json.loads(info_path.read_text())
    differs = []
    keys = set(VIDEO_ENCODER_INFO_KEYS) | set(FILE_KEYS)
    for key in ("observation.images.wrist", "observation.images.front"):
        mine, theirs = info["features"][key].get("info", {}), ours_info["features"][key]["info"]
        differs += [f"{key}:{k}" for k in sorted(keys) if k in theirs and mine.get(k) != theirs.get(k)]
        if tuple(info["features"][key].get("shape", [])) != tuple(ours_info["features"][key]["shape"]):
            differs.append(f"{key}:shape")
        info["features"][key] = json.loads(json.dumps(ours_info["features"][key]))
    info_path.write_text(json.dumps(info, indent=4))
    return differs


def prepare_source(src: dict, set_name: str, video_cfg: dict) -> dict:
    """Steps 1 to 6 for one public source. Never raises: problems become an error field."""
    t0 = time.time()
    out = {"repo_id": src["repo_id"], "episodes": len(src["episodes"])}
    try:
        out.update(_prepare(src, set_name, video_cfg))
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {str(e).splitlines()[0][:200] if str(e) else ''}"
    out["seconds"] = round(time.time() - t0, 1)
    return out


def _prepare(src: dict, set_name: str, video_cfg: dict) -> dict:
    from lerobot.configs import RGBEncoderConfig
    from lerobot.datasets import LeRobotDataset
    from lerobot.datasets.dataset_tools import delete_episodes, reencode_dataset, remove_feature
    from lerobot.scripts.convert_dataset_v21_to_v30 import convert_dataset

    name = local_name(src["repo_id"])
    work = OUT / "work" / set_name / name
    if work.exists():
        shutil.rmtree(work)
    raw = work / "raw"
    # 1. Assemble. Both downloads were made at the revision planned in step 3a; check that.
    for d in (PUBLIC_DATA / name, PUBLIC_VIDEO / name):
        rev = json.loads((d / "manifest.json").read_text())["revision"]
        if rev != src["revision"]:
            raise ValueError(f"revision mismatch in {d.name}: {rev} != {src['revision']}")
    shutil.copytree(PUBLIC_VIDEO / name / "meta", raw / "meta")
    shutil.copytree(PUBLIC_VIDEO / name / "videos", raw / "videos")
    shutil.copytree(PUBLIC_DATA / name / "data", raw / "data")
    # 2. Convert v2.1 to v3.0 (offline: root given, no push).
    if str(src["codebase_version"]).startswith("v2"):
        convert_dataset(repo_id=src["repo_id"], root=raw, push_to_hub=False, force_conversion=True)
        shutil.rmtree(raw.parent / f"{raw.name}_old", ignore_errors=True)
    ds = LeRobotDataset(src["repo_id"], root=raw)
    total = ds.meta.total_episodes
    # 3. Keep only the planned episodes.
    drop = sorted(set(range(total)) - set(src["episodes"]))
    if drop:
        ds = delete_episodes(ds, drop, output_dir=work / "sel", repo_id=src["repo_id"])
    # 4. Drop the other cameras.
    if src["drop"]:
        ds = remove_feature(ds, [f"observation.images.{c}" for c in src["drop"]], output_dir=work / "cams",
                            repo_id=src["repo_id"])
    root = Path(ds.root)
    # 5. Rename to our camera keys, joint names and robot type.
    ours_info = json.loads((OURS / "meta/info.json").read_text())
    rename_in_place(root, {src["wrist"]: "wrist", src["front"]: "front"}, ours_info)
    # 6. Re-encode to our settings, then align the video metadata with ours.
    ds = LeRobotDataset(src["repo_id"], root=root)
    target = RGBEncoderConfig(vcodec="libsvtav1", pix_fmt=video_cfg["pix_fmt"], crf=video_cfg["crf"],
                              g=video_cfg["g"], preset=video_cfg["preset"])
    reencode_dataset(ds, rgb_encoder=target)
    differs = align_video_info(root, ours_info)
    # The merge concatenates files with FFmpeg's concat demuxer, which needs the same codec and pixel format.
    critical = [d for d in differs if d.split(":")[1] in FILE_KEYS + ("shape",)]
    if critical:
        raise ValueError(f"the video files still differ from ours after re-encoding: {critical}")
    ds = LeRobotDataset(src["repo_id"], root=root)
    return {"root": str(root), "source_episodes": total, "kept_episodes": ds.meta.total_episodes,
            "frames": ds.meta.total_frames, "converted": str(src["codebase_version"]).startswith("v2"),
            "encoder_fields_differing_before_alignment": differs}


def validate(merged_root: Path, set_repo: str, ours_info: dict, sources: list[dict]) -> dict:
    from lerobot.datasets import LeRobotDataset
    from lerobot.datasets.feature_utils import features_equal_for_merge

    ds = LeRobotDataset(set_repo, root=merged_root)
    checks = {"features_equal_ours": features_equal_for_merge(ours_info["features"], ds.meta.features),
              "robot_type": ds.meta.robot_type, "fps": ds.meta.fps,
              "episodes": ds.meta.total_episodes, "frames": ds.meta.total_frames}
    # Decode the first frame of every episode: ours and every public source (inside the container).
    failures = []
    for ep in range(ds.meta.total_episodes):
        idx = int(ds.meta.episodes[ep]["dataset_from_index"])
        try:
            frame = ds[idx]
            shapes = {k: tuple(v.shape) for k, v in frame.items() if k.startswith("observation.images.")}
            if any(s != (3, 480, 640) for s in shapes.values()):
                failures.append({"episode": ep, "error": f"shapes {shapes}"})
        except Exception as e:
            failures.append({"episode": ep, "error": f"{type(e).__name__}: {str(e)[:160]}"})
    checks["decode_failures"] = failures
    checks["ok"] = checks["features_equal_ours"] and not failures and checks["robot_type"] == ours_info["robot_type"]
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("set", choices=["s2", "s3"])
    parser.add_argument("--limit", type=int, default=None, help="first N sources only (a smoke test; not mergeable as the full set)")
    parser.add_argument("--num-cpus", type=int, default=4)
    args = parser.parse_args()
    if not PUBLIC_VIDEO.exists():
        raise SystemExit("build_sets.py runs inside the container only (it decodes untrusted video); see the Dockerfile.")
    if not os.environ.get("IMAGE_DIGEST", "").startswith("sha256:"):
        raise SystemExit("IMAGE_DIGEST is not set: pass -e IMAGE_DIGEST=<image id> so the results record which image ran.")

    import ray

    plan = json.loads((OUT / "plan.json").read_text())
    spec = plan["sets"][args.set]
    sources = spec["sources"][: args.limit]
    set_repo = spec["repo_id"] if args.limit is None else f"{spec['repo_id']}-smoke"
    t0 = time.time()
    ray.init(num_cpus=args.num_cpus, include_dashboard=False)
    try:
        task = ray.remote(num_cpus=1, max_retries=0)(prepare_source)
        results = ray.get([task.remote(s, args.set, plan["video"]) for s in sources])
    finally:
        ray.shutdown()
    prep_s = time.time() - t0
    failed = [r for r in results if r.get("error")]
    report = {"set": args.set, "repo_id": set_repo, "image_digest": os.environ["IMAGE_DIGEST"],
              "sources": results, "prepare_seconds": round(prep_s, 1)}
    if failed:
        report["status"] = "stopped: some sources failed; nothing merged"
    else:
        from lerobot.datasets import LeRobotDataset
        from lerobot.datasets.dataset_tools import merge_datasets, recompute_stats

        t1 = time.time()
        ours_info = json.loads((OURS / "meta/info.json").read_text())
        parts = [LeRobotDataset(plan["ours"]["repo_id"], root=OURS)] + [LeRobotDataset(r["repo_id"], root=r["root"]) for r in results]
        merged_root = OUT / args.set if args.limit is None else OUT / f"{args.set}_smoke"
        if merged_root.exists():
            shutil.rmtree(merged_root)
        merged = merge_datasets(parts, output_repo_id=set_repo, output_dir=merged_root)
        recompute_stats(merged)
        report["merge_seconds"] = round(time.time() - t1, 1)
        report["validation"] = validate(merged_root, set_repo, ours_info, sources)
        report["status"] = "ok" if report["validation"]["ok"] else "built, but validation failed"
    name = args.set if args.limit is None else f"{args.set}_smoke"
    (OUT / f"{name}_build.json").write_text(json.dumps(report, indent=1))
    print(f"{report['status']}: {len(results)} sources ({len(failed)} failed) in {prep_s:.0f} s; report: {name}_build.json")
    for r in failed:
        print("  ", r["repo_id"], r["error"])
    if "validation" in report:
        v = report["validation"]
        print(f"   validation: features equal ours {v['features_equal_ours']}, {v['episodes']} episodes, {v['frames']} frames, "
              f"decode failures {len(v['decode_failures'])}")


if __name__ == "__main__":
    main()
