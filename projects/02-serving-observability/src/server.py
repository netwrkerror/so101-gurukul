"""LeRobot's async policy server with Prometheus metrics.

Subclasses ``lerobot.async_inference.policy_server.PolicyServer`` without changing its
behaviour, and starts it the same way LeRobot's ``serve`` does.

Run from the repo root:
    uv run python projects/02-serving-observability/src/server.py \
        --config_path=projects/02-serving-observability/configs/policy_server.json
"""

import logging
import time
from concurrent import futures
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from pprint import pformat

import draccus
import grpc
from lerobot.async_inference.configs import PolicyServerConfig
from lerobot.async_inference.policy_server import PolicyServer
from lerobot.transport import services_pb2_grpc  # type: ignore

from metrics import ServerMetrics, save_snapshot, serve_metrics


@dataclass
class InstrumentedServerConfig(PolicyServerConfig):
    metrics_port: int = 9102
    metrics_host: str = "127.0.0.1"
    # Fault injection for step 5: extra seconds added to every chunk's inference, inside the
    # timed section, to simulate a slow server. 0 disables it.
    fault_delay_s: float = 0.0
    # Where a metrics snapshot is written when the server stops.
    snapshot_dir: str = "outputs"


class InstrumentedPolicyServer(PolicyServer):
    def __init__(self, config: InstrumentedServerConfig, metrics: ServerMetrics):
        super().__init__(config)
        self.metrics = metrics
        self.fault_delay_s = config.fault_delay_s
        self.metrics.fault_delay.set(self.fault_delay_s)

    def SendObservations(self, request_iterator, context):  # noqa: N802
        size = 0

        def counted(requests):
            nonlocal size
            for request in requests:
                size += len(getattr(request, "data", b""))
                yield request

        try:
            return super().SendObservations(counted(request_iterator), context)
        except Exception:
            self.metrics.errors.labels("SendObservations").inc()
            raise
        finally:
            if size:
                self.metrics.payload.observe(size)

    def _enqueue_observation(self, obs) -> bool:
        queued = super()._enqueue_observation(obs)
        self.metrics.observations.labels("queued" if queued else "skipped").inc()
        return queued

    def _predict_action_chunk(self, observation_t):
        start = time.perf_counter()
        try:
            if self.fault_delay_s > 0:
                time.sleep(self.fault_delay_s)
            return super()._predict_action_chunk(observation_t)
        except Exception:
            self.metrics.errors.labels("predict").inc()
            raise
        finally:
            self.metrics.inference.observe(time.perf_counter() - start)


@draccus.wrap()
def main(cfg: InstrumentedServerConfig):
    logging.info(pformat(asdict(cfg)))
    metrics = ServerMetrics()
    serve_metrics(cfg.metrics_port, cfg.metrics_host)

    policy_server = InstrumentedPolicyServer(cfg, metrics)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    services_pb2_grpc.add_AsyncInferenceServicer_to_server(policy_server, server)
    server.add_insecure_port(f"{cfg.host}:{cfg.port}")

    policy_server.logger.info(
        f"PolicyServer started on {cfg.host}:{cfg.port}; metrics on {cfg.metrics_host}:{cfg.metrics_port}/metrics"
    )
    if cfg.fault_delay_s > 0:
        policy_server.logger.warning(f"FAULT INJECTION: adding {cfg.fault_delay_s:.3f} s to every chunk's inference")
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=1)
    finally:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot = Path(cfg.snapshot_dir) / f"p02_server_metrics_{stamp}.prom"
        try:
            save_snapshot(snapshot)
            policy_server.logger.info(f"Metrics snapshot saved to {snapshot}")
        except OSError as e:  # for example, no writable outputs/ inside the container
            policy_server.logger.warning(f"Could not save metrics snapshot to {snapshot}: {e}")
    policy_server.logger.info("Server terminated")


if __name__ == "__main__":
    main()
