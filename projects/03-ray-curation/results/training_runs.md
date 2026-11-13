# Training runs (step 6)

Two ACT runs, on S2 (curated) and S3 (random control), with project 01's run 4 settings. Only the dataset differs: the configs equal run 4's (`projects/01-baseline-act/configs/train_act.json`) except for the job name, output folder, dataset and its revision, and model repo. S1 needs no new run; it is project 01's run 4 model (`causalerror/act-so101-toy-to-bowl`, revision `2ecffdd421f46c20f5220c3ca9c4e1fca988a646`).

Fields marked TO FILL are completed from the job logs and the Hub after each run.

## S2: curated

| Field | Value |
|---|---|
| Config | `configs/train_act_s2.json` |
| Git commit | TO FILL |
| Dataset | `causalerror/p03-s2-curated`, revision `1ea262622514800d87a4fbc050c77c7c32274811` (180 episodes, 82,165 frames) |
| Hardware and image | HF Jobs `a10g-small` (1x A10G 24 GB, 4 vCPUs, $1.00/hour), image digest `sha256:fc48db80c040…` (LeRobot 0.6.2). Run 4 used `a10g-large`: same GPU, 12 vCPUs (see DECISIONS.md, 2026-11-12) |
| Seed; steps, batch size, workers | 1000; 100,000, 8, 8 |
| Expected time and cost | About 4.5 hours if 4 vCPUs keep up with data loading (run 4 used about 14% of 12), so about $4.50; timeout 8 hours |
| Job ID | TO FILL (first submission on `a10g-large`, cancelled while waiting for hardware: S2 `6af66f8b0f431c4f7b56b59b`, S3 `6af670ee5f2f1b7284b91842`) |
| Started, finished, billed time | TO FILL |
| Seconds per step | TO FILL |
| Loss at 20k, 40k, 60k, 80k, 100k steps | TO FILL |
| Passes over the dataset | about 9.7 (800,000 samples over 82,165 frames), against about 31 for run 4 |
| Model repo and revision | `causalerror/act-so101-p03-s2-curated` (private), revision TO FILL |
| Outcome | TO FILL |

## S3: random control

| Field | Value |
|---|---|
| Config | `configs/train_act_s3.json` |
| Git commit | TO FILL |
| Dataset | `causalerror/p03-s3-random`, revision `7a5d50ab6a1faf7cb89958e1fda67fa0f0291336` (180 episodes, 94,102 frames) |
| Hardware and image | As S2 |
| Seed; steps, batch size, workers | 1000; 100,000, 8, 8 |
| Expected time and cost | As S2 |
| Job ID | TO FILL (first submission on `a10g-large`, cancelled while waiting for hardware: S2 `6af66f8b0f431c4f7b56b59b`, S3 `6af670ee5f2f1b7284b91842`) |
| Started, finished, billed time | TO FILL |
| Seconds per step | TO FILL |
| Loss at 20k, 40k, 60k, 80k, 100k steps | TO FILL |
| Passes over the dataset | about 8.5 (800,000 samples over 94,102 frames) |
| Model repo and revision | `causalerror/act-so101-p03-s3-random` (private), revision TO FILL |
| Outcome | TO FILL |

## Notes

- **The checkpoint to evaluate is the final one (100,000 steps),** chosen before evaluation, as in project 01.
- **Loss is not comparable across runs.** The training sets differ, so a lower loss on S2 or S3 says nothing about which policy is better; step 7's held-out test set and arm trials decide that.
- **Same steps, fewer passes:** with the same 100,000 steps on a larger dataset, each frame is seen about 9 times instead of 31. This is deliberate (equal compute), and the brief notes that it may favor the smaller set.
- **The final checkpoints get the same one-field conversion as run 4** (`"dtype": null` removed from `config.json`) so local LeRobot 0.6.0 can load them for evaluation.
