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
| Git commit | `0671a46` |
| Seed | 1000 |
| Steps, batch size | 50, 32 |
| Started, finished | 2026-10-17, dataset loading at 19:50:08 MDT; stopped by hand at step 8 of 50, about 19:56 MDT |
| Seconds per step | 45.8 s at step 6, 53.3 s at step 7, 60.5 s at step 8, and rising |
| Samples per second | About 0.5 to 0.7 (batch 8 in run 1: 8 to 9) |
| Data loading per step | Not reached: no log line before step 10 |
| Peak memory | About 20.2 GB for the training process in Activity Monitor. System swap at 15.2 GB of 16 GB used |
| GPU in Activity Monitor | Fluctuating between 6% and 87%, often low: the GPU was waiting on memory |
| Outcome | Stopped early. Batch 32 does not fit in 24 GB of unified memory alongside everything else: the process grew to about 20 GB, the system swapped heavily, and throughput fell to under a tenth of batch 8's. The Rerun viewer from the dataset review was also still open, holding 4.8 GB |

## Run 3: cloud check on Hugging Face Jobs (50 steps)

Purpose: (1) confirm training runs on HF Jobs with the private dataset and a digest-pinned image; (2) measure seconds per step and cost on `a10g-large`; (3) confirm a checkpoint trained with the image's LeRobot 0.6.2 loads with this repo's LeRobot 0.6.0, which evaluation uses. Not used for evaluation.

| Field | Value |
|---|---|
| Config | `configs/train_act_cloud_check.json` |
| Git commit | TO FILL |
| Hardware | HF Jobs `a10g-large`: 1x NVIDIA A10G (24 GB), 12 vCPU, 46 GB RAM, $1.50/hour |
| Image | `huggingface/lerobot-gpu@sha256:fc48db80c040cfbc33e0a481e351b042a77422c527e5150138c354e4774e471f` (the `latest` tag as of 2026-10-17; LeRobot 0.6.2, torch 2.11.0+cu128, torchcodec 0.11.1) |
| Seed | 1000 |
| Steps, batch size, workers | 50, 8, 8 |
| Job ID | TO FILL |
| Started, finished, billed time | TO FILL |
| Seconds per step | TO FILL (steps 20 to 50) |
| Data loading per step | TO FILL |
| Loss at step 10 and step 50 | TO FILL |
| Model repo | `causalerror/act-so101-toy-to-bowl-cloud-check` (private: TO CONFIRM on the Hub) |
| Loads with local LeRobot 0.6.0 | TO FILL |
| Outcome | TO FILL |
