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

## 2026-10-17: Project 01 task, cameras, and the first dataset

**Decision:** Project 01's task is picking up a stuffed toy and dropping it into a bowl at a fixed position. The toy starts from one of three spots (A, B, C). The dataset is `causalerror/so101-toy-to-bowl` (private; LeLab named it `so101-toy-to-bowl_20261017_130943`, renamed on the Hub the same day): 45 episodes, 15 per spot, recorded in LeLab with two cameras, `wrist` (Seeed, on the gripper) and `front` (Logitech, fixed in front, raised and angled down), both 640x480 at 30 fps.

**Why:**

- A puzzle cube was the planned object, but it was hard to grasp reliably during practice. The soft toy is more forgiving of a slightly off grasp. Dropped: the puzzle cube.
- The bowl stays fixed so the policy only has to handle where the toy starts, not where to drop it. Varying the bowl is left for later.
- Three spots with 15 episodes each give even coverage, and evaluation uses the same spots.
- Two views: the wrist camera sees the grasp up close, and the fixed front camera sees where the toy, bowl, and arm are. The front camera was first at table height, seeing the table almost edge-on; it was raised and angled down, and a laptop screen and a framed photo were moved out of its view.
- Cameras are named by viewpoint, not device, because the names become the dataset's image keys (`observation.images.wrist`, `observation.images.front`).

**Deviation from plan:** The brief planned to record from this repo with a committed config. The dataset was recorded in LeLab instead, so its settings have to be written down separately (project 01, step 3).
