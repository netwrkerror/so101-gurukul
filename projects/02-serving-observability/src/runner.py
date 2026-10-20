"""Trial runner for evaluating a served policy on the follower arm.

Wraps LeRobot's async ``RobotClient`` (without editing it) and adds what evaluation
needs and the stock client lacks:

- trials in a fixed schedule, each with a time limit;
- the policy paused between trials, while the operator resets the toy;
- a smooth return to the start pose after every trial, and on any exit;
- Prometheus metrics for the control loop and the server round trip;
- a JSON-lines log of every trial.

Keys, read from the terminal (keep it focused), the same as ``lerobot-rollout``:
    n or Right arrow   start the next trial; during a trial, end it after a success
    r or Left arrow    during a trial, void it after a setup mistake and run it again
    q or Esc           stop the session (the arm returns to the start pose first)

Run from the repo root, with the policy server already running:
    uv run python projects/02-serving-observability/src/runner.py \
        --config_path=projects/02-serving-observability/configs/runner.json \
        --robot.port=<follower port> --robot.cameras="{...}"
"""

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from pprint import pformat
from queue import Queue

import draccus
from lerobot.async_inference.configs import RobotClientConfig
from lerobot.async_inference.helpers import TimedObservation
from lerobot.async_inference.robot_client import RobotClient
from lerobot.transport import services_pb2  # type: ignore
from lerobot.utils.keyboard_input import init_keyboard_listener
from lerobot.utils.robot_utils import precise_sleep

from metrics import ClientMetrics, save_snapshot, serve_metrics

DEFAULT_SCHEDULE = ["A", "B", "C"] * 6 + ["A", "B"]

# The server's Ready call replaces its observation queue. The client's chunk receiver may
# still be waiting on the old queue for up to the server's obs_queue_timeout (2 s by
# default), so wait that long before a trial's timer starts.
SERVER_RESET_SETTLE_S = 2.2


@dataclass
class RunnerConfig(RobotClientConfig):
    trial_time_s: float = 45.0
    return_time_s: float = 3.0
    schedule: list[str] = field(default_factory=lambda: list(DEFAULT_SCHEDULE))
    start_trial: int = 1
    trials_log: str = "outputs/p02_trials.jsonl"
    metrics_port: int = 9101
    # Connects everything and runs the trial loop, but never asks the policy for actions.
    dry_run: bool = False
    # Shadow mode: the policy predicts as usual (observations out, chunks back, actions
    # consumed at 30 Hz), but the actions are discarded instead of sent to the arm, which
    # holds still. Measures serving latency without moving the arm.
    shadow: bool = False


class TrialClient(RobotClient):
    """RobotClient with per-trial resets, a bounded control loop, and metrics."""

    def __init__(self, config: RunnerConfig, metrics: ClientMetrics):
        super().__init__(config)
        self.metrics = metrics
        self._chunk_requested_at: float | None = None

    # --- hooks into the stock client, for metrics -------------------------------

    def send_observation(self, obs: TimedObservation) -> bool:
        if obs.must_go:
            self._chunk_requested_at = time.perf_counter()
        sent = super().send_observation(obs)
        if not sent:
            self.metrics.grpc_errors.labels("SendObservations").inc()
        return sent

    def _aggregate_action_queues(self, incoming_actions, aggregate_fn=None):
        if self._chunk_requested_at is not None:
            self.metrics.chunk_round_trip.observe(time.perf_counter() - self._chunk_requested_at)
            self._chunk_requested_at = None
        self.metrics.chunks_received.inc()
        return super()._aggregate_action_queues(incoming_actions, aggregate_fn)

    # --- trials ------------------------------------------------------------------

    def reset_for_trial(self) -> None:
        """Forget the previous trial on both sides, so the next one starts fresh."""
        self.stub.Ready(services_pb2.Empty())  # resets the server's state; the policy stays loaded
        time.sleep(SERVER_RESET_SETTLE_S)
        with self.action_queue_lock:
            self.action_queue = Queue()
        with self.latest_action_lock:
            self.latest_action = -1
        self.must_go.set()
        self._chunk_requested_at = None

    def _send_from(self, raw_observation: dict) -> None:
        """Send an observation the loop has already read, as the stock client would.

        Mirrors ``RobotClient.control_loop_observation``, except that the observation is
        read once per step by ``run_trial`` (for metrics) instead of again here.
        """
        raw_observation = dict(raw_observation)
        raw_observation["task"] = self.config.task
        with self.latest_action_lock:
            latest_action = self.latest_action
        observation = TimedObservation(
            timestamp=time.time(),
            observation=raw_observation,
            timestep=max(latest_action, 0),
        )
        with self.action_queue_lock:
            observation.must_go = self.must_go.is_set() and self.action_queue.empty()
        self.send_observation(observation)
        if observation.must_go:
            self.must_go.clear()

    def discard_next_action(self) -> None:
        """Take the next action off the queue without sending it to the arm (shadow mode)."""
        with self.action_queue_lock:
            timed_action = self.action_queue.get_nowait()
        with self.latest_action_lock:
            self.latest_action = timed_action.get_timestep()

    def run_trial(self, duration_s: float, events: dict, dry_run: bool, shadow: bool = False) -> None:
        """The stock control loop, bounded by a time limit and the operator's keys."""
        dt = self.config.environment_dt
        deadline = time.perf_counter() + duration_s
        last_command: dict | None = None
        previous_start: float | None = None

        while time.perf_counter() < deadline:
            if events["exit_early"] or events["rerecord_episode"] or events["stop_recording"]:
                break
            step_start = time.perf_counter()
            if previous_start is not None:
                self.metrics.loop_period.observe(step_start - previous_start)
            previous_start = step_start

            raw_observation = self.robot.get_observation()
            if last_command is not None:
                for key, commanded in last_command.items():
                    if key in raw_observation:
                        self.metrics.tracking_error.labels(key.removesuffix(".pos")).observe(
                            abs(commanded - raw_observation[key])
                        )

            if not dry_run:
                if self.actions_available():
                    if shadow:
                        self.discard_next_action()
                    else:
                        last_command = self.control_loop_action()
                else:
                    self.metrics.empty_queue_steps.inc()
                if self._ready_to_send_observation():
                    self._send_from(raw_observation)

            with self.action_queue_lock:
                self.metrics.queue_depth.set(self.action_queue.qsize())

            work = time.perf_counter() - step_start
            self.metrics.loop_work.observe(work)
            if work > dt:
                self.metrics.deadline_misses.inc()
            # Plain time.sleep overshoots by a few ms per step on macOS (measured: about 27 Hz
            # instead of 30). precise_sleep, as used by lerobot-rollout, holds 30 Hz.
            precise_sleep(max(0.0, dt - work))

    def current_positions(self) -> dict[str, float]:
        return {k: v for k, v in self.robot.get_observation().items() if k.endswith(".pos")}

    def return_to(self, target: dict[str, float], duration_s: float) -> None:
        """Move every joint in a straight line to ``target`` over ``duration_s`` seconds."""
        start = self.current_positions()
        steps = max(1, int(duration_s * self.config.fps))
        for i in range(1, steps + 1):
            fraction = i / steps
            self.robot.send_action({k: start[k] + (target[k] - start[k]) * fraction for k in target})
            precise_sleep(self.config.environment_dt)


def wait_for_start(events: dict) -> bool:
    """Wait for n (start) or q (quit). Returns False if the operator quit."""
    for key in ("exit_early", "rerecord_episode"):
        events[key] = False
    while True:
        if events["stop_recording"]:
            return False
        if events["exit_early"]:
            events["exit_early"] = False
            return True
        events["rerecord_episode"] = False  # r means nothing between trials
        time.sleep(0.05)


def log_trial(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


@draccus.wrap()
def main(cfg: RunnerConfig):
    logging.info(pformat(asdict(cfg)))
    metrics = ClientMetrics()
    serve_metrics(cfg.metrics_port)

    client = TrialClient(cfg, metrics)  # connects the follower and cameras
    if not client.start():  # connects to the server and has it load the policy
        client.robot.disconnect()
        raise SystemExit("Could not connect to the policy server. Is it running?")

    receiver = threading.Thread(target=client.receive_actions, daemon=True)
    receiver.start()
    client.start_barrier.wait()  # the stock receiver waits for the control loop at this barrier

    start_pose = client.current_positions()
    listener, events = init_keyboard_listener()
    log_path = Path(cfg.trials_log)
    session = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trial = cfg.start_trial

    print(f"\nSession {session}. Metrics: http://127.0.0.1:{cfg.metrics_port}/metrics")
    if cfg.dry_run:
        print("DRY RUN: the policy will not move the arm.")
    elif cfg.shadow:
        print("SHADOW: the policy predicts as usual, but its actions are discarded; the arm holds still.")

    try:
        while trial <= len(cfg.schedule):
            spot = cfg.schedule[trial - 1]
            print(f"\nTrial {trial}/{len(cfg.schedule)}, spot {spot}: place the toy, then press n to start (q to quit).")
            if not wait_for_start(events):
                break

            print("Resetting the server and client (about 2 s)...")
            client.reset_for_trial()
            started_at = datetime.now(timezone.utc).isoformat()
            t0 = time.perf_counter()
            metrics.trial_active.set(1)
            client.run_trial(cfg.trial_time_s, events, cfg.dry_run, cfg.shadow)
            metrics.trial_active.set(0)
            duration = time.perf_counter() - t0

            if events["stop_recording"]:
                ended_by = "quit"
            elif events["rerecord_episode"]:
                ended_by = "voided"
            elif events["exit_early"]:
                ended_by = "success"
            else:
                ended_by = "timeout"
            events["exit_early"] = False
            events["rerecord_episode"] = False

            print(f"Trial {trial} ended: {ended_by} after {duration:.1f} s. Returning to the start pose...")
            client.return_to(start_pose, cfg.return_time_s)

            metrics.trials.labels(ended_by).inc()
            log_trial(log_path, {
                "session": session,
                "trial": trial,
                "spot": spot,
                "started_at": started_at,
                "duration_s": round(duration, 2),
                "ended_by": ended_by,
                "dry_run": cfg.dry_run,
                "shadow": cfg.shadow,
            })

            if ended_by == "quit":
                break
            if ended_by != "voided":
                trial += 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        metrics.trial_active.set(0)
        try:
            print("Returning to the start pose before disconnecting...")
            client.return_to(start_pose, cfg.return_time_s)
        finally:
            client.stop()
            if listener is not None and hasattr(listener, "stop"):
                listener.stop()
        snapshot = log_path.parent / f"p02_client_metrics_{session}.prom"
        save_snapshot(snapshot)
        print(f"Session ended. Trials logged to {log_path}; metrics snapshot in {snapshot}.")


if __name__ == "__main__":
    main()
