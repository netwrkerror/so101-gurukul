"""Catalog public SO-100/SO-101 datasets on the Hugging Face Hub from metadata only.

For every public dataset tagged so100 or so101, Ray tasks fetch three small files
(meta/info.json, the task list, meta/stats.json) and the dataset card's license, without
downloading any video. Each dataset is checked for compatibility with ours
(causalerror/so101-toy-to-bowl) for merging, and for task relevance.

Run from the repo root (does not touch the arm):
    uv run python projects/03-ray-curation/src/catalog.py
Rebuild the outputs from saved rows only (no Hub listing, no fetches):
    uv run python projects/03-ray-curation/src/catalog.py --rebuild
Outputs:
    projects/03-ray-curation/results/catalog_compatible.csv   (compatible datasets, committed)
    projects/03-ray-curation/results/catalog_summary.md
    outputs/p03_catalog_full.csv                              (every dataset, local only)
"""

import argparse
import csv
import json
import os
import re
import time
from collections import Counter
from pathlib import Path

# Must be set before Ray is imported (see ray_check.py and DECISIONS.md, 2026-10-25).
os.environ["RAY_USAGE_STATS_ENABLED"] = "0"
os.environ["RAY_ENABLE_UV_RUN_RUNTIME_ENV"] = "0"

import ray  # noqa: E402

RESULTS = Path("projects/03-ray-curation/results")
# Each finished dataset is appended here as it arrives, so an interrupted run can resume.
PARTIAL = Path("outputs/p03_catalog_rows.jsonl")
FULL_TABLE = Path("outputs/p03_catalog_full.csv")
RUN_INFO = Path("outputs/p03_catalog_run.json")  # fetch time of the last full run, for --rebuild
OUR_VIDEO_MB_PER_EPISODE = 11  # our 45 episodes: 491 MB of video, two cameras
STAGE2_BUDGET_GB = 50
OUR_NAMESPACE = "causalerror"
OUR_JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
OUR_CAMERAS = {"wrist", "front"}
OUR_FPS = 30
OUR_IMAGE_SHAPE = (480, 640)
# Licenses that allow reuse (non-commercial included, by decision). Anything else, or none, is excluded.
ALLOWED_LICENSE_PREFIXES = ("apache", "mit", "bsd", "cc-by", "cc0", "odc", "odbl", "pddl", "cdla", "unlicense", "openrail", "gpl", "lgpl")
# LeRobot 0.6.0 reads v3.0 directly and ships a v2.1-to-v3.0 converter
# (lerobot/scripts/convert_dataset_v21_to_v30.py); older versions are excluded.
READABLE_VERSIONS = ("v3.0", "v2.1")
MIN_EPISODES = 10  # fewer usually means a test run
SIM_WORDS = ("sim", "simulation", "simulated", "mujoco", "isaac", "maniskill", "genesis", "gazebo", "pybullet", "robosuite", "libero", "synthetic")
RELEVANT_WORDS = ("pick", "place", "put", "drop", "bowl", "cup", "box", "basket", "bin", "container", "plate", "tray")


def normalize_joint(name: str) -> str:
    n = name.lower()
    for prefix in ("main_", "follower_"):
        n = n.removeprefix(prefix)
    for suffix in (".pos", "_pos", ".position"):
        n = n.removesuffix(suffix)
    return n


def feature_names(feature: dict) -> list[str]:
    names = feature.get("names")
    if isinstance(names, dict):  # older layouts: {"motors": [...]}
        names = next(iter(names.values()), [])
    return [str(n) for n in names] if isinstance(names, list) else []


def license_of(card_data, tags) -> str:
    lic = None
    if card_data is not None:
        lic = card_data.get("license") if hasattr(card_data, "get") else getattr(card_data, "license", None)
    if isinstance(lic, list):
        lic = lic[0] if lic else None
    if not lic:
        lic = next((t.split(":", 1)[1] for t in (tags or []) if t.startswith("license:")), None)
    return str(lic).lower() if lic else ""


@ray.remote(num_cpus=0.05)
def fetch(repo_id: str) -> dict:
    """Fetch one dataset's metadata. Never raises: problems become an error field."""
    try:
        return _fetch(repo_id)
    except Exception as e:
        return {"repo_id": repo_id, "error": f"{type(e).__name__}: {str(e).splitlines()[0][:120] if str(e) else ''}"}


def _fetch(repo_id: str) -> dict:
    from huggingface_hub import HfApi, hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError, GatedRepoError, HfHubHTTPError, RepositoryNotFoundError

    def with_retries(fn):
        for attempt in range(5):
            try:
                return fn()
            except HfHubHTTPError as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def download(filename):
        return with_retries(lambda: hf_hub_download(repo_id, filename, repo_type="dataset"))

    row = {"repo_id": repo_id}
    try:
        dinfo = with_retries(lambda: HfApi().dataset_info(repo_id))
        row["license"] = license_of(dinfo.card_data, dinfo.tags)
        row["downloads"] = getattr(dinfo, "downloads", None)
        row["tags"] = ";".join(t for t in (dinfo.tags or []) if not t.startswith(("license:", "region:")))[:300]
        info = json.loads(Path(download("meta/info.json")).read_text())
    except (EntryNotFoundError, RepositoryNotFoundError, GatedRepoError) as e:
        row["error"] = type(e).__name__
        return row
    except Exception as e:
        row["error"] = f"{type(e).__name__}: {str(e).splitlines()[0][:120]}"
        return row

    feats = info.get("features", {})
    cams = {k.removeprefix("observation.images."): v for k, v in feats.items() if k.startswith("observation.images.")}
    cam_640 = [n for n, v in cams.items() if tuple((v.get("shape") or [])[:2]) == OUR_IMAGE_SHAPE]
    action_joints = [normalize_joint(n) for n in feature_names(feats.get("action", {}))]
    state_joints = [normalize_joint(n) for n in feature_names(feats.get("observation.state", {}))]
    row.update({
        "codebase_version": info.get("codebase_version"),
        "robot_type": info.get("robot_type"),
        "fps": info.get("fps"),
        "episodes": info.get("total_episodes"),
        "frames": info.get("total_frames"),
        "cameras": ";".join(f"{n}:{'x'.join(str(s) for s in (v.get('shape') or [])[:2])}" for n, v in sorted(cams.items())),
        "cameras_640x480": len(cam_640),
        "action_joints": ";".join(action_joints),
        "state_joints": ";".join(state_joints),
    })

    tasks = []
    try:
        import pandas as pd
        df = pd.read_parquet(download("meta/tasks.parquet"))
        # Layouts differ: the task text is either the index (as in ours) or a "task" column.
        tasks = list(df["task"]) if "task" in df.columns else list(df.index)
    except Exception:
        try:
            tasks = [json.loads(line)["task"] for line in Path(download("meta/tasks.jsonl")).read_text().splitlines() if line.strip()]
        except Exception:
            pass
    tasks = [str(t) for t in tasks]
    row["tasks"] = " | ".join(tasks)[:500]
    row["n_tasks"] = len(tasks)

    try:
        stats = json.loads(Path(download("meta/stats.json")).read_text()).get("action", {})
        row["action_min"] = ";".join(f"{x:.1f}" for x in stats.get("min", []))
        row["action_max"] = ";".join(f"{x:.1f}" for x in stats.get("max", []))
    except Exception:
        pass
    return row


def normalize_version(v) -> str:
    v = str(v or "")
    return f"v{v}" if v[:1].isdigit() else v


def add_flags(row: dict) -> dict:
    row["codebase_version"] = normalize_version(row.get("codebase_version"))
    if row.get("error"):
        row.update(format_ok=False, real_robot=False, enough_episodes=False, robot_ok=False, joints_ok=False,
                   fps_ok=False, cameras_ok=False, license_ok=False)
    else:
        robot = (row.get("robot_type") or "").lower()
        row["format_ok"] = row.get("codebase_version") in READABLE_VERSIONS
        words = set(re.split(r"[^a-z0-9]+", (row["repo_id"] + " " + row.get("tags", "")).lower()))
        row["real_robot"] = not (words & set(SIM_WORDS))
        row["enough_episodes"] = (row.get("episodes") or 0) >= MIN_EPISODES
        row["robot_ok"] = any(r in robot for r in ("so100", "so101", "so_follower"))
        row["joints_ok"] = row.get("action_joints", "").split(";") == OUR_JOINTS and row.get("state_joints", "").split(";") == OUR_JOINTS
        row["fps_ok"] = row.get("fps") == OUR_FPS
        row["cameras_ok"] = row.get("cameras_640x480", 0) >= 2
        row["license_ok"] = row.get("license", "").startswith(ALLOWED_LICENSE_PREFIXES)
    names = {c.split(":")[0] for c in row.get("cameras", "").split(";") if c}
    row["camera_names_match"] = OUR_CAMERAS <= names
    row["needs_conversion"] = row.get("codebase_version") == "v2.1"
    row["compatible"] = all(row[k] for k in ("format_ok", "real_robot", "enough_episodes", "robot_ok", "joints_ok",
                                             "fps_ok", "cameras_ok", "license_ok"))
    row["relevant"] = any(w in row.get("tasks", "").lower() for w in RELEVANT_WORDS)
    return row


def list_candidates(limit: int | None) -> list[str]:
    from huggingface_hub import HfApi

    api = HfApi()
    ids = {}
    for tag in ("so100", "so101"):
        for d in api.list_datasets(filter=tag, full=False):
            if getattr(d, "private", False) or d.id.split("/")[0] == OUR_NAMESPACE:
                continue
            ids[d.id] = True
    out = sorted(ids)
    return out[:limit] if limit else out


def write_summary(rows: list[dict], path: Path, seconds: float | None) -> None:
    n = len(rows)
    fetched = [r for r in rows if not r.get("error")]
    funnel, remaining = [], fetched
    for key, label in (("format_ok", "LeRobot format v3.0, or v2.1 (convertible)"),
                       ("real_robot", "real robot, not simulation"), ("enough_episodes", f"at least {MIN_EPISODES} episodes"),
                       ("robot_ok", "SO-100/SO-101 robot type"),
                       ("joints_ok", "same 6 joints, same order"), ("fps_ok", "30 fps"),
                       ("cameras_ok", "at least two 640x480 cameras"), ("license_ok", "license allows reuse")):
        remaining = [r for r in remaining if r[key]]
        funnel.append((label, len(remaining)))
    compatible = [r for r in rows if r["compatible"]]
    relevant = [r for r in compatible if r["relevant"]]
    named = [r for r in relevant if r["camera_names_match"]]
    convert = [r for r in relevant if r["needs_conversion"]]
    errors = Counter((r.get("error") or "").split(":")[0] for r in rows if r.get("error"))
    versions = Counter(r.get("codebase_version") for r in fetched)
    licenses = Counter(r.get("license") or "(none)" for r in fetched)
    lines = [
        "# Public dataset catalog: summary (step 2)",
        "",
        "Built from metadata only (no videos downloaded) by `src/catalog.py`. Compatible datasets: `catalog_compatible.csv`; "
        "the table of every dataset is kept locally, not in the repo.",
        "",
        f"- Public datasets tagged `so100` or `so101` (excluding our own): {n}",
        f"- Metadata fetched: {len(fetched)}; failed: {n - len(fetched)} ({', '.join(f'{k} {v}' for k, v in errors.most_common()) or 'none'})",
        f"- Fetch time: {seconds / 60:.1f} minutes" if seconds is not None else "- Fetch time: not recorded",
        "- Failed fetches were not retried, by decision. Most (`HfHubHTTPError` without a status code) look like rate limiting.",
        "",
        "## Compatibility funnel",
        "",
        "Each line keeps only the datasets that also pass every check above it.",
        "",
        "| Check | Datasets remaining |",
        "|---|---|",
        f"| Metadata fetched | {len(fetched)} |",
        *[f"| {label} | {count} |" for label, count in funnel],
        "",
        f"**Compatible pool:** {len(compatible)} datasets, {sum(r.get('episodes') or 0 for r in compatible)} episodes.",
        f"Of those, **task-relevant** (task text mentions picking or placing into a container): {len(relevant)} datasets, {sum(r.get('episodes') or 0 for r in relevant)} episodes.",
        f"Of those, cameras already named `wrist` and `front`: {len(named)} (the rest need renaming to merge); "
        f"in format v2.1 and needing conversion: {len(convert)}.",
        "",
        "## What this means for step 3",
        "",
        *step3_notes(relevant),
        "",
        "## Format versions (fetched datasets, normalized)",
        "",
        *[f"- `{v}`: {c}" for v, c in versions.most_common()],
        "",
        "## Licenses (fetched datasets, top 10)",
        "",
        *[f"- `{lic}`: {c}" for lic, c in licenses.most_common(10)],
        "",
        "## Notes",
        "",
        "- Ray is used here for one engine across the pipeline; fetching small metadata files is I/O-bound and would also work with plain threads.",
        "- Joint units are not stated in the metadata; `action_min` and `action_max` per joint are recorded to compare with ours in a later step.",
    ]
    path.write_text("\n".join(lines) + "\n")


def step3_notes(relevant: list[dict]) -> list[str]:
    eps = sum(r.get("episodes") or 0 for r in relevant)
    camsets = Counter(";".join(sorted(c.split(":")[0] for c in r.get("cameras", "").split(";") if c)) for r in relevant)
    wrist = [r for r in relevant if any("wrist" in c.split(":")[0].lower() for c in r.get("cameras", "").split(";"))]
    keys = Counter((r.get("episodes"), r.get("frames")) for r in relevant)
    same_size = sum(1 for r in relevant if keys[(r.get("episodes"), r.get("frames"))] > 1)
    est_gb = eps * OUR_VIDEO_MB_PER_EPISODE / 1000
    fit = STAGE2_BUDGET_GB * 1000 // OUR_VIDEO_MB_PER_EPISODE
    return [
        f"- The task-relevant pool is {len(relevant)} datasets and {eps} episodes, against our 45.",
        f"- At our video size (about {OUR_VIDEO_MB_PER_EPISODE} MB per episode, two cameras), its videos would be about {est_gb:,.0f} GB. "
        f"The {STAGE2_BUDGET_GB} GB budget for step 3 fits about {fit:,} episodes at that size, so video is only fetched for a shortlist. "
        "LeRobot v3.0 also packs many episodes into each video file, so videos cannot be fetched one episode at a time.",
        f"- Datasets with a camera named like `wrist`: {len(wrist)} ({sum(r.get('episodes') or 0 for r in wrist)} episodes); "
        "these map clearly onto our `wrist` camera. Most common camera sets: "
        + ", ".join(f"`{k}` {v}" for k, v in camsets.most_common(6)) + ".",
        f"- Datasets that share their exact episode and frame counts with another relevant dataset: {same_size}. "
        "Many of these are likely copies or re-uploads, so near-duplicates are collapsed before scoring.",
        "- Joint trajectories (`data/*.parquet`) are small, so stage 1 of step 3 can score every relevant episode without video.",
    ]


def write_tables(rows: list[dict]) -> None:
    fields = ["repo_id", "compatible", "relevant", "camera_names_match", "needs_conversion", "format_ok", "real_robot",
              "enough_episodes", "robot_ok", "joints_ok", "fps_ok",
              "cameras_ok", "license_ok", "codebase_version", "robot_type", "fps", "episodes", "frames", "cameras",
              "cameras_640x480", "action_joints", "state_joints", "license", "downloads", "tags", "n_tasks", "tasks",
              "action_min", "action_max", "error"]
    for path, subset in ((RESULTS / "catalog_compatible.csv", [r for r in rows if r["compatible"]]), (FULL_TABLE, rows)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(subset)
        print(f"Wrote {path} ({len(subset)} rows)")


def load_saved() -> list[dict]:
    rows = [json.loads(line) for line in PARTIAL.read_text().splitlines() if line.strip()] if PARTIAL.exists() else []
    for r in rows:  # rows saved before the spelling change use the key "licence"
        if "licence" in r:
            r["license"] = r.pop("licence")
    return rows


def finish(rows: list[dict], seconds: float | None) -> None:
    rows = [add_flags(dict(r)) for r in rows]  # flags are recomputed, so changing a check needs no refetch
    rows.sort(key=lambda r: r["repo_id"])
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_tables(rows)
    write_summary(rows, RESULTS / "catalog_summary.md", seconds)
    print(f"Wrote {RESULTS / 'catalog_summary.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="catalog only the first N candidates (for a quick test)")
    parser.add_argument("--max-in-flight", type=int, default=32)
    parser.add_argument("--fresh", action="store_true", help=f"ignore rows saved in {PARTIAL} and start over")
    parser.add_argument("--rebuild", action="store_true", help=f"only rewrite the outputs from {PARTIAL}: no Hub listing, no fetches")
    args = parser.parse_args()

    if args.rebuild:
        rows = load_saved()
        if not rows:
            raise SystemExit(f"--rebuild needs saved rows in {PARTIAL}.")
        seconds = json.loads(RUN_INFO.read_text()).get("fetch_seconds") if RUN_INFO.exists() else None
        print(f"Rebuilding from {len(rows)} saved rows")
        finish(rows, seconds)
        return

    start = time.time()
    candidates = list_candidates(args.limit)
    print(f"{len(candidates)} candidate datasets")

    rows = []
    PARTIAL.parent.mkdir(parents=True, exist_ok=True)
    if PARTIAL.exists() and not args.fresh:
        wanted = set(candidates)
        rows = [r for r in load_saved() if r["repo_id"] in wanted]
        print(f"Resuming: {len(rows)} datasets already done ({PARTIAL})")
    elif PARTIAL.exists():
        PARTIAL.unlink()
    done_ids = {r["repo_id"] for r in rows}
    todo = [c for c in candidates if c not in done_ids]

    ray.init(num_cpus=4, include_dashboard=True, dashboard_host="127.0.0.1")
    pending = []
    try:
        while todo or pending:
            while todo and len(pending) < args.max_in_flight:
                pending.append(fetch.remote(todo.pop()))
            done, pending = ray.wait(pending, num_returns=1)
            raw = ray.get(done[0])
            with PARTIAL.open("a") as f:
                f.write(json.dumps(raw) + "\n")
            rows.append(raw)
            if len(rows) % 200 == 0:
                print(f"  {len(rows)}/{len(candidates)} done")
    finally:
        ray.shutdown()

    seconds = time.time() - start
    RUN_INFO.write_text(json.dumps({"fetch_seconds": seconds, "datasets": len(rows)}))
    finish(rows, seconds)


if __name__ == "__main__":
    main()
