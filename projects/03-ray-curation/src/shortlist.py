"""Step 3b, part 1: choose a shortlist of whole public datasets and download their videos.

Runs on the Mac. Nothing here decodes video: files are only written to disk, and decoding
happens in the container (src/score_video.py). Datasets are ranked from 3a's joint-data
scores; whole datasets are taken in that order until the download budget is used, because
LeRobot 0.6.0 can only merge whole datasets (step 5 picks episodes by deleting the rest).

Run from the repo root (does not touch the arm):
    uv run python projects/03-ray-curation/src/shortlist.py --plan   # choose and size; download nothing
    uv run python projects/03-ray-curation/src/shortlist.py          # choose, then download
Outputs:
    projects/03-ray-curation/results/shortlist.csv   (chosen and skipped datasets, with reasons; committed)
    projects/03-ray-curation/results/shortlist.md    (summary; committed)
    outputs/p03_video/<owner>__<name>/               (meta/ and videos/ at the pinned revision; local)
"""

import argparse
import csv
import json
import os
import re
import time
from pathlib import Path

# Must be set before Ray is imported (see src/ray_check.py and DECISIONS.md, 2026-10-25).
os.environ["RAY_USAGE_STATS_ENABLED"] = "0"
os.environ["RAY_ENABLE_UV_RUN_RUNTIME_ENV"] = "0"

import ray  # noqa: E402
import yaml  # noqa: E402

CONFIG = Path("projects/03-ray-curation/configs/scoring_stage2.yaml")
RESULTS = Path("projects/03-ray-curation/results")


def local_name(repo_id: str) -> str:
    return repo_id.replace("/", "__")


def with_retries(fn):
    """Retry rate limiting and server errors (same rule as src/score_trajectories.py)."""
    from huggingface_hub.errors import HfHubHTTPError

    for attempt in range(5):
        try:
            return fn()
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            transient = (isinstance(e, HfHubHTTPError) and status in (429, 500, 502, 503, 504, None)) or "429" in str(e)
            if transient and attempt < 4:
                time.sleep(2 ** (attempt + 2))
                continue
            raise


def rank_candidates(cfg: dict) -> tuple[list[dict], list[dict]]:
    """Datasets eligible for the shortlist, best first, and the ones ruled out with a reason."""
    import pandas as pd

    s = cfg["shortlist"]
    with open(s["catalog"]) as f:
        cat = {r["repo_id"]: r for r in csv.DictReader(f)}
    per = pd.read_csv(s["dataset_scores"])
    eps = pd.read_parquet(s["episode_scores"])
    eps = eps[eps["error"].isna()]
    lo, hi = s["plausible_length_s"]
    eps["plausible"] = (eps["gripper_open_events"] >= 1) & eps["length_s"].between(lo, hi)
    plausible = eps[~eps["copy_elsewhere"]].groupby("repo_id")["plausible"].mean()

    chosen, ruled_out = [], []
    for _, r in per.iterrows():
        rid = r["repo_id"]
        if rid == cfg["ours"]["repo_id"]:
            continue
        cams = [c.split(":")[0] for c in cat.get(rid, {}).get("cameras", "").split(";") if c]
        unique = int(r["episodes_scored"] - r["episodes_copied_elsewhere"])
        copy_fraction = r["episodes_copied_elsewhere"] / max(r["episodes_scored"], 1)
        row = {"repo_id": rid, "revision": r["revision"], "codebase_version": r["codebase_version"],
               "cameras": ";".join(cams), "episodes": int(r["episodes_scored"]), "unique_episodes": unique,
               "copy_fraction": round(copy_fraction, 3), "plausible_fraction": round(float(plausible.get(rid, 0.0)), 3)}
        wrist = [c for c in cams if "wrist" in c.lower()]
        words = set(re.split(r"[^a-z0-9]+", rid.split("/")[-1].lower()))
        if words & set(s["rollout_words"]):
            ruled_out.append(row | {"status": "skipped", "reason": "policy rollouts, not demonstrations (name)"})
        elif not wrist or len(cams) - len(wrist) < 1:
            ruled_out.append(row | {"status": "skipped", "reason": "no wrist camera plus a fixed camera"})
        elif copy_fraction > s["max_copy_fraction"]:
            ruled_out.append(row | {"status": "skipped", "reason": f"more than {s['max_copy_fraction']:.0%} of episodes are copies"})
        elif unique < s["min_episodes"]:
            ruled_out.append(row | {"status": "skipped", "reason": f"fewer than {s['min_episodes']} copy-free episodes"})
        elif row["episodes"] > s["max_episodes"]:
            ruled_out.append(row | {"status": "skipped", "reason": f"more than {s['max_episodes']} episodes (one dataset would take too much of the budget)"})
        else:
            chosen.append(row)
    # Most datasets tie on the plausible fraction, so ties are broken in a seeded random order: a size
    # tie-break would spend the budget on a few large datasets (few scenes).
    import random

    rng = random.Random(s["seed"])
    order = {r["repo_id"]: rng.random() for r in sorted(chosen, key=lambda r: r["repo_id"])}
    step = s["plausible_bin"]
    chosen.sort(key=lambda r: (-round(r["plausible_fraction"] / step) * step, order[r["repo_id"]]))
    for i, r in enumerate(chosen, 1):
        r["rank"] = i
    return chosen, ruled_out


@ray.remote(num_cpus=0.05)
def size_of(row: dict, cfg: dict) -> dict:
    """Size of a dataset's meta/ and videos/ at its pinned revision. Never raises."""
    try:
        from huggingface_hub import HfApi

        info = with_retries(lambda: HfApi().dataset_info(row["repo_id"], revision=row["revision"], files_metadata=True))
        files = [s for s in info.siblings if s.rfilename.startswith(("meta/", "videos/"))]
        videos = [s for s in files if s.rfilename.startswith("videos/")]
        return row | {"bytes": sum(s.size or 0 for s in files), "video_files": len(videos),
                      "largest_file_mb": round(max((s.size or 0 for s in files), default=0) / 1e6, 1)}
    except Exception as e:
        return row | {"error": f"{type(e).__name__}: {str(e).splitlines()[0][:120] if str(e) else ''}"}


@ray.remote(num_cpus=0.05)
def download(row: dict, cfg: dict) -> dict:
    """Download meta/ and videos/ at the pinned revision. Never raises; finished datasets are skipped."""
    dest = Path(cfg["shortlist"]["download_dir"]) / local_name(row["repo_id"])
    manifest = dest / "manifest.json"
    if manifest.exists() and json.loads(manifest.read_text()).get("complete"):
        return row | {"cached": True}
    try:
        from huggingface_hub import snapshot_download

        with_retries(lambda: snapshot_download(row["repo_id"], repo_type="dataset", revision=row["revision"],
                                               local_dir=dest, allow_patterns=["meta/*", "videos/*"]))
        manifest.write_text(json.dumps({k: row[k] for k in ("repo_id", "revision", "rank")} | {"complete": True}))
        return row
    except Exception as e:
        return row | {"error": f"{type(e).__name__}: {str(e).splitlines()[0][:120] if str(e) else ''}"}


def run(tasks, cfg) -> list[dict]:
    """Run (remote_fn, row) pairs with a cap on requests in flight."""
    pending, done, queue = [], [], list(tasks)
    while queue or pending:
        while queue and len(pending) < cfg["shortlist"]["max_in_flight"]:
            fn, row = queue.pop(0)
            pending.append(fn.remote(row, cfg))
        ready, pending = ray.wait(pending, num_returns=1)
        done.append(ray.get(ready[0]))
        if len(done) % 25 == 0 or not (queue or pending):
            print(f"{len(done)}/{len(tasks)}", flush=True)
    return done


def choose(sized: list[dict], cfg: dict) -> list[dict]:
    """Take datasets in rank order while they fit the budget; mark the rest."""
    s = cfg["shortlist"]
    budget, used = s["budget_gb"] * 1e9, 0
    for r in sorted(sized, key=lambda r: r["rank"]):
        if r.get("error"):
            r |= {"status": "skipped", "reason": "size lookup failed"}
        elif r["largest_file_mb"] > s["file_mb"]:
            r |= {"status": "skipped", "reason": f"a file is larger than {s['file_mb']} MB"}
        elif used + r["bytes"] > budget:
            r |= {"status": "not chosen", "reason": "over the download budget"}
        else:
            used += r["bytes"]
            r |= {"status": "chosen", "reason": "within budget, in rank order"}
    return sized


def write_outputs(rows: list[dict], cfg: dict, seconds: float, downloaded: bool) -> None:
    import subprocess
    from collections import Counter

    fields = ["repo_id", "status", "reason", "rank", "plausible_fraction", "unique_episodes", "episodes", "copy_fraction",
              "cameras", "codebase_version", "bytes", "video_files", "largest_file_mb", "revision", "error"]
    rows = sorted(rows, key=lambda r: (r.get("rank") or 10 ** 6, r["repo_id"]))
    with (RESULTS / "shortlist.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain", "projects/03-ray-curation/src", "projects/03-ray-curation/configs"],
                      capture_output=True, text=True).stdout.strip():
        commit += " plus uncommitted changes to the code or config"
    chosen = [r for r in rows if r["status"] == "chosen"]
    s = cfg["shortlist"]
    lines = [
        "# Shortlist of whole datasets for video scores (step 3b)",
        "",
        "Built by `src/shortlist.py` with `configs/scoring_stage2.yaml`, from 3a's scores. Full list with reasons: `shortlist.csv`.",
        "",
        f"- Code: git commit `{commit}`",
        f"- Eligible: a wrist camera plus a fixed camera; at most {s['max_copy_fraction']:.0%} of episodes copied from other "
        f"datasets; at least {s['min_episodes']} copy-free episodes.",
        f"- At most {s['max_episodes']} episodes per dataset, so no single dataset takes much of the budget.",
        "- Ranked by the share of copy-free episodes that are plausible (at least one gripper opening, "
        f"{s['plausible_length_s'][0]} to {s['plausible_length_s'][1]} s long), in bins of {s['plausible_bin']}; "
        f"ties in a random order with seed {s['seed']}.",
        f"- Chosen: **{len(chosen)} datasets, {sum(r['unique_episodes'] for r in chosen)} copy-free episodes "
        f"({sum(r['episodes'] for r in chosen)} in all), {sum(r['bytes'] for r in chosen) / 1e9:.1f} GB** "
        f"(budget {s['budget_gb']} GB)",
        f"- Status counts: " + ", ".join(f"{k} {v}" for k, v in Counter(r["status"] for r in rows).most_common()),
        "- Reasons: " + ", ".join(f"{k} {v}" for k, v in Counter(r["reason"] for r in rows if r["status"] != "chosen").most_common()),
        f"- {'Downloaded' if downloaded else 'Planned only (nothing downloaded)'}; {seconds / 60:.1f} min",
        "",
        "## Notes",
        "",
        "- Ranking by 3a's scores is itself a light curation. S3 (the random control) draws from these same datasets, so "
        "S2 against S3 measures the choice of episodes within them, not the choice of datasets.",
        "- Videos are kept in `outputs/p03_video/` until step 5 builds S2 and S3, then deleted.",
    ]
    (RESULTS / "shortlist.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {RESULTS / 'shortlist.csv'} and {RESULTS / 'shortlist.md'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--plan", action="store_true", help="choose and size only; download nothing")
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())

    eligible, ruled_out = rank_candidates(cfg)
    print(f"Eligible datasets: {len(eligible)}; ruled out: {len(ruled_out)}")
    ray.init(num_cpus=4, include_dashboard=True, dashboard_host="127.0.0.1")
    print(f"Ray {ray.__version__} started. Dashboard: http://127.0.0.1:8265")
    t0 = time.time()
    try:
        rows = choose(run([(size_of, r) for r in eligible], cfg), cfg)
        chosen = [r for r in rows if r["status"] == "chosen"]
        print(f"Chosen: {len(chosen)} datasets, {sum(r['bytes'] for r in chosen) / 1e9:.1f} GB")
        if not args.plan:
            results = {r["repo_id"]: r for r in run([(download, r) for r in chosen], cfg)}
            for r in rows:
                if r["repo_id"] in results and results[r["repo_id"]].get("error"):
                    r |= {"status": "skipped", "reason": "download failed", "error": results[r["repo_id"]]["error"]}
    finally:
        ray.shutdown()
    write_outputs(rows + ruled_out, cfg, time.time() - t0, downloaded=not args.plan)


if __name__ == "__main__":
    main()
