# Latency characterisation and deliberate faults (step 5)

Not counted toward any success rate. The fault is a slow server: `src/server.py --fault_delay_s=<seconds>` sleeps inside every chunk's inference, so the delay appears as slower inference. Expectations were written before measuring.

Setup for every session (2026-10-24): native server on `mps`, runner from `configs/runner.json` (100 actions per chunk, `chunk_size_threshold` 0.0, 30 Hz), a warm-up chunk before trial 1, spot A. Front camera close to the recording view (arm about 35% of the frame height against 40%), blinds open in daylight. Percentiles are interpolated within histogram buckets; means are exact.

## Part A: shadow mode, the arm holds still (one 45-second trial each)

| Fault delay | Expected round trip | Measured round trip: mean (p50, p99) | Expected pause | Empty-queue steps per chunk | Loop period, mean | Client work p99 | Deadline misses | Server inference p50 | Alerts |
|---|---|---|---|---|---|---|---|---|---|
| 0 ms | about 74 ms | 79 ms (76, 121) | about 2 steps | 2.0 | 33.37 ms | 4.9 ms | 0 | 66 ms | none |
| 100 ms | about 175 ms | 172 ms (177, 243) | about 5 steps | 4.4 | 33.36 ms | 4.9 ms | 0 | 177 ms | none |
| 200 ms | about 275 ms | 271 ms (277, 343) | about 8 steps | 7.6 | 33.36 ms | 5.5 ms | 0 | 275 ms | `ChunkRoundTripHigh` firing for 6 s, from about 28 s into the trial |
| 400 ms | about 475 ms | 470 ms (450, 499) | about 14 steps | 13.6 | 33.36 ms | 5.0 ms | 0 | 454 ms | `ChunkRoundTripHigh` firing from about 28 s into the trial until about 40 s after it ended |

Observations skipped by the server: 27, 61, 98, 162. Warm-up chunks: 0.59, 0.60, 0.55, 0.81 s. The server's inference p99 (712 to 967 ms) includes the warm-up chunk; the client's round-trip metrics exclude it.

## Part B: mitigation, shadow mode (inconclusive)

Setup: 400 ms fault delay, runner with `--chunk_size_threshold=0.2`, so the client asks for the next chunk while 20 actions (about 0.67 s) are still queued. Expected: the next chunk arrives before the queue empties, so the pauses disappear. Run twice, with one server run covering both.

| Run | Chunks received | Empty-queue steps per chunk | Round trip, mean | Deadline misses |
|---|---|---|---|---|
| B1 | 12 | 13.8 | 473 ms | 0 |
| B2 | 12 | 13.8 | 471 ms | 0 |
| Part A, 400 ms, threshold 0.0 (for comparison) | 12 | 13.6 | 470 ms | 0 |

Server, both sessions together: 26 observations used, 801 skipped.

The mitigation had no effect, because the server ignored every early request. LeRobot's policy server runs inference on an observation only if the client marks it as required (`must_go`, which the client sets only when its queue is empty), or if the robot's joint positions differ by more than 1 unit from the last observation it ran on (`observations_similar` in `lerobot/async_inference/helpers.py`). In shadow mode the arm holds still, so every early observation looked like a duplicate and was skipped; inference waited for the empty queue, as with a threshold of 0.

So shadow mode cannot test this mitigation: any server logic that depends on the robot's state behaves differently when the robot does not move. On the arm, the joints are moving when the early request is sent, so the filter would let it through. That test is listed under "later" in the brief.

## Part C: on the arm (not counted)

| Fault delay | Session | Trial | Outcome (trial log) | What the arm did | Round trip, mean | Empty-queue steps per chunk | Tracking error p90 (degrees; gripper 0 to 100) |
|---|---|---|---|---|---|---|---|
| 0 ms | C1 | 1 | success, 21.7 s | not recorded | 72 ms | 1.9 | shoulder pan 3.1, shoulder lift 8.4, elbow 8.1, wrist flex 1.9, wrist roll 1.0, gripper 4.9 |
| 0 ms | C1 | 2 | timeout, 45 s | not recorded | | | |
| 200 ms | C2 | 1 | success, 14.7 s | not recorded | 267 ms | 7.6 | shoulder pan 3.0, shoulder lift 8.0, elbow 5.8, wrist flex 2.5, wrist roll 1.5, gripper 4.9 |
| 200 ms | C2 | 2 | timeout, 45 s | not recorded | | | |
| 200 ms | C3 | 1 | success, 35.4 s | not recorded | 272 ms | 7.9 | shoulder pan 1.9, shoulder lift 9.2, elbow 8.7, wrist flex 2.7, wrist roll 1.4, gripper 8.2 |
| 200 ms | C3 | 2 | success, 19.3 s | not recorded | | | |

The 200 ms setting was run as two sessions of two trials (four trials) instead of one. Control loop 33.35 to 33.36 ms and no deadline misses in all three sessions. No alert fired during part C.

## Findings

1. **Server latency passes straight through to the arm.** The round trip rose by 93, 192, and 391 ms for delays of 100, 200, and 400 ms, and the pause at each chunk boundary grew in step (2.0, 4.4, 7.6, 13.6 empty-queue steps per chunk). With `chunk_size_threshold` at 0, the client does nothing to hide server latency.
2. **The control loop is unaffected by a slow server.** It held 30 Hz with no deadline misses at every delay. A slow server lengthens the pauses between chunks; it does not slow the loop.
3. **The observation flood alone does not cause deadline misses.** At 400 ms the client sent 162 skipped 1.8 MB observations to the native server, and its work per step stayed under 5.0 ms at p99. The 2 deadline misses seen with the containerized server (`dashboards.md`) therefore need another explanation. A likely one, not tested, is that sends into Docker Desktop's virtual machine are slower than to a local process.
4. **The round-trip alert is borderline at 200 ms.** That delay puts the 90th percentile at about 300 ms, so `ChunkRoundTripHigh` fired for 6 seconds in part A and not at all in part C. This is the alert doing what it says, near its threshold. The rule is unchanged.
5. **On the arm, pauses of about a quarter of a second did not stop the task.** 3 of 4 trials succeeded at 200 ms and 1 of 2 at no delay, with similar tracking error. With 2 and 4 trials this is not a comparison, only evidence that the task still worked with the pauses.
6. **The warm-up chunk** took 0.35 to 0.81 s across sessions, the cold-start cost that the warm-up keeps out of trial metrics.
7. **Shadow mode has a blind spot.** The early-request mitigation (part B) could not be tested in shadow mode, because the server skips observations whose joint positions match the last one, and a still arm always matches. Shadow mode is reliable for latency, but not for behavior that depends on the robot moving.

## Latency of the evaluation setup (native server, no fault)

From parts A and C at 0 ms, and the step 4 re-check:

| Measure | p50 | p99 | Mean |
|---|---|---|---|
| Control loop period | 33.4 ms | 33.5 ms | 33.35 to 33.37 ms |
| Chunk round trip | 74 to 76 ms | 89 to 121 ms | 72 to 79 ms |
| Server inference per chunk (excluding warm-up, from the round trip's server share) | 63 to 66 ms | not separable from warm-up in the snapshots | |
| Pause at each chunk boundary | | | about 2 steps (about 65 ms) |

## Sources

Session IDs are the UTC start time of each runner session. They match the trial-log entries and metrics snapshots kept locally under `outputs/` (gitignored, not in this repo).

| Run | Fault delay | Session ID |
|---|---|---|
| A1 | 0 ms | `20261024T204214Z` |
| A2 | 100 ms | `20261024T204419Z` |
| A3 | 200 ms | `20261024T204622Z` |
| A4 | 400 ms | `20261024T204912Z` |
| B1 | 400 ms, threshold 0.2 | `20261024T212645Z` |
| B2 | 400 ms, threshold 0.2 | `20261024T213000Z` |
| C1 | 0 ms, on the arm | `20261024T205218Z` |
| C2 | 200 ms, on the arm | `20261024T205624Z` |
| C3 | 200 ms, on the arm | `20261024T205846Z` |

Alert timings were read back from Prometheus's history.
