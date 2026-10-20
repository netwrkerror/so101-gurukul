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
from pprint import pformat

import draccus
import grpc
from lerobot.async_inference.configs import PolicyServerConfig
from lerobot.async_inference.policy_server import PolicyServer
from lerobot.transport import services_pb2_grpc  # type: ignore

from metrics import ServerMetrics, serve_metrics


@dataclass
class InstrumentedServerConfig(PolicyServerConfig):
    metrics_port: int = 9102


class InstrumentedPolicyServer(PolicyServer):
    def __init__(self, config: PolicyServerConfig, metrics: ServerMetrics):
        super().__init__(config)
        self.metrics = metrics

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
    serve_metrics(cfg.metrics_port)

    policy_server = InstrumentedPolicyServer(cfg, metrics)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    services_pb2_grpc.add_AsyncInferenceServicer_to_server(policy_server, server)
    server.add_insecure_port(f"{cfg.host}:{cfg.port}")

    policy_server.logger.info(
        f"PolicyServer started on {cfg.host}:{cfg.port}; metrics on 127.0.0.1:{cfg.metrics_port}/metrics"
    )
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=1)
    policy_server.logger.info("Server terminated")


if __name__ == "__main__":
    main()
