# so101-gurukul

Hands-on physical AI projects on a Seeed Studio SO-ARM101 Pro (leader and follower arms) using Hugging Face LeRobot. The aim is to work through the full loop on real hardware: data collection, training, evaluation, serving, and observability.

## Status

Project 01 has its first dataset: 45 teleoperated episodes of picking up a stuffed toy and dropping it into a bowl, recorded in LeLab. No policy has been trained or evaluated yet, and nothing has been run on the arms from this repo.

## Hardware

| Item | Value |
|---|---|
| Leader arm (black) | `guru` |
| Follower arm (white) | `shishya` |
| Dev machine | macOS |
| Local compute device | `mps` (Apple GPU) |

The setup as a whole is called gurukul.

## Setup

Requires [uv](https://docs.astral.sh/uv/) 0.12.0 or newer. On Apple Silicon it must be an arm64 build of uv, otherwise the environment is built without MPS support. macOS on Apple Silicon is the only platform this has been run on.

```sh
uv sync
```

This creates `.venv` with Python 3.12 and LeRobot 0.6.0, pinned to git commit `30da8e687a6dfc617fcd94afc367ac7071c376ce`, with the `core-scripts`, `feetech`, and `training` extras.

### FFmpeg 8 for reading datasets

LeRobot decodes dataset videos with torchcodec, which loads FFmpeg from the system. The pinned torchcodec (0.11.1) supports FFmpeg 4 to 8, and Homebrew's default `ffmpeg` is now version 9, so install FFmpeg 8 explicitly. It needs the Apple Silicon Homebrew in `/opt/homebrew`, not an Intel Homebrew in `/usr/local`:

```sh
brew install ffmpeg@8
```

`ffmpeg@8` is installed alongside any other FFmpeg and is not linked into the default locations. Point the library search at it, for example in `~/.zprofile`:

```sh
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/opt/ffmpeg@8/lib"
```

Check that torchcodec loads:

```sh
uv run python -c "import torchcodec.decoders; print('torchcodec ok')"
```

Recording does not need this: it encodes video through PyAV, which bundles its own FFmpeg.

Check the install:

```sh
uv run python -c "import platform, torch; from importlib.metadata import version; import lerobot; print(version('lerobot'), platform.machine(), torch.__version__, torch.backends.mps.is_available())"
```

Expected output on the dev machine:

```
0.6.0 arm64 2.11.0 True
```

On macOS, LeRobot commands print an `objc` warning about duplicate `AVFFrameReceiver` classes. It comes from two dependencies bundling the same FFmpeg library; see `DECISIONS.md`.

## Projects

| Project | Status |
|---|---|
| `projects/01-baseline-act` | Brief not written yet |
| `projects/02-serving-observability` | Not started |
| `projects/03-ray-curation` | Not started |

## Repo guide

- `CLAUDE.md`: working agreement for this repo, including the hardware and environment table.
- `DECISIONS.md`: dated log of choices and the reasons for them.
- `projects/<nn-name>/BRIEF.md`: the plan for each project.

Datasets, checkpoints, and run outputs are not committed. They live on the Hugging Face Hub.

## License

Apache License 2.0. See `LICENSE`.
