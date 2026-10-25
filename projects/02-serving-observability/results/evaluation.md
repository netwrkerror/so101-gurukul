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
| Front camera | Close to the recording view | Close to the recording view: the arm fills about 37% of the frame height against 40%, same horizontal position; slightly more of the bowl in view |
| Lighting | Blinds closed, evening | Blinds closed, evening (the same) |

## Session conditions

| Check | Value |
|---|---|
| Date | 2026-10-24, evening |
| Git commit | `49aa349` (protocol committed before the session) |
| Camera indexes (`lerobot-find-cameras`) | `wrist` 0, `front` 1, confirmed from stills before the session. The front camera timed out once at connection in the dim light, so it was given 3 s to warm up at connection (`warmup_s: 3`); this affects only connecting, not frames during trials |
| Front view against the first frame of recorded episode 0 | Arm about 37% of the frame height against 40%; arm at the same horizontal position; spot marks aligned with the recorded toy position; bowl slightly further into the frame |
| Lighting | Blinds closed, evening, as in project 01's evaluation |
| Bowl on its outline, spots taped | Yes |
| No recalibration since recording | None reported |
| Warm-up chunk | 0.46 s |

## Trials

| Trial | Spot | Outcome | Failure type | Time to success (s) | Notes |
|---|---|---|---|---|---|
| 1 | A | Success |  | 23 | Pushed the toy off its spot while picking, then grasped it and succeeded |
| 2 | B | Failure | Missed the bowl | | Pushed the toy off its spot while picking and tried about twice; grasped it, then released it early, on the way to the bowl (operator's best recollection) |
| 3 | C | Failure | not recorded | | |
| 4 | A | Failure | Grasp missed | | Pushed the toy to the left, hesitated, then moved toward the bowl without the toy, completing the motion empty |
| 5 | B | Failure | Grasp missed | | Pushed the toy off its spot, then kept moving as if looking for it, toward spot A and then toward the bowl. One voided attempt before (setup mistake) |
| 6 | C | Failure | Missed the bowl | | Released the toy outside the bowl; tried again |
| 7 | A | Success |  | 31 | Grasped the toy after 3 tries and released it in the bowl |
| 8 | B | Failure | Grasp missed | | Reached to the right of the toy and pushed it to the left |
| 9 | C | Failure | Grasp missed | | Could not grasp the toy: closed the gripper slightly early (misjudged depth) and moved toward the bowl. One voided attempt before (setup mistake) |
| 10 | A | Failure | Grasp missed | | Did not reach far enough to grasp |
| 11 | B | Success |  | 26 | Hesitated before releasing, then released |
| 12 | C | Success |  | about 44 | Released in the bowl at about 44 s, judged by the operator at the limit; the runner logged a timeout because `n` was not pressed in time. One voided attempt before (setup mistake) |
| 13 | A | Success |  | 18 | Worked cleanly. Four voided attempts before (setup mistakes) |
| 14 | B | Failure | Grasp missed | | Almost grasped the toy, then pushed it off its spot |
| 15 | C | Failure | Grasp missed | | Jerky movements; the arm did not extend toward the toy or open its gripper, and kept moving toward spot A. Three voided attempts before (setup mistakes) |
| 16 | A | Success |  | 32 | Pushed the toy off its spot, reached further and grasped it; failed to release 3 times, then released |
| 17 | B | Success |  | 15 | One voided attempt before (setup mistake) |
| 18 | C | Failure | Grasp missed | | Jerky movements; the arm did not extend toward the toy or open its gripper. One voided attempt before (setup mistake) |
| 19 | A | Success |  | 12 | One voided attempt before (setup mistake) |
| 20 | B | Success |  | 15 | |

Time to success is the trial's duration when ended with `n`, from the trial log: an upper bound on the true time.

## Serving metrics during the session

| Measure | Value |
|---|---|
| Control loop period (mean, p99) | 33.36 ms, 33.5 ms (30 Hz) |
| Deadline misses | 0 |
| Chunk round trip (mean, p50, p99) | 72 ms, 73 ms, 94 ms (315 chunks) |
| Empty-queue steps per chunk | 1.94 (about 65 ms of pause per chunk) |
| Server inference per chunk (mean, p50) | 64 ms, 63 ms (316 chunks, including warm-up); 0 server errors |
| Tracking error p90 by joint | shoulder pan 3.8, shoulder lift 8.4, elbow flex 7.2, wrist flex 3.9, wrist roll 1.2 (degrees); gripper 5.4 |
| Alerts | None fired. `ControlRateLow` was pending for 2 samples (about 4 s), at a trial boundary |

## Comparison with project 01

| | Project 01 | This evaluation |
|---|---|---|
| Successes | 10/20 (A 4/7, B 3/7, C 3/6) | **9/20** (A 5/7, B 3/7, C 1/6) |
| Grasp missed | 6 | 8 (trials 4, 5, 8, 9, 10, 14, 15, 18) |
| Dropped during carry | 0 | 0 |
| Missed the bowl | 2 | 2 (trials 2, 6) |
| Did not release | 2 | 0 |
| Timed out (other) | 0 | 0 |
| Failure type not recorded | 0 | 1 (trial 3) |
| Time to success, range (mean) | 14 to 23 s (16.8 s) | 12 to 32 s (21.6 s) for the 8 trials ended with `n`; trial 12 about 44 s |

Failure types come from the operator's notes, written after the session; trial 2's is a best recollection and trial 3 has no note. With these counts, the failure mix looks similar to project 01's: missed grasps dominate.

With 20 trials each, a result of 10/20 is consistent with a true success rate of roughly 30% to 70%. Only a large difference between the two evaluations would show a real effect of serving; a difference of a few trials is within chance.

## Summary

**9/20 through the served setup, against 10/20 in project 01.** Same policy and checkpoint, task, spots, cameras, lighting, and time limit; served over gRPC on localhost, with about 65 ms of pause at each chunk boundary.

- **Serving did not measurably change the success rate.** A difference of one trial in 20 is well within chance. Through the whole session the serving side was steady: 30 Hz with no deadline misses, a 72 ms mean round trip (p99 94 ms), about 2 steps of pause per chunk, and no server errors.
- **Spot C was the weak spot: 1/6, against 3/6 in project 01.** Six trials per spot are too few to tell a real change from chance. The metrics show spot C trials were served no differently from the others (the same pauses and round trips), so if the drop is real, it comes from the policy, not from serving.
- **In trials 15 and 18 the policy's commands themselves were unsteady.** The operator saw jerky movements, with the arm not reaching or opening its gripper. Per-attempt metrics show normal pauses and normal arm tracking error in those trials, so the arm followed its commands, and the gripper's low tracking error (2 to 3, against 8 to 10 when it closes on the toy) matches never grasping.
- **Missed grasps are still the main failure: 8 of 11,** as in project 01 (6 of 10). In 5 of the 8, the arm pushed the toy off its spot and did not recover.
- **But the policy did recover a pushed toy, in trials 1 and 16:** it went after the toy, grasped it, and succeeded. In project 01's evaluation it never recovered a pushed toy. With so few trials this is an observation, not a measured difference.
- **Release hesitation also appeared in successes:** trial 11 hesitated before releasing, and trial 16 failed to release three times before letting go. It is the same weakness behind project 01's two "did not release" failures.
- **Caveats.** 13 attempts were voided and re-run, against 3 in project 01; all were classified as setup mistakes after the session, without video, and four of them preceded counted successes. Trial 12's success was judged by eye at 44 s of 45. Failure types come from notes written after the session; trial 2's is a best recollection and trial 3 has none.

## Sources

Session IDs are the UTC start time of each runner session. They match the trial-log entries and metrics snapshots kept locally under `outputs/` (gitignored, not in this repo).

| Run | Session ID |
|---|---|
| Evaluation session | `20261024T225735Z` |
