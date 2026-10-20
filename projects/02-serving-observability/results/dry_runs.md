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
