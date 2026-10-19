# Project 01: Baseline ACT

Status: complete, 2026-10-18. Result: 10/20, which meets the success target. See `results/summary.md`.

## Goal

An ACT policy, trained on my own teleoperated demonstrations, that makes `shishya` (follower) pick up a stuffed toy from one of three marked spots and drop it into a bowl without anyone touching `guru` (leader). The project ends with a measured success rate over a fixed set of trials, a private dataset and checkpoint on the Hub, and a written account of what failed.

## Why it matters

This is the smallest complete loop of a physical AI stack: data collection, training, and evaluation on real hardware. Every later project builds on it. Project 02 serves and observes the policy trained here, and project 03 curates the kind of dataset recorded here.

## Steps

Ordered, each one branch and PR. Steps 2, 3, 4, and 6 move the arm.

| # | Step | Branch | Done when |
|---|---|---|---|
| 1 | Workspace and camera setup: fixed `front` mount, three toy spots (A, B, C) and the bowl position marked | `p01/workspace` | Both cameras measure about 30 fps at 640x480; the marks match the recorded episodes; a reference still is kept locally; placement is in `DECISIONS.md` |
| 2 | Teleoperation from this repo with the LeRobot CLI and both cameras | `p01/teleop` | `shishya` mirrors `guru` using calibration ID `gurukul`; both feeds are visible; the command is documented. Needed before step 6, which runs from this repo |
| 3 | Record the dataset | `p01/record-dataset` | Recorded in LeLab: 45 episodes, 15 per spot, in a private Hub dataset. The LeLab settings used are written to a committed file; camera frames have been reviewed |
| 4 | Inspect the dataset | `p01/inspect-dataset` | Every episode has been viewed; one has been replayed on `shishya`; the episode-to-spot mapping and any bad episodes are listed in `results/` |
| 5 | Train ACT on `mps` | `p01/train-act` | A short smoke run completes; the full-run checkpoint is on the Hub (private) with config, seed, git commit, and dataset revision recorded |
| 6 | Evaluate on the arm | `p01/eval` | Every trial is logged in `results/` with its spot, outcome, and a failure note where it failed |
| 7 | Write-up | `p01/writeup` | README and the results summary match the logs |

## Definition of done

The project is done when the success rate has been measured and reported under the protocol below.

Success target: 10/20 or better.

- If the first evaluation reaches the target, the project closes.
- If it falls short, there is one improvement round: diagnose from the logged failures, make one change (for example, re-record bad episodes or add more), retrain, and evaluate again under the same protocol. The project then closes with both results reported, whether or not the second one reaches the target.
- Every evaluation is reported, including the ones below target.

Evaluation protocol:

- Task: pick up the stuffed toy from a marked spot and drop it into the bowl.
- Task string, used exactly as recorded: `Pick up the stuffed toy and place it in the bowl`
- Trials: 20, run in one session with one checkpoint, chosen before the session (the final checkpoint from training).
- Spots: 7 trials at A, 7 at B, 6 at C. The trial order cycles A, B, C and is written down before the session starts.
- Start of each trial: `shishya` in its rest pose; the toy placed by hand on the marked spot, as close as possible to how it was placed during recording.
- Success: the toy is fully inside the bowl and released within 45 seconds, with no human contact with either arm. 45 seconds matches the recording episode limit.
- Each failed trial is logged as one of: grasp missed, dropped during carry, missed the bowl, timed out, or other (with a note).
- Dry runs to check the setup are allowed, logged as dry runs, and not counted.
- Held fixed between recording and evaluation: both camera positions, lighting, bowl position, the three spots, the toy, and the calibration files.
- Reported as: successes out of trials overall and per spot, with the conditions, for example "14/20 (A 5/7, B 5/7, C 4/6), toy on marked spots, `wrist` and `front` cameras, bowl fixed".

## Inputs and outputs

- Inputs:
  - `guru` and `shishya`, calibrated through LeLab, calibration ID `gurukul`. LeLab teleoperation without cameras passed every check (direction, range, gripper, no jitter).
  - Cameras: `wrist` (Seeed, on the gripper) and `front` (Logitech, fixed), both 640x480 at 30 fps.
  - The repo's uv environment: LeRobot 0.6.0 at the pinned commit.
  - Hugging Face account: `causalerror`.
- Outputs:
  - Private Hub dataset: `causalerror/so101-toy-to-bowl` (recorded as `so101-toy-to-bowl_20261017_130943` and renamed on the Hub). 45 episodes, 25,876 frames, 30 fps, one task. Episodes by spot: A is 0-13 and 44, B is 14-28, C is 29-43 (15 each).
  - Private Hub model (ACT checkpoint): `causalerror/act-so101-toy-to-bowl` (proposed name).
  - `results/`: episode-to-spot mapping, evaluation log, failure notes, and a summary.

## Risks and unknowns

- The dataset was recorded in LeLab, so its settings are not in git. They must be written down from LeLab before they are forgotten.
- The toy starts from only three spots. The policy is not expected to work from anywhere else, and evaluation is limited to those spots.
- A stuffed toy lies a little differently each time it is put down, which may make grasps less consistent.
- 20 trials give a wide margin of error: 10/20 is consistent with a true success rate anywhere from about 30% to 70%. Small differences between two evaluations are not meaningful.
- If a camera is bumped or the lighting changes between recording and evaluation, the comparison is no longer like for like. Keep the reference still and compare before each session.
- Camera indexes can change when a camera is replugged. Check before every session.
- Camera frame rate was measured with one camera open at a time and the arms idle; LeLab recorded with both cameras and arms, but dropped frames have not been checked yet.
- Calibration files live outside the repo. Recalibrating now may make the dataset and the arm disagree. Do not recalibrate mid-project; if it happens, log it.
- Every LeRobot command prints an `objc` duplicate-class warning (`opencv-python-headless` and `av` both bundle `libavdevice`). Not yet checked with cameras running through LeRobot.
- Training reads the videos back through torchcodec, which needs a system FFmpeg between versions 4 and 8. Resolved on 2026-10-17: FFmpeg 8 installed from Apple Silicon Homebrew, see `DECISIONS.md` and the README setup.
- ACT training time and memory use on `mps` with 24 GB are unknown. If an operation is unsupported on `mps`, or the run is too slow, the fallback is a smaller image size or batch size, logged in `DECISIONS.md`.

## Out of scope / later

- Serving and observability (project 02).
- Dataset curation with Ray (project 03).
- SmolVLA or any cloud training.
- Comparing policies or sweeping hyperparameters.
- Varying the bowl position, toy starting spots other than A, B, and C, or using more than one object.
- A puzzle cube as the task object (tried and found harder to grasp; see `DECISIONS.md`).
