# Offline comparison: action prediction error on the held-out test set (step 4)

Built by `src/offline_eval.py` (git commit `6bd0be1`). Test set: `causalerror/so101-toy-to-bowl-test` @ `0683b67a`, 9 episodes (project 03's); every 5th frame (861 frames per policy), on mps. Models: SmolVLA = `causalerror/smolvla-so101-toy-to-bowl` @ `a299de1f`, the 20,000-step model (`src/fetch_model.py`); S1 = ACT, project 01's run 4 (`outputs/act_final`).

Mean absolute error between predicted and recorded actions. Body joints in degrees (mean of the five); gripper on its 0 to 100 scale. Mean over the 9 episodes, with a 95% bootstrap interval over episodes in brackets. Lower is closer to how the operator did it. SmolVLA's rows differ only in the random noise its chunks start from (seeds 1000 and 2000); the first is the main result.

| Policy | First action, body | First second, body | First action, gripper | First second, gripper |
|---|---|---|---|---|
| SmolVLA | 2.10 [1.91 to 2.30] | 5.79 [5.19 to 6.44] | 1.82 [1.60 to 2.04] | 5.40 [4.39 to 6.60] |
| SmolVLA, noise seed 2000 | 2.09 [1.90 to 2.29] | 5.79 [5.20 to 6.43] | 1.81 [1.65 to 2.00] | 5.43 [4.41 to 6.66] |
| S1 | 3.52 [3.21 to 3.84] | 7.06 [6.41 to 7.89] | 2.40 [2.05 to 2.80] | 4.53 [4.00 to 5.16] |

## Paired differences (same episodes)

Mean over episodes of (first minus second), with a 95% bootstrap interval. Negative means the first is closer to the recorded actions. An interval that includes 0 is no measurable difference. The last row is SmolVLA against itself with different noise: a difference smaller than that is within SmolVLA's own randomness.

| Comparison | First action, body | First second, body | First action, gripper | First second, gripper |
|---|---|---|---|---|
| SmolVLA minus S1 | -1.42 [-1.67 to -1.20] | -1.27 [-2.04 to -0.58] | -0.59 [-0.97 to -0.29] | +0.88 [-0.29 to +2.31] |
| SmolVLA, noise seed 2000 minus S1 | -1.43 [-1.67 to -1.20] | -1.27 [-2.03 to -0.59] | -0.59 [-0.96 to -0.27] | +0.91 [-0.28 to +2.35] |
| SmolVLA minus SmolVLA, noise seed 2000 | +0.01 [-0.01 to +0.02] | +0.00 [-0.02 to +0.03] | +0.00 [-0.08 to +0.07] | -0.03 [-0.07 to +0.00] |

## Per joint, first second (mean over episodes)

| Policy | shoulder_pan | shoulder_lift | elbow_flex | wrist_flex | wrist_roll | gripper |
|---|---|---|---|---|---|---|
| SmolVLA | 4.23 | 7.31 | 9.42 | 4.73 | 3.27 | 5.40 |
| SmolVLA, noise seed 2000 | 4.21 | 7.32 | 9.43 | 4.73 | 3.26 | 5.43 |
| S1 | 5.15 | 8.74 | 12.16 | 5.63 | 3.63 | 4.53 |

## By spot, first second (mean over 3 episodes each; descriptive only)

| Policy | Spot A, body | Spot A, gripper | Spot B, body | Spot B, gripper | Spot C, body | Spot C, gripper |
|---|---|---|---|---|---|---|
| SmolVLA | 5.14 | 4.42 | 6.82 | 6.95 | 5.41 | 4.85 |
| SmolVLA, noise seed 2000 | 5.18 | 4.41 | 6.79 | 6.98 | 5.40 | 4.91 |
| S1 | 7.71 | 5.23 | 7.39 | 4.00 | 6.09 | 4.35 |

## Time per chunk on this Mac

Pre-processing, prediction, and post-processing, one observation at a time, after 3 warm-up predictions.

| Policy | Predictions timed | Median | Slowest |
|---|---|---|---|
| SmolVLA | 858 | 274 ms | 617 ms |
| SmolVLA, noise seed 2000 | 858 | 275 ms | 452 ms |
| S1 | 858 | 31 ms | 36 ms |

## Notes

- **S1 matches project 03:** the largest difference from project 03's per-episode numbers is 0.0000 (same model, test set, frames, and metric).
- This measures imitation of new demonstrations of our own task, by the same operator. It does not measure success: a policy can be close on average and still miss a grasp. In project 03, S1, S2, and S3 scored about the same here and differed on the arm. The arm trials (step 6) decide.
- Nine episodes: the intervals are wide, and differences may not be measurable here.
- Each prediction starts from the recorded observation, so errors do not compound as they do on the arm.
- SmolVLA builds its vision-language backbone from `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`'s architecture (cached since step 2); the fine-tuned checkpoint then supplies all the weights.
