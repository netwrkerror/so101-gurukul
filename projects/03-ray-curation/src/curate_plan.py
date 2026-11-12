"""Step 5a, part 1: choose the public episodes for S2 (curated) and S3 (random control).

Runs on the Mac and decodes nothing. Starting from the shortlisted datasets (step 3b):
  - drop the excluded datasets and those whose joint units cannot be matched to ours,
  - map cameras: the wrist camera to `wrist`, the fixed camera that looks most like our front view
    (lowest median distance to our scene, step 3b) to `front`; other cameras are dropped,
  - drop exact copies (one episode per fingerprint),
  - S3: a seeded random draw from that pool (only the requirements for merging applied),
  - S2: the same pool, filtered by the scores the step 4 review supported (idle fraction and length
    extremes) and by task match (two gripper openings), then ranked by similarity to our scene, with
    a cap per dataset.

Run from the repo root (does not touch the arm):
    uv run python projects/03-ray-curation/src/curate_plan.py
Outputs:
    projects/03-ray-curation/results/s2_episodes.csv, s3_episodes.csv   (committed: the episode lists)
    projects/03-ray-curation/results/curation_plan.md                    (committed: the funnel and the makeup)
    outputs/p03_sets/plan.json                                           (local: read by the builder in the container)
"""

import argparse
import csv
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

CONFIG = Path("projects/03-ray-curation/configs/curation.yaml")
RESULTS = Path("projects/03-ray-curation/results")


def load(cfg: dict):
    s = pd.read_csv(cfg["shortlist"])
    chosen = sorted(set(s.loc[s.status == "chosen", "repo_id"]) - set(cfg["exclude"]))
    with open(cfg["catalog"]) as f:
        cat = {r["repo_id"]: r for r in csv.DictReader(f)}
    per = pd.read_csv(cfg["dataset_scores"]).set_index("repo_id")
    eps = pd.read_parquet(cfg["episode_scores"])
    vid = pd.read_parquet(cfg["video_scores"], columns=["repo_id", "episode_index", "camera", "role", "dist_to_ours"])
    return chosen, cat, per, eps, vid


def units_ok(row, min_abs: float) -> bool:
    lo = [float(v) for v in row["action_low"].split(";")]
    hi = [float(v) for v in row["action_high"].split(";")]
    return max(abs(v) for v in lo[:5] + hi[:5]) > min_abs


def camera_map(repo_id: str, cat: dict, vid: pd.DataFrame) -> dict | None:
    cams = [c.split(":")[0] for c in cat[repo_id]["cameras"].split(";") if c]
    wrist = sorted(c for c in cams if "wrist" in c.lower())
    fixed = [c for c in cams if c not in wrist]
    if not wrist or not fixed:
        return None
    d = vid[(vid.repo_id == repo_id) & vid.camera.isin(fixed)].groupby("camera")["dist_to_ours"].median()
    front = d.idxmin() if len(d) else sorted(fixed)[0]
    return {"wrist": wrist[0], "front": front, "drop": sorted(set(cams) - {wrist[0], front})}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    chosen, cat, per, eps, vid = load(cfg)

    funnel = [("Shortlisted datasets (step 3b), minus the 2 excluded", len(chosen), None)]
    unit_ok = [r for r in chosen if units_ok(per.loc[r], cfg["units_min_body_abs"])]
    funnel.append((f"Joint units match ours (a body joint beyond +-{cfg['units_min_body_abs']})", len(unit_ok), None))
    maps = {r: camera_map(r, cat, vid) for r in unit_ok}
    usable = [r for r in unit_ok if maps[r]]
    funnel.append(("A wrist camera and a fixed camera", len(usable), None))

    pool = eps[eps.repo_id.isin(usable) & eps["error"].isna()].copy()
    front_dist = vid.merge(pd.DataFrame([(r, m["front"]) for r, m in maps.items() if m], columns=["repo_id", "camera"]))
    pool = pool.merge(front_dist[["repo_id", "episode_index", "dist_to_ours"]], on=["repo_id", "episode_index"], how="inner")
    funnel.append(("Episodes scored in 3a and 3b", pool.repo_id.nunique(), len(pool)))
    pool = pool.sort_values(["repo_id", "episode_index"]).drop_duplicates("fingerprint", keep="first")
    funnel.append(("After dropping exact copies (one per fingerprint)", pool.repo_id.nunique(), len(pool)))

    # One seeded order over the whole pool, drawn before build exclusions are applied, so excluding a
    # dataset later only replaces its episodes instead of redrawing all of S3.
    rng = np.random.default_rng(cfg["seed"])
    n = cfg["n_public"]
    order = pool.iloc[rng.permutation(len(pool))]
    bad = set(cfg.get("exclude_build", {}))
    s3 = order[~order.repo_id.isin(bad)].head(n).assign(reason="random draw (seeded order)")
    pool = pool[~pool.repo_id.isin(bad)]
    funnel.append(("After excluding datasets LeRobot could not build (exclude_build)", pool.repo_id.nunique(), len(pool)))

    f = cfg["s2_filters"]
    median_len = pool.length_s.median()
    pool["length_deviation"] = np.log(pool.length_s / median_len).abs()
    idle_max = pool.idle_fraction.quantile(f["idle_fraction_quantile"])
    len_max = pool.length_deviation.quantile(f["length_deviation_quantile"])
    s2_pool = pool[pool.idle_fraction <= idle_max]
    funnel.append((f"S2: idle fraction at most {idle_max:.3f} (pool's {f['idle_fraction_quantile']:.0%} quantile)",
                   s2_pool.repo_id.nunique(), len(s2_pool)))
    s2_pool = s2_pool[s2_pool.length_deviation <= len_max]
    funnel.append((f"S2: length within a factor of {np.exp(len_max):.2f} of the median {median_len:.1f} s",
                   s2_pool.repo_id.nunique(), len(s2_pool)))
    s2_pool = s2_pool[s2_pool.gripper_open_events == f["gripper_open_events"]]
    funnel.append((f"S2: exactly {f['gripper_open_events']} gripper openings (a single pick and place)",
                   s2_pool.repo_id.nunique(), len(s2_pool)))
    ranked = s2_pool.sort_values(["dist_to_ours", "repo_id", "episode_index"])
    ranked = ranked[ranked.groupby("repo_id").cumcount() < cfg["max_per_dataset_s2"]]
    s2 = ranked.head(n).assign(reason="passed filters; ranked by similarity to our scene")
    if len(s2) < n:
        raise SystemExit(f"Only {len(s2)} episodes pass S2's filters; {n} needed.")

    cols = ["repo_id", "episode_index", "revision", "codebase_version", "wrist_camera", "front_camera",
            "dropped_cameras", "length_s", "idle_fraction", "gripper_open_events", "dist_to_ours", "reason"]
    for name, df in (("s2", s2), ("s3", s3)):
        df = df.assign(revision=df.repo_id.map(per["revision"]), codebase_version=df.repo_id.map(per["codebase_version"]),
                       wrist_camera=df.repo_id.map(lambda r: maps[r]["wrist"]), front_camera=df.repo_id.map(lambda r: maps[r]["front"]),
                       dropped_cameras=df.repo_id.map(lambda r: ";".join(maps[r]["drop"])))
        df.sort_values(["repo_id", "episode_index"])[cols].to_csv(RESULTS / f"{name}_episodes.csv", index=False, float_format="%.4f")

    plan = {"ours": cfg["ours"], "video": cfg["build"]["video"], "sets": {}}
    for name, df in (("s2", s2), ("s3", s3)):
        plan["sets"][name] = {"repo_id": cfg["build"]["sets"][name], "sources": [
            {"repo_id": r, "revision": per.loc[r, "revision"], "codebase_version": per.loc[r, "codebase_version"],
             "episodes": sorted(int(e) for e in g.episode_index), **maps[r]} for r, g in df.groupby("repo_id")]}
    out = Path(cfg["build"]["plan"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=1))

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    overlap = len(set(zip(s2.repo_id, s2.episode_index)) & set(zip(s3.repo_id, s3.episode_index)))
    lines = [
        "# S2 and S3: episode selection (step 5a)",
        "",
        f"Built by `src/curate_plan.py` with `configs/curation.yaml` (git commit `{commit}`). Episode lists: "
        "`s2_episodes.csv`, `s3_episodes.csv`. Both sets are our 45 episodes plus the public episodes below.",
        "",
        "| Step | Datasets | Episodes |",
        "|---|---|---|",
        *[f"| {label} | {d} | {'' if e is None else e} |" for label, d, e in funnel],
        "",
        f"- **S3 (random control):** {len(s3)} episodes from {s3.repo_id.nunique()} datasets, drawn with seed {cfg['seed']} "
        "from the pool after copies were dropped. No quality or relevance filter.",
        f"- **S2 (curated):** {len(s2)} episodes from {s2.repo_id.nunique()} datasets, at most {cfg['max_per_dataset_s2']} per dataset, "
        "closest to our scene first.",
        f"- Episodes in both sets: {overlap}.",
        f"- Median length: S2 {s2.length_s.median():.1f} s, S3 {s3.length_s.median():.1f} s. "
        f"Median distance to our scene (front camera): S2 {s2.dist_to_ours.median():.3f}, S3 {s3.dist_to_ours.median():.3f}.",
        f"- Gripper openings in S3: " + ", ".join(f"{int(k)}: {v}" for k, v in s3.gripper_open_events.value_counts().sort_index().items()),
        "",
        "## Notes",
        "",
        "- Joint units: datasets whose body joints all stay within +-100 may use the older -100 to 100 scale; they are excluded, "
        "not converted. Calibration still differs from arm to arm (the brief's risk); this is not corrected.",
        "- Camera mapping: the wrist camera becomes `wrist`; the fixed camera with the lowest median distance to our scene "
        "becomes `front`; others are dropped. Every public episode is re-encoded to our video settings when the sets are built.",
    ]
    (RESULTS / "curation_plan.md").write_text("\n".join(lines) + "\n")
    for label, d, e in funnel:
        print(f"{label}: {d} datasets" + ("" if e is None else f", {e} episodes"))
    print(f"S2: {len(s2)} episodes from {s2.repo_id.nunique()} datasets; S3: {len(s3)} from {s3.repo_id.nunique()}; overlap {overlap}")
    print(f"Wrote {RESULTS / 's2_episodes.csv'}, {RESULTS / 's3_episodes.csv'}, {RESULTS / 'curation_plan.md'}, {out}")


if __name__ == "__main__":
    main()
