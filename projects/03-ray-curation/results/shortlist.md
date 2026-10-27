# Shortlist of whole datasets for video scores (step 3b)

Built by `src/shortlist.py` with `configs/scoring_stage2.yaml`, from 3a's scores. Full list with reasons: `shortlist.csv`.

- Code: git commit `cfb4dfb`
- Eligible: a wrist camera plus a fixed camera; at most 20% of episodes copied from other datasets; at least 10 copy-free episodes.
- At most 300 episodes per dataset, so no single dataset takes much of the budget.
- Ranked by the share of copy-free episodes that are plausible (at least one gripper opening, 3 to 60 s long), in bins of 0.05; ties in a random order with seed 1000.
- Chosen: **75 datasets, 4980 copy-free episodes (4987 in all), 50.0 GB** (budget 50 GB)
- Status counts: skipped 647, not chosen 82, chosen 75
- Reasons: no wrist camera plus a fixed camera 473, more than 20% of episodes are copies 101, over the download budget 82, policy rollouts, not demonstrations (name) 35, a file is larger than 200 MB 33, more than 300 episodes (one dataset would take too much of the budget) 4, fewer than 10 copy-free episodes 1
- Downloaded; 16.2 min

## Notes

- Ranking by 3a's scores is itself a light curation. S3 (the random control) draws from these same datasets, so S2 against S3 measures the choice of episodes within them, not the choice of datasets.
- Videos are kept in `outputs/p03_video/` until step 5 builds S2 and S3, then deleted.
