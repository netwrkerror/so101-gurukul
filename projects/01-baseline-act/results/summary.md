# Project 01 summary: a baseline ACT policy on an SO-ARM101

**Result: 10/20 successes on the real arm.** Task: pick up a stuffed toy from one of three marked spots and drop it into a bowl at a fixed position. Two cameras (`wrist` on the gripper, `front` fixed), 45-second limit per trial, one checkpoint chosen before evaluation. Evaluated in room lighting with the blinds closed, which differed from the daylight during recording.

This page summarises the project. The detailed records are linked in each section.

## What was built

An end-to-end imitation-learning loop on a low-cost arm:

1. **Teleoperated demonstrations.** The leader arm (`guru`) is moved by hand, and the follower (`shishya`) copies it while both cameras and the joint positions are recorded.
2. **A dataset.** 45 episodes, 15 per start spot, 25,876 frames at 30 fps, on the Hugging Face Hub as `causalerror/so101-toy-to-bowl` (private), revision `c6319da…`.
3. **A trained policy.** ACT (Action Chunking Transformer, 52M parameters), which maps the two camera images and the six joint positions to the next 100 joint targets. Trained for 100,000 steps on Hugging Face Jobs.
4. **A fixed evaluation.** 20 trials on the real arm, in an order written down before the session, with every trial recorded.

## Pipeline

| Stage | Tool | Record |
|---|---|---|
| Calibration and recording | LeLab (LeRobot 0.6.0) | `configs/record_lelab.yaml` |
| Dataset review | `lerobot-dataset-viz`, `lerobot-replay` | `results/dataset_inspection.md` |
| Training | `lerobot-train` on HF Jobs, `a10g-large` | `configs/train_act.json`, `results/training_runs.md` |
| Evaluation | `lerobot-rollout`, episodic mode | `configs/eval_act.json`, `results/evaluation.md` |

The environment is a uv project pinned to LeRobot commit `30da8e6` (0.6.0). Decisions and the reasons for them are in [`DECISIONS.md`](../../../DECISIONS.md).

## Numbers

**Data:** 45 episodes, 11.6 to 30.1 seconds each (mean 19.2). All 45 passed review, and replaying one on the follower reproduced the demonstrated motion.

**Training:**

| | Mac (M5 Pro, `mps`) | HF Jobs (A10G) |
|---|---|---|
| Seconds per step, batch 8 | 0.95 | 0.16 |
| 100,000 steps | about 26 hours (estimated) | about 4.5 hours, about $6.75 (actual) |

Batch 32 did not fit in the Mac's 24 GB of shared memory. Final training loss 0.067. On 30 recorded frames, the trained policy's predicted joint targets were within 0.8 to 1.9 degrees of the demonstrations on average. That shows it learned the demonstrations, not that it works on the arm.

**Evaluation:**

| Spot | Successes |
|---|---|
| A | 4/7 |
| B | 3/7 |
| C | 3/6 |
| Total | **10/20** |

Failures: 6 grasp missed, 2 missed the bowl, 2 carried the toy to the bowl without releasing it. Successful trials took 14 to 23 seconds.

## What failed, and why it matters

- **Grasping is the weak point.** Six of the ten failures never picked the toy up. In three, the policy pushed the toy off its spot and then could not recover. The demonstrations only ever show the toy on one of the three spots, so once it moves, the policy is somewhere it has no examples of. This is the standard weakness of imitation learning from a small dataset.
- **Releasing is a second weak point.** Twice the policy reached the bowl with the toy but never opened the gripper.
- **The comparison is not fully like for like.** The lighting at evaluation differed from recording, a deliberate choice recorded in `DECISIONS.md`. The policy may do better in matching light; that is untested.
- **20 trials is a small sample.** 10/20 is consistent with a true success rate of roughly 30% to 70%, and the per-spot differences are not meaningful.

## Lessons from the setup

Problems that cost time, and what fixed them:

- **The x86_64 Homebrew on an Apple Silicon Mac.** An Intel `uv` builds an environment without GPU support. Fixed by using the arm64 `uv` and pinning `required-version` in `pyproject.toml`.
- **torchcodec and FFmpeg.** LeRobot reads dataset videos with torchcodec, which needs a system FFmpeg between versions 4 and 8. Homebrew's default is now 9. Fixed with `ffmpeg@8` from the Apple Silicon Homebrew and `DYLD_FALLBACK_LIBRARY_PATH`.
- **macOS strips `DYLD_*` variables** when a protected binary such as `/usr/bin/time` launches a program, which broke the first training run. Fixed by using the shell's built-in `time`.
- **The cloud image runs a newer LeRobot (0.6.2).** Its checkpoints add a `dtype` field that 0.6.0 rejects. Fixed by pinning the image by digest and removing that one field before evaluation, after checking that a 0.6.2 checkpoint loads and predicts in 0.6.0.
- **A misleading warning.** `lerobot-rollout` reported "19.5 Hz" against a 30 Hz target. The warning measures one loop iteration, and the slow one is the step where ACT runs its network, once per 100-step chunk. Frame counts showed the loop kept 30 Hz.

## What would come next

- **Evaluate again in the recording's lighting,** to measure how much lighting cost.
- **Record recovery demonstrations:** episodes that start with the toy pushed off its spot. These target the main failure.
- **More varied starts:** more spots, or random placement within an area, so the policy sees more of the situations it can end up in.
- **Project 02:** serve this policy and add observability. **Project 03:** curate datasets like this one at scale with Ray.

## Reproducing

1. Set up the environment as described in the [README](../../../README.md), including FFmpeg 8.
2. Train: `uv run lerobot-train --config_path=projects/01-baseline-act/configs/train_act.json` (submits to HF Jobs; needs access to the dataset).
3. Convert the checkpoint for LeRobot 0.6.0 by removing `"dtype": null` from `config.json` (see `results/training_runs.md`, run 3).
4. Evaluate: `lerobot-rollout --config_path=projects/01-baseline-act/configs/eval_act.json`, with the follower's port and camera indexes on the command line (see `results/evaluation.md`).

The dataset and model are private, so steps 2 to 4 currently work only from the owner's account.
