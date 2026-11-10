"""Step 4, part 3: how well 3a's and 3b's scores agree with the manual labels.

Runs on the Mac. Reads outputs/p03_review/sample.json (clip -> episode) and labels.csv (exported
from the labeling page), and the scores, and reports:
  - self-consistency: how often the repeated clips got the same label,
  - on the random public part (the unbiased part): for each score, AUROC of the score against
    good/bad labels, in the "worse" direction fixed in configs/review.yaml, with a bootstrap 95% interval,
  - the same for each score against its matching reason tag,
  - on the extremes: how many were labeled bad, and how many with the matching reason.

Run from the repo root:
    uv run python projects/03-ray-curation/src/review_agreement.py
Outputs:
    projects/03-ray-curation/results/review_labels.csv     (committed: labels, tags, notes per episode)
    projects/03-ray-curation/results/review_agreement.md   (committed)
"""

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from review_sample import CONFIG, episode_table

RESULTS = Path("projects/03-ray-curation/results")


def auroc(worse: np.ndarray, positive: np.ndarray) -> float:
    """P(score of a positive > score of a negative), ties counting half (Mann-Whitney)."""
    pos, neg = worse[positive], worse[~positive]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    greater = (pos[:, None] > neg[None, :]).mean()
    ties = (pos[:, None] == neg[None, :]).mean()
    return float(greater + 0.5 * ties)


def auroc_ci(worse, positive, seed, reps=2000):
    rng = np.random.default_rng(seed)
    n, vals = len(worse), []
    for _ in range(reps):
        k = rng.integers(0, n, n)
        v = auroc(worse[k], positive[k])
        if not np.isnan(v):
            vals.append(v)
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if vals else (np.nan, np.nan)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    out = Path(cfg["review_dir"])

    sample = pd.DataFrame(json.loads((out / "sample.json").read_text()))
    labels = pd.read_csv(out / "labels.csv", dtype=str).fillna("")
    df = sample.merge(labels, on="clip", how="left")
    df["label"] = df["label"].fillna("")
    df["tags"] = df["tags"].fillna("")
    scores = episode_table(cfg)
    names = list(cfg["criteria"])
    df = df.merge(scores[["repo_id", "episode_index"] + names], on=["repo_id", "episode_index"], how="left")

    keep = ["clip", "part", "criterion", "repeat_of", "repo_id", "episode_index", "label", "tags", "note"]
    df[[c for c in keep if c in df]].sort_values(["part", "repo_id", "episode_index"]).to_csv(
        RESULTS / "review_labels.csv", index=False)

    labeled = df[df.label != ""]
    lines = [
        "# Manual review: agreement between the scores and the labels (step 4)",
        "",
        "Labels from one reviewer, blind to dataset names and scores, on clips re-encoded in the isolated container. "
        "Built by `src/review_agreement.py` with `configs/review.yaml`; labels in `review_labels.csv`.",
        "",
        f"- Code: git commit `{subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()}`",
        f"- Clips: {len(df)}; labeled {len(labeled)}. By part: "
        + ", ".join(f"{p} {len(g)} (good {sum(g.label == 'good')}, bad {sum(g.label == 'bad')}, unsure {sum(g.label == 'unsure')})"
                    for p, g in labeled.groupby("part")),
    ]

    # Self-consistency on repeats.
    rep = labeled[labeled.part == "repeat"]
    first = labeled.set_index("clip")["label"]
    same = [first.get(r.repeat_of, "") == r.label for r in rep.itertuples()]
    lines.append(f"- Self-consistency: {sum(same)}/{len(same)} repeated clips got the same label as the first time")

    # Random public part: AUROC per score.
    rnd = labeled[(labeled.part == "random") & labeled.label.isin(["good", "bad"])]
    n_bad, n_good = int((rnd.label == "bad").sum()), int((rnd.label == "good").sum())
    lines += [
        "",
        f"## Random public episodes: does each score separate bad from good? (n = {len(rnd)}: {n_bad} bad, {n_good} good)",
        "",
        "AUROC: the chance that a randomly chosen bad episode scores worse than a randomly chosen good one. "
        "0.5 is chance, 1.0 is perfect. Brackets: bootstrap 95% interval. Unsure labels are left out.",
        "",
        "| Score | Worse is | AUROC, bad vs good | AUROC, matching reason tag | Tag |",
        "|---|---|---|---|---|",
    ]
    rnd_all = labeled[labeled.part == "random"]
    for name in names:
        c = cfg["criteria"][name]
        sign = 1 if c["worse"] == "high" else -1
        w = sign * rnd[name].to_numpy(dtype=float)
        a = auroc(w, (rnd.label == "bad").to_numpy())
        lo, hi = auroc_ci(w, (rnd.label == "bad").to_numpy(), cfg["seed"]) if min(n_bad, n_good) >= 3 else (np.nan, np.nan)
        has_tag = rnd_all.tags.str.contains(c["tag"], regex=False).to_numpy()
        wt = sign * rnd_all[name].to_numpy(dtype=float)
        at = auroc(wt, has_tag)
        ab = f"{a:.2f} [{lo:.2f} to {hi:.2f}]" if not np.isnan(lo) else (f"{a:.2f} (too few to bound)" if not np.isnan(a) else "-")
        tag_text = f"{at:.2f} ({int(has_tag.sum())} tagged)" if not np.isnan(at) else f"- ({int(has_tag.sum())} tagged)"
        lines.append(f"| `{name}` | {c['worse']} | {ab} | {tag_text} | {c['tag']} |")

    # Extremes.
    ext = labeled[labeled.part == "extreme"]
    lines += [
        "",
        "## Extremes: the worst episodes for each score",
        "",
        "| Score | Labeled bad | With the matching reason |",
        "|---|---|---|",
    ]
    for name in names:
        g = ext[ext.criterion == name]
        tag = cfg["criteria"][name]["tag"]
        lines.append(f"| `{name}` | {int((g.label == 'bad').sum())}/{len(g)} | "
                     f"{int(g.tags.str.contains(tag, regex=False).sum())}/{len(g)} ({tag}) |")

    ours = labeled[labeled.part == "ours"]
    lines += [
        "",
        "## Ours",
        "",
        f"- {len(ours)} of our episodes: good {int((ours.label == 'good').sum())}, bad {int((ours.label == 'bad').sum())}, "
        f"unsure {int((ours.label == 'unsure').sum())}",
        "",
        "## Notes",
        "",
        "- The worse direction of each score was fixed in `configs/review.yaml` before labeling.",
        "- One reviewer; the repeats are the only measure of label noise. With this few random episodes the intervals are wide; "
        "a score whose interval includes 0.5 has not been shown to agree with the labels.",
        "- The extremes are taken from the worse end only, so they show whether a score's worst cases are real problems, not how "
        "well it separates typical episodes.",
        "- Clips are 10 fps and 240 pixels high; fine blur may not be visible at that size.",
    ]
    (RESULTS / "review_agreement.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {RESULTS / 'review_labels.csv'} and {RESULTS / 'review_agreement.md'}")


if __name__ == "__main__":
    main()
