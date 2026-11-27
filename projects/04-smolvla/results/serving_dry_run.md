# Serving dry run on the arm (step 5, part B)

Shadow sessions and practice trials through project 02's policy server and trial runner, with `configs/runner_smolvla.json` and `configs/runner_act.json` (git commit `6ea13a5`): early chunk requests at `chunk_size_threshold` 0.5, `latest_only` aggregation, project 01's speed cap. Date: 2026-11-26. None of these trials count toward the evaluation.

## Front camera view

Before the practice trials, the `front` camera was matched to the view of project 01's evaluation (its first front frame), not to training episode 0:

- **Why that reference:** the training recordings' front view varied between episodes (in episodes 22 and 44 the arm sits higher and the bowl further into the frame than in episode 0), while project 01's and project 03's evaluations used the same view. The comparison is with those evaluations.
- **How:** stills at 640x480 compared with the reference, then a live overlay of the camera on the reference. Final check: the arm, table edges, and bowl overlap within a few pixels. The bowl sits on its taped outline.
- An earlier comparison against training episode 0 suggested moving the bowl; against the evaluation view, the bowl's position relative to the arm matched, so it was not moved further.

## Shadow sessions (the arm holds still)

One 15-second trial per policy; the policy predicts as usual and its actions are discarded. Recorded locally only (`causalerror/p04_shadow_smolvla`, `causalerror/p04_shadow_act`, not pushed).

| | SmolVLA | ACT |
|---|---|---|
| Recording | 449 frames (15 s at 30 fps), both cameras | 449 frames, both cameras |
| Control loop | 30 Hz, 1 deadline miss | 30 Hz, 0 deadline misses |
| Warm-up chunk | 7.4 s (first SmolVLA load in this server) | 0.25 s |
| Chunk round trip, mean | 0.36 s (8 chunks) | 0.09 s (5 chunks) |
| Empty-queue steps | 83 of 449 | 10 of 449 |

With the arm still, the server skips observations that barely differ from the previous one, so early requests go unanswered and each chunk is fetched only when the queue is empty: the empty-queue steps here are expected and say nothing about early requests (as project 02 found). The first ACT start failed while connecting: the `front` camera gave no frame within LeRobot's 1-second start-up wait (`TimeoutError`, before any motion or recording); the second start worked.

## Practice trials (the arm moves)

Three trials per policy, one per spot, recorded and pushed to the Hub, private (`causalerror/p04_dryrun_smolvla`, `causalerror/p04_dryrun_act`). Outcomes and notes as reported by the operator.

| Policy | Trial, spot | Result | Duration | Operator's notes |
|---|---|---|---|---|
| SmolVLA | 1, A | Success | 20.9 s | Quick start; the hand shot to a position twice; jerky but quick; stopped a few seconds before releasing |
| SmolVLA | 2, B | Timeout | 45.0 s | Hesitated to lift; the hand shot to a position twice; almost grasped; a lot of jerky movement; could not extend the arm |
| SmolVLA | 3, C | Timeout | 45.0 s | Stiff, jerky movements; unable to grasp; tried several times |
| ACT | 1, A | Success | 22.4 s | A little slow releasing the toy into the bowl |
| ACT | 2, B | Success | 23.6 s | Extended the arm and wrist; slow releasing |
| ACT | 3, C | Timeout | 45.0 s | Lifted, dropped the toy in flight; tried grasping again several times |

Three trials per policy are far too few to compare success rates; they test serving.

### Serving (client metrics over each session)

| | SmolVLA | ACT |
|---|---|---|
| Control loop | 33.4 ms per step (30 Hz), 1 deadline miss in 3,316 steps | 33.4 ms (30 Hz), 1 in 2,721 |
| Loop work per step, mean (including recording) | 3.2 ms | 2.5 ms |
| Chunks received | 192, one every 0.58 s | 81, one every 1.12 s |
| Empty-queue steps | 70 of 3,316 (2.1%) | 9 of 2,721 (0.3%) |
| Chunks requested on an empty queue; their mean round trip | 6; 0.43 s | 3; 0.12 s |
| Warm-up chunk | 0.71 s | 0.26 s |

Early requests work on a moving arm: almost every chunk arrived before the queue ran out. The metrics do not record when the empty-queue steps happened. Recordings: 3,319 and 2,724 frames, matching the logged trial durations.

### Why SmolVLA was jerky

From the recorded actions (the action sent to the arm at each step):

| Policy, trial | Largest change between consecutive actions (body joints) | Steps with a change over 3 degrees |
|---|---|---|
| SmolVLA 1 | 63 degrees (elbow) | 11% |
| SmolVLA 2 | 71 degrees (shoulder lift) | 6% |
| SmolVLA 3 | 42 degrees (shoulder lift) | 8% |
| ACT 1 | 14 degrees | 7% |
| ACT 2 | 10 degrees | 6% |
| ACT 3 | 19 degrees | 7% |
| Training demonstrations (all 45) | 7 degrees | 9% |

The large SmolVLA jumps have one pattern. In trials 1 and 2 the arm starts moving, then a new chunk commands its rest pose for about 7 frames (the arm turns back), and the next chunk sends it forward again: the "hand shot to a position twice" in the notes. In trial 3 the arm jumped 42 degrees out of rest in one step.

SmolVLA, run on recorded rest frames with 16 noise seeds each (largest move in its first second; over 15 degrees counted as "go"):

| Frame (practice recording) | Joint state | "Go" predictions |
|---|---|---|
| Trial 2, 10.0 s, at rest | at rest | 0 of 16 |
| Trial 2, 11.0 s, at rest, same joint state | at rest | 8 of 16 (up to 40 degrees) |
| Trial 1, 2.2 s, just starting to move | near rest | 0 of 16 |
| Trial 3, 1.0 s, at rest | at rest | 16 of 16 (about 72 degrees) |

Near the rest pose, SmolVLA is unsure whether to wait or to go, and at some frames its random noise decides. The training data explains it: the demonstrations wait at rest for 0.3 to 4.0 seconds before moving (median 1.2 s). With early requests at 0.5, SmolVLA re-decides about every 0.6 s, so a new chunk can reverse a move that has started. ACT is deterministic, so its consecutive chunks do not flip. The offline metric (step 4) averages over all frames, where these few decision frames barely count.

Also seen: the arm's rest pose at the start of the practice trials differed from training's (elbow 94 to 98 degrees against 89, spread 2.5; in trial 1 the shoulder lift was at -110 against -101), but the flips also happen at a training-like pose (the trial 2 frames above).

## Lighting

Front-camera brightness at the start of each practice trial: 87 to 97 (SmolVLA 92 to 97, ACT 87 to 92), darker than project 01's evaluation (122 to 137) and project 03's (118 to 121). The counted session needs the evaluation lighting, checked by brightness before it starts.

## What this changes for step 6

See `DECISIONS.md` (2026-11-26): the arm evaluation adds a second serving setting for SmolVLA, `chunk_size_threshold` 0.25, alongside the planned 0.5, in one session.
