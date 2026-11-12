# S2 and S3: episode selection (step 5a)

Built by `src/curate_plan.py` with `configs/curation.yaml` (git commit `8f64adf`). Episode lists: `s2_episodes.csv`, `s3_episodes.csv`. Both sets are our 45 episodes plus the public episodes below.

| Step | Datasets | Episodes |
|---|---|---|
| Shortlisted datasets (step 3b), minus the 2 excluded | 73 |  |
| Joint units match ours (a body joint beyond +-100) | 61 |  |
| A wrist camera and a fixed camera | 61 |  |
| Episodes scored in 3a and 3b | 61 | 4213 |
| After dropping exact copies (one per fingerprint) | 61 | 4213 |
| After excluding datasets LeRobot could not build (exclude_build) | 58 | 3972 |
| S2: idle fraction at most 0.482 (pool's 95% quantile) | 58 | 3773 |
| S2: length within a factor of 2.37 of the median 13.8 s | 58 | 3577 |
| S2: exactly 2 gripper openings (a single pick and place) | 52 | 2373 |

- **S3 (random control):** 135 episodes from 46 datasets, drawn with seed 1000 from the pool after copies were dropped. No quality or relevance filter.
- **S2 (curated):** 135 episodes from 16 datasets, at most 10 per dataset, closest to our scene first.
- Episodes in both sets: 4.
- Median length: S2 10.5 s, S3 16.5 s. Median distance to our scene (front camera): S2 0.225, S3 0.269.
- Gripper openings in S3: 1: 21, 2: 94, 3: 1, 4: 11, 5: 2, 6: 2, 7: 1, 8: 3

## Notes

- Joint units: datasets whose body joints all stay within +-100 may use the older -100 to 100 scale; they are excluded, not converted. Calibration still differs from arm to arm (the brief's risk); this is not corrected.
- Camera mapping: the wrist camera becomes `wrist`; the fixed camera with the lowest median distance to our scene becomes `front`; others are dropped. Every public episode is re-encoded to our video settings when the sets are built.
