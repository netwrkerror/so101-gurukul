# Project 02: Serving and observability

Status: approved, 2026-10-19.

## Goal

Run project 01's ACT policy as a separate policy server that the robot client calls over gRPC, and make the whole control loop observable: live metrics from both sides in Prometheus, a Grafana dashboard, and a re-run of project 01's 20-trial evaluation through the served setup, so the cost of serving is measured, not assumed.

## Why it matters

Real robot deployments rarely run the model inside the control loop. A policy server holds the model (often on a GPU elsewhere), and a lightweight client next to the robot keeps the control loop running at a fixed rate. That split adds a network hop, queues, and timing failures that do not exist in a single process. Observing them (loop rate, deadline misses, queue depth, inference and round-trip latency) is how robotics and ML platform teams keep a fleet healthy and debug a policy that "works in the lab".

This project covers the real-time control case: one robot, one server, one machine. Evaluating policies at scale, with many simulated robots as clients of the same kind of server, is a follow-on (see "Out of scope / later").

## Steps

Ordered, each one branch and PR. Steps 2 and 6 move the arm.

| # | Step | Branch | Done when |
|---|---|---|---|
| 1 | Async inference setup: add LeRobot's gRPC extra to the environment, run `policy_server` and `robot_client` natively on the Mac (localhost, `mps`) with the project 01 model | `p02/async-setup` | Environment change and `DECISIONS.md` entry merged; a 2-trial dry run completes through the server; client settings chosen to stay as close as possible to project 01's synchronous chunk execution |
| 2 | Container for the policy server | `p02/container` | A committed Dockerfile builds and serves the policy on CPU; a dry run works with the client on the host. Decide (with measurements) whether evaluation uses the native or the containerized server |
| 3 | Client runner and metrics | `p02/metrics` | A runner in `src/` wraps LeRobot's `RobotClient` (without editing LeRobot's code) and adds what evaluation needs and the stock client lacks: trials with a 45-second limit, a safe return to the start pose, reset time, and recording if feasible. Client and server export metrics (list below) with `prometheus_client`; overhead measured in the control loop |
| 4 | Prometheus and Grafana | `p02/dashboards` | Docker Compose runs Prometheus and Grafana locally; the dashboard (committed as JSON) shows every metric live during a dry run; one or two alert rules (for example, control rate below target) |
| 5 | Latency and load characterisation | `p02/latency` | Without counting successes: measured loop period, round-trip latency, and inference time (p50, p99) for the chosen setup, plus at least one deliberate fault (for example, added server delay) and what the dashboard and the arm do |
| 6 | Evaluation through the served setup | `p02/eval` | 20 trials logged in `results/` under project 01's protocol, compared with project 01's 10/20 |
| 7 | Write-up | `p02/writeup` | README and the results summary match the logs |

Metrics, proposed:

- Client: control loop period and deadline misses; action queue depth; time from chunk request to chunk received; age of the camera frames used; commanded versus measured joint position (tracking error); gRPC errors and reconnects; trial outcomes.
- Server: observations received; inference time per chunk; queue wait; observation payload size; errors.

## Definition of done

- The dashboard shows the metrics above live during an evaluation session.
- Latency is reported as p50 and p99 with the setup it was measured on.
- The 20-trial evaluation through the served setup is reported under project 01's protocol, with the result stated next to project 01's 10/20 and every difference in conditions listed.
- There is no success target: the point is to measure what serving costs. With 20 trials, only a large difference from 10/20 would be meaningful, and the write-up says so.

Evaluation protocol, unchanged from project 01:

- Same policy (`causalerror/act-so101-toy-to-bowl` at revision `2ecffdd…`, converted for LeRobot 0.6.0), same task string, the same three spots and fixed bowl, `wrist` and `front` cameras at 640x480 and 30 fps, 45-second limit, 7/7/6 trials in the same A, B, C order, the same failure types and arrow-key rules.
- Same lighting as project 01's evaluation (blinds closed, evening or room light), so that serving is the main change.

## Inputs and outputs

- Inputs:
  - The project 01 policy and its converted local copy; the project 01 dataset (for offline checks).
  - `guru` and `shishya`, calibration ID `gurukul`; both cameras.
  - LeRobot 0.6.0's `async_inference` module (`policy_server`, `robot_client`).
- Outputs:
  - Committed: server and client launch configs, the instrumentation code in `src/`, the Dockerfile, Docker Compose for Prometheus and Grafana, the dashboard JSON, alert rules.
  - `results/`: latency measurements, the fault experiment, the evaluation log, and a summary.
  - If trial recordings are possible with the served setup, a private Hub dataset; otherwise noted.

## Risks and unknowns

- Async inference is not the same control scheme as project 01's synchronous rollout: the client requests chunks early and blends overlapping ones. If the closest settings still differ, the comparison with 10/20 has two changes, serving and chunk handling, and the write-up has to say which.
- Docker on macOS has no access to the Apple GPU, so a containerized server runs ACT on the CPU (about 124 ms per network step, measured in project 01, against 24 ms on `mps`).
- LeRobot's async inference passes observations and actions with Python `pickle` over gRPC. Unpickling untrusted data can run arbitrary code, so the server binds to localhost only, and no remote access is added in this project.
- `robot_client` may not record trials to a dataset the way `lerobot-rollout` does. If not, evidence for each trial needs another route (for example, a separate camera recording), or the gap is noted.
- Instrumentation inside a 30 Hz loop has a cost; it is measured in step 3 and kept off the critical path where possible.
- The gRPC extra must resolve against the existing lock without changing LeRobot or torch versions; checked in step 1.
- Lighting: project 01's evaluation ran in evening light with the blinds closed. Matching it is part of the protocol.

## Out of scope / later

- Kubernetes: deploying the policy server to a local cluster (kind or minikube).
- OpenTelemetry traces (for example to Grafana Tempo or Jaeger), following one observation through client and server. Metrics start with `prometheus_client` by choice, so adding traces means adding OpenTelemetry instrumentation then (see `DECISIONS.md`).
- Evaluation at scale in simulation: many simulated robots (LeRobot's optional `aloha`, `pusht`, `libero`, or `metaworld` environments) as clients of the policy server, orchestrated with Ray, building on project 03.
- Running the server on another machine or in the cloud, with real network latency.
- Authentication and TLS for gRPC, and replacing `pickle` with a safe serialisation format.
- Serving several robots from one server, and serving SmolVLA or other larger policies.
- Re-evaluating project 01 in the recording's daylight.
