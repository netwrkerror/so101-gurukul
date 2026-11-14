# Offline metric: action prediction error on the held-out test set (step 7, part B)

Built by `src/offline_eval.py` (git commit `7bb5742`). Test set: `causalerror/so101-toy-to-bowl-test` @ `0683b67a`, 9 episodes; every 5th frame (861 frames per policy), on mps. Models: S1 = run 4 (`outputs/act_final`), S2 and S3 = the final checkpoints (`src/fetch_models.py`).

Mean absolute error between predicted and recorded actions. Body joints in degrees (mean of the five); gripper on its 0 to 100 scale. Mean over the 9 episodes, with a 95% bootstrap interval over episodes in brackets. Lower is closer to how the operator did it.

| Policy | First action, body | First second, body | First action, gripper | First second, gripper |
|---|---|---|---|---|
| S1 | 3.52 [3.21 to 3.84] | 7.06 [6.41 to 7.89] | 2.40 [2.05 to 2.80] | 4.53 [4.00 to 5.16] |
| S2 | 3.95 [3.59 to 4.51] | 7.20 [6.51 to 8.14] | 2.15 [1.87 to 2.47] | 4.73 [4.05 to 5.47] |
| S3 | 3.96 [3.50 to 4.49] | 6.95 [6.38 to 7.66] | 2.33 [2.06 to 2.61] | 4.89 [4.33 to 5.44] |

## Paired differences (same episodes)

Mean over episodes of (first policy minus second), with a 95% bootstrap interval. Negative means the first policy is closer to the recorded actions. An interval that includes 0 is no measurable difference.

| Comparison | First second, body (degrees) | First second, gripper |
|---|---|---|
| S2 minus S1 | +0.13 [-0.53 to +0.75] | +0.20 [-0.27 to +0.72] |
| S3 minus S1 | -0.11 [-0.47 to +0.26] | +0.36 [-0.13 to +0.82] |
| S2 minus S3 | +0.25 [-0.52 to +0.91] | -0.16 [-0.85 to +0.66] |

## Per joint, first second (mean over episodes)

| Policy | shoulder_pan | shoulder_lift | elbow_flex | wrist_flex | wrist_roll | gripper |
|---|---|---|---|---|---|---|
| S1 | 5.15 | 8.74 | 12.16 | 5.63 | 3.63 | 4.53 |
| S2 | 4.87 | 8.52 | 11.64 | 6.10 | 4.85 | 4.73 |
| S3 | 4.65 | 9.52 | 11.40 | 5.57 | 3.61 | 4.89 |

## Notes

- This measures imitation of new demonstrations of our own task, by the same operator. It does not measure success: a policy can be close on average and still miss a grasp. The arm trials decide that.
- Nine episodes: the intervals are wide, and differences between policies may not be measurable here.
- Each prediction starts from the recorded observation, so errors do not compound as they do on the arm.
