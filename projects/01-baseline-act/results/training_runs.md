# Training runs: project 01

One section per run, including failed and aborted runs. Configs are in `../configs/`. Outputs stay local under `outputs/train/` (gitignored); final models go to the Hub, private.

Common to all runs unless stated:

- Dataset: `causalerror/so101-toy-to-bowl` at revision `c6319da870f16f94db98e029ca0f4f654d585970`, all 45 episodes.
- Policy: ACT with LeRobot 0.6.0 defaults (ResNet-18 backbone from ImageNet weights, chunk size 100).
- LeRobot commit: `30da8e687a6dfc617fcd94afc367ac7071c376ce`.
- Hardware: Apple Silicon Mac (M5 Pro, 24 GB unified memory), device `mps`.

## Run 1: GPU check (50 steps)

Purpose: confirm the pipeline runs end to end on `mps` (dataset download, video decoding, training steps, checkpoint saving) before any longer run. Not used for evaluation.

| Field | Value |
|---|---|
| Config | `configs/train_act_gpu_check.json` |
| Git commit | `bc3d72a` |
| Seed | 1000 |
| Steps, batch size | 50, 8 |
| Started, finished | 2026-10-17, about 19:36:15 to 19:37:23 MDT; 66 s for the training command |
| Device confirmed | `mps` in the logged config. A repeat of the same run, identical except for output folder `outputs/train/p01_act_gpu_check_1`, showed the training process at 97.3% GPU in Activity Monitor |
| Seconds per step | 0.95 s update time at steps 20 to 50 (about 1.05 steps/s, 8 to 9 samples/s); data loading 0.004 s per step. Step 10 was slower (1.79 s) because of start-up |
| Peak memory | 935 MB maximum resident memory for the process. This may not fully count GPU memory, which shares system memory on Apple Silicon |
| Loss at step 10 and step 50 | 43.0 and 5.90 (step 20: 13.3, step 30: 8.31, step 40: 6.59) |
| Checkpoint saved | Yes, `checkpoints/000050/`, about 590 MB including optimizer state |
| Outcome | Passed: dataset loaded (45 episodes, 25,876 frames), videos decoded, 50 steps trained on `mps`, loss fell steadily, checkpoint written |
| Notes | 52M learnable parameters. 50 steps at batch 8 is 400 samples, about 1.5% of one pass over the dataset |

Failed attempts:

- 2026-10-17, git commit `bc3d72a`: stopped at step 0 with "Could not load libtorchcodec"; no step ran and no output folder was created. Cause: the command was wrapped in `/usr/bin/time`, which macOS System Integrity Protection treats as a protected system binary, so it strips `DYLD_*` variables from its environment. torchcodec therefore never saw `DYLD_FALLBACK_LIBRARY_PATH` and could not find FFmpeg 8. Fix: use the shell's built-in `time` instead.

## Run 2: batch 32 throughput check (50 steps)

Purpose: measure whether batch size 32 processes samples faster than batch size 8 on `mps`, to decide the full run's batch size and length. Measures speed and memory only; the loss is not compared, and no checkpoint is saved.

| Field | Value |
|---|---|
| Config | `configs/train_act_batch32_check.json` |
| Git commit | TO FILL |
| Seed | 1000 |
| Steps, batch size | 50, 32 |
| Started, finished | TO FILL |
| Seconds per step | TO FILL (steps 20 to 50) |
| Samples per second | TO FILL (batch 8 in run 1: 8 to 9) |
| Data loading per step | TO FILL |
| Peak memory | TO FILL (process, and Activity Monitor's Memory Used) |
| GPU in Activity Monitor | TO FILL |
| Outcome | TO FILL |
