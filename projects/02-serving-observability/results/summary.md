# Project 02 summary: serving and observing a robot policy

**Result: 9/20 through the served setup, against 10/20 with the policy running in-process** (project 01). Same ACT policy and checkpoint, task (a stuffed toy from three marked spots into a fixed bowl), cameras, lighting, and 45-second limit. A difference of one trial in 20 is within chance: serving did not measurably change the success rate. The serving path held the 30 Hz control loop with no deadline misses, a 72 ms mean chunk round trip, and about 65 ms of pause at each chunk boundary.

This page summarises the project. The detailed records are linked in each section.

## What was built

Project 01's policy, moved out of the control loop and made observable:

```
trial runner ──controls──▶ RobotClient ──gRPC (localhost)──▶ policy server (ACT on mps)
     │                          │                                   │
     │                          └──actions──▶ follower arm           │
     └──── metrics ─────────────────────────────────────────────────┴──▶ Prometheus ──▶ Grafana
```

| Piece | What it is | Where |
|---|---|---|
| Policy server | LeRobot 0.6.0's async-inference `PolicyServer`, subclassed to add Prometheus metrics, a fault-injection delay, and a metrics snapshot on shutdown | `src/server.py` |
| Trial runner | Wraps LeRobot's `RobotClient` (unmodified) with trials, a time limit, the policy paused between trials, a safe return to the start pose, a warm-up request, shadow mode, and a trial log | `src/runner.py` |
| Metrics | Control loop period and work, deadline misses, queue depth, waiting steps, chunk round trip, tracking error per joint, inference time, observations used and skipped | `src/metrics.py` |
| Container | The policy server as a Linux image, built from the repo's own lock file | `Dockerfile` |
| Observability stack | Prometheus and Grafana with Docker Compose; a 17-panel dashboard and two alert rules | `observability/` |

Decisions and the reasons for them are in [`DECISIONS.md`](../../../DECISIONS.md).

## Why a policy server

The computer next to a robot is often too small for the model, so real deployments run the model on a GPU server and keep a small client next to the robot that holds a fixed control rate. ACT's action chunks make that work: the robot plays out a chunk of 100 actions (about 3.3 seconds) while the next one is requested. The cost is a network hop inside the control loop, and new ways to fail: late chunks, an empty action queue, a server that is slow or down. This project measures those costs on one robot and one machine.

## Numbers

**Evaluation** ([`evaluation.md`](evaluation.md)):

| | Project 01 (in-process) | Project 02 (served) |
|---|---|---|
| Successes | 10/20 (A 4/7, B 3/7, C 3/6) | 9/20 (A 5/7, B 3/7, C 1/6) |
| Grasp missed | 6 | 8 |
| Missed the bowl | 2 | 2 |
| Did not release | 2 | 0 |
| Pause at each chunk boundary | about 51 ms | about 65 ms |

**Latency of the served setup**, native server on `mps` ([`latency_and_faults.md`](latency_and_faults.md), [`evaluation.md`](evaluation.md)):

| Measure | Value |
|---|---|
| Control loop period | mean 33.36 ms, p99 33.5 ms (30 Hz), 0 deadline misses |
| Chunk round trip | mean 72 ms, p50 73 ms, p99 94 ms |
| Server inference per chunk | p50 63 ms |
| One observation over gRPC | 1.84 MB (two raw camera images) |

**Native against containerized server**, shadow mode ([`latency_native_vs_container.md`](latency_native_vs_container.md)):

| | Native (`mps`) | Container (CPU) |
|---|---|---|
| Inference per chunk, mean | 88 ms (including a cold start) | 344 ms |
| Pause per chunk | about 90 ms | about 360 ms |
| Image size | | 7.69 GB |

Docker on macOS cannot use the Apple GPU, so the container runs on the CPU. The evaluation used the native server.

**A slow server, injected on purpose** ([`latency_and_faults.md`](latency_and_faults.md)):

| Injected delay | Round trip, mean | Pause per chunk | Alert |
|---|---|---|---|
| 0 ms | 79 ms | 2.0 steps | none |
| 100 ms | 172 ms | 4.4 steps | none |
| 200 ms | 271 ms | 7.6 steps | briefly, at its threshold |
| 400 ms | 470 ms | 13.6 steps | `ChunkRoundTripHigh` |

The control loop held 30 Hz with no deadline misses at every delay.

## What the measurements showed

- **Serving latency passes straight through to the arm.** With the client asking for a new chunk only when its queue is empty (chosen to match project 01's chunk handling), every millisecond of server latency becomes a longer pause at each chunk boundary. A slow server does not slow the control loop; it makes the arm wait.
- **Serving did not measurably change success at this latency.** 9/20 against 10/20, with the served setup adding about 15 ms of pause per chunk boundary. On the arm, pauses of about a quarter of a second (a 200 ms injected delay) still let 3 of 4 informal trials succeed.
- **Missed grasps remain the main failure**, as in project 01, often after the arm pushed the toy off its spot. In two evaluation trials the policy recovered a pushed toy, which it never did in project 01; with so few trials that is an observation, not a measured difference. Spot C fell to 1/6; the metrics show spot C trials were served no differently, so if the drop is real it comes from the policy.
- **The cold start is real.** The first chunk after the server loads the policy took about 0.35 to 0.8 s. A warm-up request before the first trial keeps it out of every trial.

## Lessons from building it

- **`time.sleep` overshoots on macOS.** The first runner, copying LeRobot's stock client, ran at about 27 Hz instead of 30 because each sleep overshot by a few milliseconds. LeRobot's own `precise_sleep` (sleep, then spin for the last few milliseconds) fixed it.
- **The stock async client is a demo, not an evaluation tool.** It has no trials, time limit, or reset phase, and cuts motor power when stopped; in a first dry run a stuck policy repeated the same motion six times. The runner adds what is missing without editing LeRobot.
- **The stock client floods the server while waiting.** With its queue empty, it sends a 1.8 MB observation on every control step; the server uses the first and skips the rest. In one 45-second session with a slow server that was 162 skipped observations.
- **Shadow mode has a blind spot.** Running the policy with its actions discarded is a safe way to measure latency, but LeRobot's server skips observations whose joint positions match the last one, and a still arm always matches. So shadow mode could not test the standard mitigation for slow servers, asking for the next chunk early.
- **Alert on what the arm experiences.** A round-trip alert measures latency, not its effect: with a mitigation that requests chunks early, latency could be hidden from the arm while the alert still fires. The steps spent waiting with an empty queue measure what actually affects the motion. (This follows from how the client works; it was not demonstrated, because the mitigation could not be tested in shadow mode.) Two alert rules also needed guards against false alarms at trial starts and from a single slow chunk.
- **Percentiles come from buckets.** With histogram buckets at 33.3 and 36 ms, Prometheus reported a p50 loop period of about 34.7 ms for a true mean of 33.4 ms. Finer buckets near the target, plus an exact mean, fixed it.

## Limitations

- One evaluation of 20 trials per project: only a large difference would be meaningful.
- 13 attempts were voided and re-run as setup mistakes, classified after the session without video; 4 of them preceded counted successes.
- The served evaluation has no trial recordings (deferred), and failure types come from notes written after the session.
- One robot, one server, one machine: no real network latency, no load from several robots.

## What would come next

- Test the early-request mitigation (`chunk_size_threshold` above 0) on the arm with a slow server.
- Serve over a real network, or from a GPU machine using the same container image with CUDA.
- Send one observation per chunk request, and compress the camera images.
- OpenTelemetry traces through client and server; Kubernetes deployment of the server.
- Evaluation at scale in simulation, with many simulated robots as clients, building on project 03 (Ray).

## Reproducing

From the repo root, after the setup in the [README](../../../README.md):

1. Observability stack: `docker compose -f projects/02-serving-observability/observability/docker-compose.yml --env-file .env up -d` (needs `GRAFANA_ADMIN_PASSWORD` in `.env`).
2. Policy server: `uv run python projects/02-serving-observability/src/server.py --config_path=projects/02-serving-observability/configs/policy_server.json`
3. Trial runner: `uv run python projects/02-serving-observability/src/runner.py --config_path=projects/02-serving-observability/configs/runner.json`, plus the follower's port and camera indexes on the command line. Add `--shadow=true` to run the policy without moving the arm.

The policy is project 01's private checkpoint, converted for LeRobot 0.6.0 (see project 01's `results/training_runs.md`), so step 3 currently works only from the owner's account.
