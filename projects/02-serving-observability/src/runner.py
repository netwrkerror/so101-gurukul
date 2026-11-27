"""Trial runner for evaluating a served policy on the follower arm.

Wraps LeRobot's async ``RobotClient`` (without editing it) and adds what evaluation
needs and the stock client lacks:

- trials in a fixed schedule, each with a time limit;
- the policy paused between trials, while the operator resets the toy;
- a smooth return to the start pose after every trial, and on any exit;
- Prometheus metrics for the control loop and the server round trip;
- a JSON-lines log of every trial;
- a recording of every trial (project 04), voided ones included: one episode per trial in a
  LeRobot dataset (both cameras, the joint state, and the action sent to the arm), pushed to
  the Hub as a private dataset when the session ends;
- a camera-name mapping (``rename_map``) passed to the server, which the stock client
  never sends (project 04: SmolVLA's camera slots are named camera1 to camera3).

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
from lerobot.datasets import LeRobotDataset
from lerobot.transport import services_pb2  # type: ignore
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, combine_feature_dicts, hw_to_dataset_features
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
    # Camera names to policy names, applied by the server's preprocessor, for example
    # {"observation.images.front": "observation.images.camera1"}. Empty: names unchanged.
    rename_map: dict[str, str] = field(default_factory=dict)
    # Record every trial to this new local dataset (it must not exist yet); None: no recording.
    record_repo_id: str | None = None
    # Push the recording to the Hub, always private, when the session ends.
    record_push: bool = True


class TrialClient(RobotClient):
    """RobotClient with per-trial resets, a bounded control loop, and metrics."""

    def __init__(self, config: RunnerConfig, metrics: ClientMetrics):
        super().__init__(config)
        # The stock client builds its policy settings without a rename_map; set it before
        # start() sends them to the server.
        self.policy_config.rename_map = dict(config.rename_map)
        self.metrics = metrics
        self._chunk_requested_at: float | None = None
        self._warming_up = False
        self.dataset: LeRobotDataset | None = None

    # --- hooks into the stock client, for metrics -------------------------------

    def send_observation(self, obs: TimedObservation) -> bool:
        if obs.must_go:
            self._chunk_requested_at = time.perf_counter()
        sent = super().send_observation(obs)
        if not sent:
            self.metrics.grpc_errors.labels("SendObservations").inc()
        return sent

    def _aggregate_action_queues(self, incoming_actions, aggregate_fn=None):
        if self._warming_up:  # the warm-up chunk is kept out of the round-trip metrics
            return super()._aggregate_action_queues(incoming_actions, aggregate_fn)
        if self._chunk_requested_at is not None:
            self.metrics.chunk_round_trip.observe(time.perf_counter() - self._chunk_requested_at)
            self._chunk_requested_at = None
        self.metrics.chunks_received.inc()
        return super()._aggregate_action_queues(incoming_actions, aggregate_fn)

    # --- trials ------------------------------------------------------------------

    def warm_up(self, timeout_s: float = 15.0) -> float | None:
        """Request one throwaway chunk, so no trial pays the cost of the first inference.

        The first chunk after the server loads the policy is slow (one-off GPU setup); in
        the step 4 shadow sessions it reached about 0.45 s natively and 0.9 s in the
        container. The chunk is discarded: the next reset_for_trial clears the queue.
        Returns the warm-up time in seconds, or None if no chunk arrived in time.
        """
        self._warming_up = True
        try:
            self.reset_for_trial()
            start = time.perf_counter()
            self._send_from(self.robot.get_observation())
            while time.perf_counter() - start < timeout_s:
                if self.actions_available():
                    elapsed = time.perf_counter() - start
                    self.metrics.warmup.set(elapsed)
                    return elapsed
                time.sleep(0.01)
            return None
        finally:
            self._warming_up = False
            self._chunk_requested_at = None

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

    def create_recording(self, repo_id: str) -> None:
        """A new local dataset for this session, recorded as lerobot-rollout records."""
        features = combine_feature_dicts(
            hw_to_dataset_features(self.robot.action_features, ACTION, use_video=True),
            hw_to_dataset_features(self.robot.observation_features, OBS_STR, use_video=True),
        )
        self.dataset = LeRobotDataset.create(
            repo_id,
            self.config.fps,
            features=features,
            robot_type=self.robot.name,
            use_videos=True,
            image_writer_threads=4 * len(self.robot.cameras),
            streaming_encoding=True,
        )

    def record_frame(self, raw_observation: dict, action: dict) -> None:
        if self.dataset is None:
            return
        features = self.dataset.features
        self.dataset.add_frame({
            **build_dataset_frame(features, raw_observation, prefix=OBS_STR),
            **build_dataset_frame(features, action, prefix=ACTION),
            "task": self.config.task,
        })

    def save_trial_recording(self) -> int | None:
        """Close the trial's episode; returns its index, or None if nothing was recorded."""
        if self.dataset is None or not self.dataset.has_pending_frames():
            return None
        index = self.dataset.num_episodes
        self.dataset.save_episode()
        return index

    def run_trial(self, duration_s: float, events: dict, dry_run: bool, shadow: bool = False) -> None:
        """The stock control loop, bounded by a time limit and the operator's keys."""
        dt = self.config.environment_dt
        deadline = time.perf_counter() + duration_s
        last_command: dict | None = None
        previous_start: float | None = None
        held: dict | None = None  # what the arm holds when no action is sent: the start of the trial

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

            if held is None:
                held = {k: v for k, v in raw_observation.items() if k.endswith(".pos")}

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

            # The action recorded is the one sent this step; on a step with none (empty queue,
            # shadow, dry run), the last one sent, which the arm holds.
            self.record_frame(raw_observation, last_command if last_command is not None else held)

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


def safe_save(client: TrialClient) -> int | None:
    """Save a trial cut short by an error, if possible; otherwise drop its frames."""
    try:
        return client.save_trial_recording()
    except Exception as e:
        print(f"Could not save the interrupted trial's recording: {e!r}")
        if client.dataset is not None:
            client.dataset.clear_episode_buffer()
        return None


def close_recording(client: TrialClient, cfg: RunnerConfig) -> None:
    """Finalize the session's recording, then push it to the Hub (private)."""
    if client.dataset is None:
        return
    if client.dataset.has_pending_frames():  # frames of a trial that was not saved
        safe_save(client)
    try:
        client.dataset.finalize()
    except Exception as e:
        print(f"Could not finalize the recording at {client.dataset.root}: {e!r}. Not pushed; kept locally.")
        return
    print(f"Recording: {client.dataset.num_episodes} episodes at {client.dataset.root}.")
    if cfg.record_push and client.dataset.num_episodes > 0:
        try:
            client.dataset.push_to_hub(private=True)
            print(f"Pushed to the Hub (private): {cfg.record_repo_id}")
        except Exception as e:
            print(f"Could not push the recording: {e!r}. It is kept locally; push it later.")


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
    if cfg.record_repo_id:
        try:
            client.create_recording(cfg.record_repo_id)  # fails if the dataset already exists locally
        except Exception:
            client.robot.disconnect()
            raise
        print(f"Recording every trial to {cfg.record_repo_id} ({client.dataset.root}).")
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
    else:
        if cfg.shadow:
            print("SHADOW: the policy predicts as usual, but its actions are discarded; the arm holds still.")
        print("Warming up the policy server (one throwaway chunk; the arm does not move)...")
        warmup_s = client.warm_up()
        print(f"Warm-up chunk took {warmup_s:.2f} s." if warmup_s is not None else "Warm-up chunk did not arrive within 15 s.")

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
            try:
                client.run_trial(cfg.trial_time_s, events, cfg.dry_run, cfg.shadow)
            except Exception as e:  # for example, the follower stopped answering
                metrics.trial_active.set(0)
                log_trial(log_path, {
                    "session": session, "trial": trial, "spot": spot, "started_at": started_at,
                    "duration_s": round(time.perf_counter() - t0, 2), "ended_by": f"error: {type(e).__name__}",
                    "dry_run": cfg.dry_run, "shadow": cfg.shadow, "recording": cfg.record_repo_id,
                    "episode_index": safe_save(client),
                })
                raise
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
            episode_index = client.save_trial_recording()
            if episode_index is not None:
                print(f"Saved as episode {episode_index} of {cfg.record_repo_id}.")

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
                "recording": cfg.record_repo_id,
                "episode_index": episode_index,
            })

            if ended_by == "quit":
                break
            if ended_by != "voided":
                trial += 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        metrics.trial_active.set(0)
        # Each step is guarded, so one failure (for example, a disconnected follower) does not
        # skip the others, and the recording is always closed.
        try:
            print("Returning to the start pose before disconnecting...")
            client.return_to(start_pose, cfg.return_time_s)
        except Exception as e:
            print(f"Could not return to the start pose: {e!r}")
        try:
            client.stop()
        except Exception as e:
            print(f"Could not stop the client cleanly: {e!r}")
        if listener is not None and hasattr(listener, "stop"):
            listener.stop()
        close_recording(client, cfg)
        snapshot = log_path.parent / f"p02_client_metrics_{session}.prom"
        save_snapshot(snapshot)
        print(f"Session ended. Trials logged to {log_path}; metrics snapshot in {snapshot}.")


if __name__ == "__main__":
    main()
