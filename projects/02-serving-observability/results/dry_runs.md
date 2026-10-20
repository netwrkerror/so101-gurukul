# Dry runs: project 02

Not counted in any evaluation. Each checks a setup before it is used for counted trials.

## 2026-10-19: stock async client, server on the Mac (step 1)

Setup: LeRobot 0.6.0 `policy_server` and `robot_client` from `configs/policy_server.json` and `configs/robot_client.json`, localhost, policy on `mps`, `actions_per_chunk` 100, `chunk_size_threshold` 0.0, project 01's speed cap. Policy: project 01's final checkpoint (`outputs/act_final`). Spot A, bowl on its outline, evening lighting. Session started 19:45 MDT. Client log: `outputs/p02_client_dryrun.log` (local).

What happened:

1. The client connected to the follower, both cameras, and the server, and the server loaded the policy. The toy was picked up from spot A and placed in the bowl: a success through the server path.
2. With the client still running (the stock client has no trials or reset phase), the toy was put back on spot A by hand. The policy picked it up straight away and carried it to the bowl, but did not open the gripper. It took the toy back toward the start, returned to the bowl, and again did not release it. This repeated about six times, until the client was stopped with Ctrl+C.

Observations:

- The server path works end to end: observations out, action chunks back, the arm driven at 30 Hz, with no errors in the client log.
- "Did not release" is the same failure seen in project 01's trials 9 and 18, under the synchronous `lerobot-rollout`, so it is not evidence of a serving problem. It is not counted either way.
- The repetition is expected from how ACT runs: at inference it is deterministic, so a similar camera view and arm position produce the same chunk of actions again. Without a time limit, a stuck policy repeats the same motion indefinitely.
- The stock client recorded no timing data at INFO level. Measuring the pause between chunks, queue depth, and round-trip time needs step 3's metrics.
- Resetting the toy while the client kept running meant a hand near a moving arm. Step 3's runner adds a reset phase with the policy paused.

## 2026-10-19: runner first start, motor 4 did not answer (step 2)

The first start of `src/runner.py` failed inside LeRobot while connecting to the follower, before any runner code ran: `Failed to write 'Torque_Enable' on id_=4 ... There is no status packet!`. Motor 4 (wrist flex) did not reply on the serial bus when LeRobot switched the motors back on after configuring them. Likely causes: a loose connector on the daisy chain, the servo's overload protection after the long hold in the step 1 dry run, or a one-off dropped reply (LeRobot tries once). Fixed by power-cycling the follower and reseating the cables at motor 4; the next start connected normally. Which cause it was is not known.

## 2026-10-20 02:19 UTC (2026-10-19 evening MDT): runner, dry-run mode (step 2)

Setup: `src/server.py` and `src/runner.py` with `configs/runner.json`, `--dry_run=true --schedule="[A,B]"`, so the policy never moved the arm. Log: `outputs/p02_trials_dryrun.jsonl` (local).

| Trial | Spot | Ended by | Duration |
|---|---|---|---|
| 1 | A | success (n key) | 15.6 s |
| 2 | B | timeout | 45.0 s |

The session connected to the follower, both cameras, and the server; waited for the start key; reset between trials; honoured the n key; ended trial 2 at the limit; logged both trials; and disconnected. Metrics were not captured from this session, so the runner now saves a snapshot of its metrics when a session ends.

## 2026-10-20 02:27 UTC (2026-10-19 evening MDT): runner, two real trials (step 2)

Setup: as the dry-run mode session, without `--dry_run`, `--schedule="[A,A]"`. Logs: `outputs/p02_trials_dryrun.jsonl`, `outputs/p02_runner_dryrun.log`, metrics snapshot `outputs/p02_client_metrics_20261020T022649Z.prom` (all local).

| Trial | Spot | What happened | Logged as |
|---|---|---|---|
| 1 | A | Success | success, 24.7 s |
| 2 | A | Pushed the toy off its spot, went toward the bowl, came back, grasped it, and placed it in the bowl: a success | quit, 29.1 s (ended with `q` instead of `n`) |

Trial 2 is the first time the policy has been seen to recover a displaced toy; in project 01's evaluation it never did (trials 13, 14, and 16). One trial cannot show whether this happens more often through the server.

Client metrics over about 1,450 control steps (percentiles are bucket upper bounds):

| Metric | Value |
|---|---|
| Loop period | mean 36.9 ms against a target of 33.3 ms: about 27 Hz |
| Work per step | mean 2.7 ms, p99 at most 10 ms; 0 deadline misses |
| Chunk round trip | 15 chunks, mean 90 ms, p50 at most 75 ms, p90 at most 100 ms |
| Steps with an empty queue | 29 over 16 chunks: about 2 steps of waiting per chunk |
| Tracking error, mean | shoulder pan 1.1, shoulder lift 3.6, elbow flex 3.3, wrist flex 1.7, wrist roll 0.5 (degrees); gripper 2.5 |

Finding: the loop ran at about 27 Hz because Python's `time.sleep` overshoots by a few milliseconds per step on macOS. The work itself took 2.7 ms. LeRobot's `precise_sleep` (sleep, then spin for the last few milliseconds), used by `lerobot-rollout` and so by project 01, avoids this; LeRobot's stock async client, which the runner copied, does not. The runner now uses `precise_sleep`. At 27 Hz the policy's actions played out about 10% slower than at training time.

The "Error receiving actions: Channel closed" at the end of the session is the chunk receiver's pending call being cancelled when the client closes its connection. Harmless.

## 2026-10-20 02:35 UTC: loop timing after switching to `precise_sleep` (step 2)

Setup: runner in dry-run mode, one 45-second trial, policy not moving the arm. Metrics snapshot `outputs/p02_client_metrics_20261020T023520Z.prom` (local).

- Loop period: mean 33.35 ms over 1,349 steps (29.98 Hz; target 33.33 ms). Every step fell in the 33.3 to 36 ms bucket.
- Work per step: mean 1.36 ms (lower than with the policy running, since no actions or observations are sent in dry-run mode); 0 deadline misses.

The fix holds the loop at 30 Hz. With the policy running, the work per step was 2.7 ms, well inside the 33 ms budget, so the same should hold; to be confirmed in the next session with the policy.
