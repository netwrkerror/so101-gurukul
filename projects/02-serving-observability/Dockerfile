# Policy server for project 02 (LeRobot async inference with Prometheus metrics).
#
# Built from the repo's own uv.lock, so the container has the same packages as the Mac.
# On Linux the lock resolves torch to the CUDA 12.8 build: it runs on CPU when there is no
# GPU (Docker on macOS) and uses an NVIDIA GPU unchanged on a Linux GPU machine.
#
# Two stages: the build stage has the compiler (some packages, such as evdev, have no
# prebuilt Linux arm64 wheel and are compiled from source); the runtime image only gets
# the finished environment.
#
# Build from the repo root:
#   docker build --platform linux/arm64 -f projects/02-serving-observability/Dockerfile -t gurukul-policy-server:dev .
#
# Run, publishing the ports on the host's loopback only (the server unpickles what it receives):
#   docker run --rm -p 127.0.0.1:8080:8080 -p 127.0.0.1:9102:9102 \
#     -v "$PWD/outputs/act_final:/app/outputs/act_final:ro" gurukul-policy-server:dev

FROM python:3.12-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /uvx /bin/

# git: LeRobot is installed from a pinned git commit.
# build-essential, linux-libc-dev: compile packages without a prebuilt wheel (evdev).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential linux-libc-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project


FROM python:3.12-slim-bookworm

RUN useradd --create-home --uid 1000 gurukul
WORKDIR /app

# LeRobot's async inference writes log files to ./logs when its modules are imported.
RUN mkdir -p /app/logs && chown gurukul:gurukul /app/logs

# Same base image and path, so the environment's Python links stay valid.
COPY --from=build /app/.venv /app/.venv
COPY projects/02-serving-observability/src projects/02-serving-observability/src
COPY projects/02-serving-observability/configs projects/02-serving-observability/configs

USER gurukul
ENV PATH="/app/.venv/bin:$PATH"

# The model is not part of the image: mount it read-only at /app/outputs/act_final, the
# same relative path the client sends as pretrained_name_or_path.
EXPOSE 8080 9102
CMD ["python", "projects/02-serving-observability/src/server.py", \
     "--config_path=projects/02-serving-observability/configs/policy_server.json", \
     "--host=0.0.0.0", "--metrics_host=0.0.0.0"]
