# Manual review: agreement between the scores and the labels (step 4)

Labels from one reviewer, blind to dataset names and scores, on clips re-encoded in the isolated container. Built by `src/review_agreement.py` with `configs/review.yaml`; labels in `review_labels.csv`.

- Code: git commit `a929de1`
- Clips: 68; labeled 68. By part: extreme 18 (good 11, bad 3, unsure 4), ours 6 (good 6, bad 0, unsure 0), random 36 (good 32, bad 2, unsure 2), repeat 8 (good 5, bad 1, unsure 2)
- Self-consistency: 6/8 repeated clips got the same label as the first time

## Random public episodes: does each score separate bad from good? (n = 34: 2 bad, 32 good)

AUROC: the chance that a randomly chosen bad episode scores worse than a randomly chosen good one. 0.5 is chance, 1.0 is perfect. Brackets: bootstrap 95% interval. Unsure labels are left out.

| Score | Worse is | AUROC, bad vs good | AUROC, matching reason tag | Tag |
|---|---|---|---|---|
| `idle_fraction` | high | 0.50 (too few to bound) | 0.50 (2 tagged) | recording problem |
| `hesitations` | high | 0.30 (too few to bound) | 1.00 (2 tagged) | hesitant or slow |
| `jerk` | high | 0.94 (too few to bound) | 0.00 (1 tagged) | jerky |
| `gripper_deviation` | high | 0.28 (too few to bound) | - (0 tagged) | task failed |
| `action_state_gap` | high | 0.42 (too few to bound) | 0.54 (1 tagged) | jerky |
| `sharpness_min` | low | 0.12 (too few to bound) | 0.46 (1 tagged) | camera problem |
| `brightness_deviation` | high | 0.47 (too few to bound) | 0.83 (1 tagged) | camera problem |
| `frozen_max` | high | 0.33 (too few to bound) | 0.84 (1 tagged) | camera problem |
| `length_deviation` | high | 0.22 (too few to bound) | 0.21 (2 tagged) | recording problem |

## Extremes: the worst episodes for each score

| Score | Labeled bad | With the matching reason |
|---|---|---|
| `idle_fraction` | 2/2 | 2/2 (recording problem) |
| `hesitations` | 0/2 | 1/2 (hesitant or slow) |
| `jerk` | 0/2 | 0/2 (jerky) |
| `gripper_deviation` | 0/2 | 0/2 (task failed) |
| `action_state_gap` | 0/2 | 0/2 (jerky) |
| `sharpness_min` | 0/2 | 0/2 (camera problem) |
| `brightness_deviation` | 0/2 | 0/2 (camera problem) |
| `frozen_max` | 0/2 | 0/2 (camera problem) |
| `length_deviation` | 1/2 | 1/2 (recording problem) |

## Ours

- 6 of our episodes: good 6, bad 0, unsure 0

## Notes

- The worse direction of each score was fixed in `configs/review.yaml` before labeling.
- One reviewer; the repeats are the only measure of label noise. With this few random episodes the intervals are wide; a score whose interval includes 0.5 has not been shown to agree with the labels.
- The extremes are taken from the worse end only, so they show whether a score's worst cases are real problems, not how well it separates typical episodes.
- Clips are 10 fps and 240 pixels high; fine blur may not be visible at that size.
