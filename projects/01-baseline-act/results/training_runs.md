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
| Git commit | TO FILL |
| Seed | 1000 |
| Steps, batch size | 50, 8 |
| Started, finished | TO FILL |
| Device confirmed | TO FILL (from the log, and GPU activity in Activity Monitor) |
| Seconds per step | TO FILL (from the later log lines; the first includes start-up) |
| Peak memory | TO FILL |
| Loss at step 10 and step 50 | TO FILL |
| Checkpoint saved | TO FILL |
| Outcome | TO FILL |
| Notes | |
