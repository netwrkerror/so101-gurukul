# Evaluation: project 01's policy through the served setup (step 6)

The protocol, schedule, and comparison below were written before any trial was run.

## What is evaluated

- **Policy:** `causalerror/act-so101-toy-to-bowl` at revision `2ecffdd421f46c20f5220c3ca9c4e1fca988a646`, project 01's final checkpoint, converted for LeRobot 0.6.0 by removing `"dtype": null` from `config.json`. The same policy and checkpoint that scored 10/20 in project 01.
- **Served by:** `src/server.py` (LeRobot 0.6.0's `PolicyServer` with metrics), run natively on the Mac, policy on `mps`, no fault injected.
- **Driven by:** `src/runner.py` with `configs/runner.json`. The client is LeRobot's `RobotClient` with 100 actions per chunk and `chunk_size_threshold` 0.0 (a new chunk only when the queue is empty, so chunks are played out whole), 30 Hz, project 01's per-joint speed cap, and a warm-up chunk before trial 1.
- **Metrics:** Prometheus and Grafana running throughout; the runner and server save metrics snapshots at the end of the session.

## Protocol

Unchanged from project 01:

- Task string: `Pick up the stuffed toy and place it in the bowl`.
- 20 trials in one session with one checkpoint: 7 at spot A, 7 at B, 6 at C, in the fixed order below.
- Start of each trial: the follower in its start pose (the runner returns it there after every trial); the toy placed by hand on the marked spot, as close as possible to how it was placed during recording.
- Success: the toy is fully inside the bowl and released within 45 seconds, with no human contact with either arm.
- Each failure is one of: grasp missed, dropped during carry, missed the bowl, timed out, or other (with a note). A trial stopped for safety is "other: safety stop".
- Held fixed: both camera positions, the lighting of project 01's evaluation (blinds closed, evening), the bowl on its outline, the three spots, the toy, and the calibration files.

Keys, as the runner records them:

- `n` during a trial: only after a success (the toy released in the bowl). The runner logs it as a success.
- A failure always runs to the 45-second limit, even when it is clearly lost. The runner logs a timeout as a failure.
- `r` during a trial: only for a setup mistake, such as the toy on the wrong spot. The trial is voided, listed below with its reason, and run again. A policy failure is never voided.
- `q`: ends the session; the arm returns to the start pose first.

## Differences from project 01's evaluation

| | Project 01 (10/20) | This evaluation |
|---|---|---|
| Where the policy runs | Inside `lerobot-rollout`, same process as the control loop | Separate server process, over gRPC on localhost |
| Pause at each chunk boundary | One slow step, about 51 ms | About 2 steps, about 65 ms (step 5) |
| First chunk of the session | Slow (cold start) | Absorbed by a warm-up chunk before trial 1 |
| Reset between trials | Fixed 30 s | Ends when the operator presses `n` |
| Trial recordings | Every trial recorded to a private dataset | None (trial recording is deferred) |
| Front camera | Close to the recording view | TO FILL after the camera check |
| Lighting | Blinds closed, evening | TO FILL (planned: the same) |

## Session conditions

| Check | Value |
|---|---|
| Date | TO FILL |
| Git commit | TO FILL |
| Camera indexes (`lerobot-find-cameras`) | TO FILL |
| Front view against the first frame of recorded episode 0 | TO FILL |
| Lighting | TO FILL |
| Bowl on its outline, spots taped | TO FILL |
| No recalibration since recording | TO FILL |
| Warm-up chunk | TO FILL |

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

Time to success is the trial's duration when ended with `n`, from the trial log: an upper bound on the true time.

Voided trials (setup mistakes, re-run): none so far.

## Serving metrics during the session

| Measure | Value |
|---|---|
| Control loop period (mean, p99) | TO FILL |
| Deadline misses | TO FILL |
| Chunk round trip (mean, p50, p99) | TO FILL |
| Empty-queue steps per chunk | TO FILL |
| Tracking error p90 by joint | TO FILL |
| Alerts | TO FILL |

## Comparison with project 01

| | Project 01 | This evaluation |
|---|---|---|
| Successes | 10/20 (A 4/7, B 3/7, C 3/6) | TO FILL |
| Grasp missed | 6 | TO FILL |
| Dropped during carry | 0 | TO FILL |
| Missed the bowl | 2 | TO FILL |
| Did not release | 2 | TO FILL |
| Timed out (other) | 0 | TO FILL |
| Time to success, range (mean) | 14 to 23 s (16.8 s) | TO FILL |

With 20 trials each, a result of 10/20 is consistent with a true success rate of roughly 30% to 70%. Only a large difference between the two evaluations would show a real effect of serving; a difference of a few trials is within chance.

## Summary

TO FILL after the session.

## Sources

Session IDs are the UTC start time of each runner session. They match the trial-log entries and metrics snapshots kept locally under `outputs/` (gitignored, not in this repo).

| Run | Session ID |
|---|---|
| Evaluation session | TO FILL |
