"""Prometheus metrics for the project 02 policy server and robot client.

Each process exposes its metrics over HTTP on localhost for Prometheus to scrape:
the client on port 9101 and the server on port 9102 by default.
"""

from pathlib import Path

from prometheus_client import Counter, Gauge, Histogram, generate_latest, start_http_server

# Control-loop timings cluster around 1/30 s, so the buckets are dense there.
LOOP_BUCKETS = (0.010, 0.020, 0.025, 0.030, 0.0333, 0.036, 0.040, 0.050, 0.075, 0.100, 0.200, 0.500)
WORK_BUCKETS = (0.001, 0.002, 0.005, 0.010, 0.020, 0.0333, 0.050, 0.100, 0.200)
LATENCY_BUCKETS = (0.010, 0.020, 0.030, 0.040, 0.050, 0.075, 0.100, 0.150, 0.200, 0.300, 0.500, 1.0, 2.0)
TRACKING_BUCKETS = (0.5, 1, 2, 5, 10, 20, 45, 90)
PAYLOAD_BUCKETS = (1e4, 1e5, 2.5e5, 5e5, 1e6, 2e6, 4e6)


class ClientMetrics:
    def __init__(self) -> None:
        self.loop_period = Histogram(
            "gurukul_client_loop_period_seconds",
            "Time from the start of one control step to the start of the next (target 1/30 s)",
            buckets=LOOP_BUCKETS,
        )
        self.loop_work = Histogram(
            "gurukul_client_loop_work_seconds",
            "Time spent working in one control step, before sleeping to keep the rate",
            buckets=WORK_BUCKETS,
        )
        self.deadline_misses = Counter(
            "gurukul_client_deadline_misses_total",
            "Control steps whose work took longer than one control period",
        )
        self.queue_depth = Gauge(
            "gurukul_client_action_queue_depth",
            "Actions waiting in the client's queue",
        )
        self.empty_queue_steps = Counter(
            "gurukul_client_empty_queue_steps_total",
            "Control steps during a trial with no action to send (the arm waits for a chunk)",
        )
        self.chunk_round_trip = Histogram(
            "gurukul_client_chunk_round_trip_seconds",
            "Time from sending an observation that requires a new chunk to receiving that chunk",
            buckets=LATENCY_BUCKETS,
        )
        self.chunks_received = Counter(
            "gurukul_client_chunks_received_total",
            "Action chunks received from the policy server",
        )
        self.tracking_error = Histogram(
            "gurukul_client_tracking_error",
            "Absolute difference between the commanded position and the position measured one step later, "
            "per joint (degrees for arm joints, 0 to 100 scale for the gripper)",
            ["joint"],
            buckets=TRACKING_BUCKETS,
        )
        self.grpc_errors = Counter(
            "gurukul_client_grpc_errors_total",
            "Failed gRPC calls from the client",
            ["call"],
        )
        self.trial_active = Gauge(
            "gurukul_trial_active",
            "1 while a trial is running, 0 otherwise",
        )
        self.trials = Counter(
            "gurukul_trials_total",
            "Finished trials by how they ended: success (n key), timeout, voided (r key), or quit (q key)",
            ["ended_by"],
        )


class ServerMetrics:
    def __init__(self) -> None:
        self.inference = Histogram(
            "gurukul_server_inference_seconds",
            "Time to predict one action chunk, including pre- and post-processing",
            buckets=LATENCY_BUCKETS,
        )
        self.observations = Counter(
            "gurukul_server_observations_total",
            "Observations received, by whether they were queued for inference or skipped",
            ["result"],
        )
        self.payload = Histogram(
            "gurukul_server_observation_bytes",
            "Size of one serialised observation received by the server",
            buckets=PAYLOAD_BUCKETS,
        )
        self.errors = Counter(
            "gurukul_server_errors_total",
            "Errors raised while handling a request",
            ["call"],
        )


def serve_metrics(port: int) -> None:
    """Expose this process's metrics on localhost only."""
    start_http_server(port, addr="127.0.0.1")


def save_snapshot(path: Path) -> None:
    """Write the current value of every metric, in Prometheus text format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(generate_latest())
