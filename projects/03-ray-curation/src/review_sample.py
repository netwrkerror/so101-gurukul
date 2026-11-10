"""Step 4, part 1: choose the episodes for the manual review and set up the labeling page.

Runs on the Mac and decodes nothing. Combines 3a's joint scores and 3b's video scores into one
row per episode, then draws (with a fixed seed):
  - random public episodes from the shortlisted datasets (the unbiased part),
  - extremes: the worst few episodes for each criterion in configs/review.yaml,
  - a few of ours,
  - repeats of some clips, shown again among the later clips, to measure self-consistency.

Run from the repo root (does not touch the arm):
    uv run python projects/03-ray-curation/src/review_sample.py
Outputs (local only; the clips show other people's rooms):
    outputs/p03_review/sample.json    clip id -> dataset and episode (not read by the page, so labeling stays blind)
    outputs/p03_review/manifest.js    clip order and file names only
    outputs/p03_review/label.html     copy of review/label.html
Then make the clips in the container (score_video.py clips) and open label.html.
"""

import argparse
import json
import random
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

CONFIG = Path("projects/03-ray-curation/configs/review.yaml")
PAGE = Path("projects/03-ray-curation/review/label.html")


def episode_table(cfg: dict) -> pd.DataFrame:
    """One row per episode of the shortlisted datasets and ours, with 3a's and 3b's scores."""
    chosen = pd.read_csv(cfg["shortlist"])
    keep = set(chosen.loc[chosen.status == "chosen", "repo_id"]) - set(cfg["exclude"]) | {cfg["ours"]}

    traj = pd.read_parquet(cfg["episode_scores"])
    traj = traj[traj.repo_id.isin(keep) & traj["error"].isna()]

    vid = pd.read_parquet(cfg["video_scores"])
    vid = vid[vid.repo_id.isin(keep)]
    public = vid[vid.repo_id != cfg["ours"]]
    role_median = public.groupby("role")["sharpness"].median()
    vid = vid.assign(sharp_rel=vid["sharpness"] / vid["role"].map(role_median),
                     bright_dev=(vid["brightness"] - 128).abs())
    per_ep = vid.groupby(["repo_id", "episode_index"]).agg(
        sharpness_min=("sharp_rel", "min"), brightness_deviation=("bright_dev", "max"),
        frozen_max=("frozen_fraction", "max"), cameras=("camera", "nunique")).reset_index()

    df = traj.merge(per_ep, on=["repo_id", "episode_index"], how="inner")
    df["gripper_deviation"] = (df["gripper_open_events"] - 2).abs()
    median_len = df.loc[df.repo_id != cfg["ours"], "length_s"].median()
    df["length_deviation"] = np.log(df["length_s"] / median_len).abs()
    return df


def draw(df: pd.DataFrame, cfg: dict) -> list[dict]:
    s, rng = cfg["sample"], random.Random(cfg["seed"])
    ours, public = df[df.repo_id == cfg["ours"]], df[df.repo_id != cfg["ours"]]
    # Shuffle once with the seed, so ties at the extremes (for example many episodes with 0 gripper
    # openings) are broken at random rather than by dataset name.
    public = public.sample(frac=1, random_state=cfg["seed"])
    picked, rows = set(), []

    def add(r, part, criterion=None):
        key = (r.repo_id, int(r.episode_index))
        if key in picked:
            return False
        picked.add(key)
        rows.append({"repo_id": r.repo_id, "episode_index": int(r.episode_index), "part": part, "criterion": criterion})
        return True

    # Extremes first, so the random part is drawn from what remains (no overlap between parts).
    for name, c in cfg["criteria"].items():
        ordered = public.sort_values(name, ascending=(c["worse"] == "low"), kind="mergesort")
        n = 0
        for r in ordered.itertuples():
            if n == s["extremes_per_criterion"]:
                break
            n += add(r, "extreme", name)
    rest = public[[(r, int(e)) not in picked for r, e in zip(public.repo_id, public.episode_index)]]
    for i in rng.sample(range(len(rest)), s["random_public"]):
        add(rest.iloc[i], "random")
    for i in rng.sample(range(len(ours)), s["ours"]):
        add(ours.iloc[i], "ours")

    rng.shuffle(rows)
    for r in rows:
        r["clip"] = f"{rng.getrandbits(48):012x}"
    # Repeats: copies of clips from the first half, inserted at random places in the second half.
    half = len(rows) // 2
    for src in rng.sample(rows[:half], s["repeats"]):
        rep = dict(src, part="repeat", repeat_of=src["clip"], clip=f"{rng.getrandbits(48):012x}")
        rows.insert(rng.randint(half + 1, len(rows)), rep)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())

    df = episode_table(cfg)
    rows = draw(df, cfg)
    out = Path(cfg["review_dir"])
    (out / "clips").mkdir(parents=True, exist_ok=True)
    (out / "sample.json").write_text(json.dumps(rows, indent=1))
    # The page sees only clip ids and file names; repeats point at their original's file.
    manifest = [{"clip": r["clip"], "file": f"clips/{r.get('repeat_of', r['clip'])}.mp4"} for r in rows]
    (out / "manifest.js").write_text("window.REVIEW_CLIPS = " + json.dumps(manifest) + ";\n")
    shutil.copy(PAGE, out / "label.html")

    parts = pd.Series([r["part"] for r in rows]).value_counts().to_dict()
    print(f"Episodes available: {len(df)} ({df.repo_id.nunique()} datasets)")
    print(f"Clips to label: {len(rows)} {parts}; unique episodes to render: {len(rows) - parts.get('repeat', 0)}")
    print(f"Wrote {out / 'sample.json'}, {out / 'manifest.js'}, {out / 'label.html'}")


if __name__ == "__main__":
    main()
