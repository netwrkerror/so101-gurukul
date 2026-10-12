# Decisions

Dated log of real choices and the reasons for them. Newest entry last.

## 2026-10-11: uv environment, LeRobot pinned to LeLab's commit

**Decision:** The repo environment is a uv project on Python 3.12 (`>=3.12,<3.13`). LeRobot is pinned to git commit `30da8e687a6dfc617fcd94afc367ac7071c376ce` (tag v0.6.0) with extras `core-scripts`, `feetech`, `training`. `pyproject.toml` and `uv.lock` are committed.

**Why:**

- LeLab was installed as a uv tool and resolved LeRobot to this commit with these extras. The arms were set up and calibrated through LeLab, so matching it keeps calibration and motor code identical between the two environments.
- A commit hash cannot move; a tag can.
- uv is already on the machine and writes a lockfile with hashes.
- Python is capped below 3.13 to match LeLab's interpreter (3.12.13).

**Locked versions:** torch 2.11.0, torchvision 0.26.0, torchcodec 0.11.1 on macOS arm64, identical to LeLab's. No extra constraints were needed. The lock also carries a Linux fork with torch 2.11.0+cu128 and torchvision 0.26.0+cu128 from the PyTorch cu128 index, which has not been installed or tested.

**Dropped:** conda and plain pip with a requirements file (no lock with hashes, a second tool to maintain).

**Notes:** This machine had an x86_64 Homebrew uv (0.11.21) ahead of the arm64 uv (0.12.0) on PATH, because Homebrew here is the Intel install under `/usr/local`. The Homebrew uv was uninstalled. `required-version = ">=0.12.0"` stays as a guard against an older uv building the environment.

**Known warning:** On macOS, `opencv-python-headless` and `av` each bundle `libavdevice`, so every LeRobot CLI call prints an `objc` duplicate-class warning. LeLab's environment has the same duplicate. Left as is to stay matched to LeLab; to be checked at the first camera test.
