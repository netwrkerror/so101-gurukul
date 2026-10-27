# Video scoring for project 03 step 3b: decodes untrusted public videos in isolation.
#
# Built from the repo's own uv.lock (as project 02's image), so the packages match the Mac.
# Debian 13 (trixie) for a newer FFmpeg with security updates (7.1; Debian 12 has 5.1).
# torchcodec loads the system FFmpeg; torch runs on CPU (no MPS inside Docker on a Mac).
#
# Build from the repo root:
#   docker build --platform linux/arm64 -f projects/03-ray-curation/Dockerfile -t gurukul-video-scoring:dev .
#
# Run with no network, a read-only root filesystem, and only these mounts (nothing else from
# the Mac is visible: not the home folder, .env, the Hugging Face token, or the repo):
#   docker run --rm --network none --read-only --tmpfs /tmp:size=4g --shm-size=4g --cpus 6 --memory 12g \
#     -e IMAGE_DIGEST="$(docker image inspect gurukul-video-scoring:dev --format '{{.Id}}')" \
#     -v "$PWD/outputs/p03_video:/data/video:ro" \
#     -v "$HOME/.cache/huggingface/lerobot/causalerror/so101-toy-to-bowl_20261017_130943:/data/ours:ro" \
#     -v "$HOME/.cache/torch/hub/checkpoints/resnet18-f37072fd.pth:/data/weights/resnet18-f37072fd.pth:ro" \
#     -v "$PWD/outputs/p03_video_scores:/data/out" \
#     gurukul-video-scoring:dev score --only-ours

FROM python:3.12-slim-trixie AS build

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


FROM python:3.12-slim-trixie

# FFmpeg's shared libraries for torchcodec; the ffmpeg binary only reports its version.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 gurukul
WORKDIR /app

# Same base image and path, so the environment's Python links stay valid.
COPY --from=build /app/.venv /app/.venv
COPY projects/03-ray-curation/src/score_video.py projects/03-ray-curation/src/score_video.py
COPY projects/03-ray-curation/configs/scoring_stage2.yaml projects/03-ray-curation/configs/scoring_stage2.yaml

USER gurukul
# torchcodec's CUDA 12.8 build loads NVIDIA's NPP, installed by uv under site-packages/nvidia/npp
# (see DECISIONS.md, 2026-10-26). torch preloads its own NVIDIA libraries but not this one.
ENV PATH="/app/.venv/bin:$PATH" \
    LD_LIBRARY_PATH=/app/.venv/lib/python3.12/site-packages/nvidia/npp/lib \
    HOME=/tmp
ENTRYPOINT ["python", "projects/03-ray-curation/src/score_video.py"]
CMD ["score", "--only-ours"]
