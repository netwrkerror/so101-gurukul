# Evaluation on the arm: S1, S2, and S3 (step 7, part C)

The protocol and schedule below were written before any trial was run. Results are filled in after the session.

## What is evaluated

| Policy | Model (private) | Local copy | Config |
|---|---|---|---|
| S1: our 45 episodes (project 01's run 4) | `causalerror/act-so101-toy-to-bowl` @ `2ecffdd4` | `outputs/act_final/` | `configs/eval_act_s1.json` |
| S2: ours plus 135 curated public episodes | `causalerror/act-so101-p03-s2-curated` @ `9537e8b4` | `outputs/act_s2/` | `configs/eval_act_s2.json` |
| S3: ours plus 135 random public episodes | `causalerror/act-so101-p03-s3-random` @ `2ea29fd7` | `outputs/act_s3/` | `configs/eval_act_s3.json` |

- **Final checkpoints,** chosen before evaluation, each converted for LeRobot 0.6.0 by removing `"dtype": null` (`src/fetch_models.py`).
- **Run with** `lerobot-rollout`, episodic strategy, in-process, on `mps`, LeRobot 0.6.0.
- **The configs are project 01's `eval_act.json`** with only the policy path, the recording name, and 10 episodes per run changed. The speed cap (`max_relative_target`), timing, and task string are unchanged.
- **Every trial is recorded** (private): `causalerror/rollout_act_p03_<policy>_eval_<timestamp>`, one dataset per block.

## Protocol (project 01's, unchanged)

- **Task string:** `Pick up the stuffed toy and place it in the bowl`.
- **20 trials per policy,** 7 at spot A, 7 at B, 6 at C, in project 01's fixed order: trials 1 to 10 are A, B, C, A, B, C, A, B, C, A; trials 11 to 20 are B, C, A, B, C, A, B, C, A, B.
- **Start of each trial:** the follower in its starting position, and the toy placed by hand on the marked spot, as close as possible to how it was placed during recording.
- **Success:** the toy fully inside the bowl and released within 45 seconds, with no human contact with either arm.
- **Failure types:** grasp missed, dropped during carry, missed the bowl, timed out, or other (with a note). A trial stopped for safety is "other: safety stop".
- **Keys:** right arrow ends a trial early only after a success, or when a failure is certain (as in project 01). Left arrow (discard and re-run) only for a setup mistake, such as the toy on the wrong spot; the voided attempt is still listed with its reason. A policy failure is never discarded.
- **Held fixed:** both camera positions, the evening lighting with the blinds closed (as project 01 and 02's evaluations), the bowl on its outline, the three spots, the toy, and the calibration files.

## Schedule: balanced blocks of 10

Six runs of 10 trials, in this order, so each policy has one block early and one late in the session (light, operator fatigue, and motor warmth all drift over an evening):

| Run | Policy | Block | Trials (spots) |
|---|---|---|---|
| 1 | S1 | 1 | 1 to 10 (A, B, C, A, B, C, A, B, C, A) |
| 2 | S2 | 1 | 1 to 10 |
| 3 | S3 | 1 | 1 to 10 |
| 4 | S3 | 2 | 11 to 20 (B, C, A, B, C, A, B, C, A, B) |
| 5 | S2 | 2 | 11 to 20 |
| 6 | S1 | 2 | 11 to 20 |

## Session conditions (to fill)

| Check | Value |
|---|---|
| Date | TO FILL |
| Git commit | TO FILL |
| Camera indexes (`lerobot-find-cameras`) | TO FILL |
| `front` view against the reference still | TO FILL |
| Lighting | TO FILL (planned: evening, blinds closed) |
| Bowl on its outline, spots taped | TO FILL |
| No recalibration since recording | TO FILL |

## Trials (to fill)

For each policy, 20 rows: trial, spot, outcome, failure type, time to success, notes. Voided attempts listed separately with their reason.

## Known limits

- **Not blind:** the operator knows which policy is running. The success rule is objective, and every trial is recorded, so judgment calls can be checked on video.
- **With 20 trials per policy,** only a large difference (for example 15/20 against 10/20) would be meaningful. The write-up reports intervals.
- **S1 is re-run in the same session** so the three policies share conditions. Its October result (10/20) is reported alongside, but is not the comparison.
