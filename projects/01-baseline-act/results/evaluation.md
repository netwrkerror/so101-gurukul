# Evaluation: project 01 ACT policy on the arm

Step 6 of the brief. The schedule and protocol below were written before any trial was run.

## What is evaluated

- Policy: `causalerror/act-so101-toy-to-bowl` at revision `2ecffdd421f46c20f5220c3ca9c4e1fca988a646` (the final checkpoint of run 4, chosen before evaluation), converted for LeRobot 0.6.0 by removing `"dtype": null` from `config.json`. Local copy: `outputs/act_final/`.
- Run with: `lerobot-rollout`, episodic strategy, LeRobot 0.6.0 (commit `30da8e687a6dfc617fcd94afc367ac7071c376ce`), on `mps`.
- Config: `configs/eval_act.json`.
- Trial recordings: `causalerror/rollout_act_so101_toy_to_bowl_eval_<timestamp>` (private; LeRobot appends the session's timestamp). Session dataset: `causalerror/rollout_act_so101_toy_to_bowl_eval_20261018_194442`, 20 episodes (one per counted trial).

## Protocol

From the brief:

- Task string: `Pick up the stuffed toy and place it in the bowl`.
- 20 trials in one session with one checkpoint: 7 at spot A, 7 at B, 6 at C, in the fixed order below.
- Start of each trial: `shishya` (follower) in its starting position; the toy placed by hand on the marked spot, as close as possible to how it was placed during recording.
- Success: the toy is fully inside the bowl and released within 45 seconds, with no human contact with either arm.
- Each failure is one of: grasp missed, dropped during carry, missed the bowl, timed out, or other (with a note). A trial stopped for safety is "other: safety stop".
- Right arrow ends a trial early only after a success. Left arrow (discard and re-run) is used only for a setup mistake, such as the toy on the wrong spot; the voided trial is still listed below with its reason. A policy failure is never discarded.
- Held fixed from recording: both camera positions, lighting, the bowl on its outline, the three spots, the toy, and the calibration files.

## Session conditions

| Check | Value |
|---|---|
| Date and time | 2026-10-18, 19:44 to 20:04 MDT |
| Git commit | `e0716e7`. The lighting decision below was written before the session but committed after it |
| Camera indexes (from `lerobot-find-cameras`) | `wrist` 0, `front` 1, confirmed from the saved stills before the dry run |
| `front` view matches the reference still | Close: compared with the first `front` frame of recorded episode 0, the framing is within a few percent; the bowl looks slightly further into the frame |
| Lighting as during recording | No, by decision (`DECISIONS.md`, 2026-10-18): blinds closed and evening light, against open blinds and daylight during recording. The session ran from 19:44 to 20:04 with the blinds closed. Tape marks for the spots and bowl outline are also new in the `front` view |
| Bowl on its outline, spots taped | Yes |
| No recalibration since recording | None reported |

## Dry runs (not counted)

2026-10-18, 19:07 to 19:09 MDT, git commit `22676d5`, config `configs/eval_act_dryrun.json`. Blinds closed, evening light: not the recording's lighting, so these say nothing about the success rate. Recordings: `causalerror/rollout_act_so101_toy_to_bowl_dryrun_20261018_190723` (LeRobot appends a timestamp to rollout dataset names).

| Dry run | Spot | Outcome | Notes |
|---|---|---|---|
| 1 | A | Success | Ended with the right arrow after 41.6 s (1,247 frames) |
| 2 | A | Success | Ran the full 45 s (1,341 frames); the right arrow was not pressed |

Pipeline checks from the dry run:

- Policy, both cameras, and the follower connected; the arm returned to its starting position between trials and at the end; both trials uploaded.
- Keyboard: macOS did not grant `pynput` permission, so LeRobot fell back to terminal keys (arrows, or `n`/`r`/`q`) with the terminal focused. The right arrow worked.
- Control rate: LeRobot warned "Record loop is running slower (about 19.5 Hz) than the target FPS (30 Hz)" about every 3.3 s. That is one warning per 100-step ACT action chunk: the warning measures a single loop iteration, and the slow one is the step where the network runs (24 ms on `mps`, measured offline). The recorded frame counts show the loop as a whole kept 30 Hz: 1,247 frames in 42 s and 1,341 frames in 45 s of wall-clock time. Offline timing: the inference pipeline takes 2.6 ms on other steps; reading the follower and both cameras and sending a command takes 2.2 ms with the speed cap.

## Trials

| Trial | Spot | Outcome | Failure type | Time to success (s) | Notes |
|---|---|---|---|---|---|
| 1 | A | Success |  | 18 |  |
| 2 | B | Success |  | 15 |  |
| 3 | C | Success |  | 16 | Grasped by the legs. Re-run after a setup issue (see below) |
| 4 | A | Success |  | 14 |  |
| 5 | B | Failure | Grasp missed |  | Failed to pick up; retried several times until time ran out |
| 6 | C | Failure | Missed the bowl |  | Missed the first grasp, moved toward the bowl, came back and grasped, then dropped the toy outside the bowl and returned to rest. Ended with the right arrow at 38 s |
| 7 | A | Failure | Missed the bowl |  | Grasped and moved quickly to the bowl, released from above outside it; the toy fell to the floor. Ended with the right arrow at 13 s |
| 8 | B | Failure | Grasp missed |  | Did not grasp properly and displaced the toy; went toward the bowl, came back and retried several times; the arm did not reach far enough |
| 9 | C | Failure | Other: did not release |  | Grasped and carried the toy into the bowl but did not open the gripper; carried it back and dropped it near the marker; repeated grasp attempts failed |
| 10 | A | Success |  | 17 |  |
| 11 | B | Failure | Grasp missed |  | Could not pick up the toy. Re-run after a setup issue (see below); the re-run is the counted trial |
| 12 | C | Success |  | 17 | Grasped by the legs |
| 13 | A | Failure | Grasp missed |  | Pushed the toy off its spot, then could not pick it up |
| 14 | B | Failure | Grasp missed |  | Pushed the toy off its spot, then could not pick it up |
| 15 | C | Success |  | 15 | Grasped by the legs. Re-run after a setup issue (see below) |
| 16 | A | Failure | Grasp missed |  | Pushed the toy off its spot, then could not pick it up |
| 17 | B | Success |  | 17 |  |
| 18 | C | Failure | Other: did not release |  | Picked up the toy but did not release it in the bowl; motions looked hesitant |
| 19 | A | Success |  | 23 |  |
| 20 | B | Success |  | 16 |  |

Time to success is when the right arrow was pressed after the toy was released, from the log timestamps, rounded to the second: an upper bound on the true time.

Voided trials (re-run after a setup issue, as reported by the operator; the discarded attempts are not in the dataset):

| Trial | Spot | Discarded attempt | Re-run |
|---|---|---|---|
| 3 | C | Stopped with the left arrow after 24 s | Success |
| 11 | B | Stopped with the left arrow after 30 s | Failure |
| 15 | C | Stopped with the left arrow after 9 s | Success |

Deviations from the protocol:

- The right arrow ended two failed trials early: trial 6 at 38 s (toy already dropped outside the bowl, arm back at rest) and trial 7 at 13 s (toy on the floor). Neither could have become a success, so the outcomes stand.
- Lighting differed from recording, by decision (see Session conditions).

## Summary

**10/20 successes**: stuffed toy from three marked spots into a fixed bowl, `wrist` and `front` cameras, 45-second limit, one checkpoint, room lighting with the blinds closed (not the recording's daylight).

| Spot | Successes |
|---|---|
| A | 4/7 |
| B | 3/7 |
| C | 3/6 |
| Total | 10/20 |

Failures by type:

| Type | Count | Trials |
|---|---|---|
| Grasp missed | 6 | 5, 8, 11, 13, 14, 16 |
| Missed the bowl | 2 | 6, 7 |
| Other: did not release | 2 | 9, 18 |
| Dropped during carry | 0 | |
| Timed out | 0 | |

The brief's target of 10/20 is reached, so per the definition of done there is no improvement round.

What the numbers support:

- With 20 trials, 10/20 is consistent with a true success rate of roughly 30% to 70%. The per-spot counts (6 or 7 trials each) are too small to say one spot is harder than another.
- Grasping is the main weakness: 6 of the 10 failures never picked the toy up. In three of them the policy pushed the toy off its spot and could not recover; the training data never shows the toy away from the three spots.
- In two failures the policy carried the toy to the bowl but did not open the gripper.
- Successful trials took 14 to 23 seconds (mean 16.8), against 19.2 seconds on average for the demonstrations.
- Trials 5 to 9 failed in a row. The cause is not known; the log shows nothing different about them.

Not tested: performance in the recording's lighting, from spots other than A, B, and C, or with the bowl elsewhere.
