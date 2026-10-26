# Episode scores from joint data: summary (step 3, stage 1)

Built by `src/score_trajectories.py` with `configs/scoring_stage1.yaml`. No video was downloaded.

- Code: git commit `a3e2aa5`; run on the dev machine (local Ray, 4 CPUs)
- Datasets: ours plus 807 public; ready 804; failed 3
- Failures by type: cameras not stored as video (cannot merge with ours) 3
- Episodes scored: 77486 (ours 45, public 77441); failed or too short: 178
- Download: 0.7 min for 33 datasets, 0.03 GB (datasets already downloaded are not re-fetched)
- Scoring: 19 s, 246,759 episodes per minute
- Episodes with an exact copy in another dataset (every action identical): 28684

## Distributions

Median, with the 10th to 90th percentile in brackets. "Ours in public" is the percentile of our median among public episodes.

| Score | Ours | Public | Ours in public |
|---|---|---|---|
| `length_s` | 18.3 [14.4 to 26] | 11.6 [6.27 to 25.1] | 76% |
| `idle_fraction` | 0.233 [0.166 to 0.318] | 0.239 [0.0785 to 0.437] | 48% |
| `hesitations` | 2 [0 to 5] | 1 [0 to 4] | 70% |
| `hesitation_s` | 0.9 [0 to 3.32] | 0.333 [0 to 2.57] | 71% |
| `jerk` | 27.5 [23.3 to 33.7] | 21.4 [12.9 to 38.5] | 71% |
| `gripper_open_events` | 2 [2 to 2] | 2 [0 to 2] | 47% |
| `action_state_gap` | 0.0228 [0.019 to 0.0282] | 0.0185 [0.0108 to 0.0299] | 71% |

## Notes

- Joint values are scaled to 0 to 1 per dataset (its own 0.5th to 99.5th action percentiles). Units differ between datasets (degrees in ours); the raw ranges are in `scores_by_dataset.csv`.
- `jerk` and `action_state_gap` leave out the gripper. `gripper_open_events` uses the commanded gripper.
- These are proxies for quality, not quality itself. Step 4 checks them against a manual review.
