# Evaluation: project 01 ACT policy on the arm

Step 6 of the brief. The schedule and protocol below were written before any trial was run.

## What is evaluated

- Policy: `causalerror/act-so101-toy-to-bowl` at revision `2ecffdd421f46c20f5220c3ca9c4e1fca988a646` (the final checkpoint of run 4, chosen before evaluation), converted for LeRobot 0.6.0 by removing `"dtype": null` from `config.json`. Local copy: `outputs/act_final/`.
- Run with: `lerobot-rollout`, episodic strategy, LeRobot 0.6.0 (commit `30da8e687a6dfc617fcd94afc367ac7071c376ce`), on `mps`.
- Config: `configs/eval_act.json`.
- Trial recordings: `causalerror/rollout_act_so101_toy_to_bowl_eval_<timestamp>` (private; LeRobot appends the session's timestamp). Exact name: TO FILL.

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

To fill in on the day:

| Check | Value |
|---|---|
| Date and time | TO FILL |
| Git commit | TO FILL |
| Camera indexes (from `lerobot-find-cameras`) | TO FILL |
| `front` view matches the reference still | TO FILL |
| Lighting as during recording | TO FILL |
| Bowl on its outline, spots taped | TO FILL |
| No recalibration since recording | TO FILL |

## Dry runs (not counted)

2026-10-18, 19:07 to 19:09 MDT, git commit `22676d5`, config `configs/eval_act_dryrun.json`. Blinds closed, evening light: not the recording's lighting, so these say nothing about the success rate. Recordings: `causalerror/rollout_act_so101_toy_to_bowl_dryrun_20261018_190723` (LeRobot appends a timestamp to rollout dataset names).

| Dry run | Spot | Outcome | Notes |
|---|---|---|---|
| 1 | A | TO FILL | Ended with the right arrow after 41.6 s (1,247 frames) |
| 2 | A | TO FILL | Ran the full 45 s (1,341 frames) |

Pipeline checks from the dry run:

- Policy, both cameras, and the follower connected; the arm returned to its starting position between trials and at the end; both trials uploaded.
- Keyboard: macOS did not grant `pynput` permission, so LeRobot fell back to terminal keys (arrows, or `n`/`r`/`q`) with the terminal focused. The right arrow worked.
- Control rate: LeRobot warned "Record loop is running slower (about 19.5 Hz) than the target FPS (30 Hz)" about every 3.3 s. That is one warning per 100-step ACT action chunk: the warning measures a single loop iteration, and the slow one is the step where the network runs (24 ms on `mps`, measured offline). The recorded frame counts show the loop as a whole kept 30 Hz: 1,247 frames in 42 s and 1,341 frames in 45 s of wall-clock time. Offline timing: the inference pipeline takes 2.6 ms on other steps; reading the follower and both cameras and sending a command takes 2.2 ms with the speed cap.

## Trials

| Trial | Spot | Outcome | Failure type | Time to success (s) | Notes |
|---|---|---|---|---|---|
| 1 | A | | | | |
| 2 | B | | | | |
| 3 | C | | | | |
| 4 | A | | | | |
| 5 | B | | | | |
| 6 | C | | | | |
| 7 | A | | | | |
| 8 | B | | | | |
| 9 | C | | | | |
| 10 | A | | | | |
| 11 | B | | | | |
| 12 | C | | | | |
| 13 | A | | | | |
| 14 | B | | | | |
| 15 | C | | | | |
| 16 | A | | | | |
| 17 | B | | | | |
| 18 | C | | | | |
| 19 | A | | | | |
| 20 | B | | | | |

Voided trials (setup mistakes, re-run): none so far.

## Summary

TO FILL after the session: successes out of 20 overall and per spot, failure counts by type, and whether the 10/20 target was reached.
