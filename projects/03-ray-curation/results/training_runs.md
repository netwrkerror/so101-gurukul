# Training runs (step 6)

Two ACT runs, on S2 (curated) and S3 (random control), with project 01's run 4 settings. Only the dataset differs: the configs equal run 4's (`projects/01-baseline-act/configs/train_act.json`) except for the job name, output folder, dataset and its revision, and model repo. S1 needs no new run; it is project 01's run 4 model (`causalerror/act-so101-toy-to-bowl`, revision `2ecffdd421f46c20f5220c3ca9c4e1fca988a646`).

Filled in from the job logs (`hf jobs logs`) and the Hub after both runs completed on 2026-11-13.

## S2: curated

| Field | Value |
|---|---|
| Config | `configs/train_act_s2.json` |
| Git commit | `86a4159` |
| Dataset | `causalerror/p03-s2-curated`, revision `1ea262622514800d87a4fbc050c77c7c32274811` (180 episodes, 82,165 frames) |
| Hardware and image | HF Jobs `a10g-small` (1x A10G 24 GB, 4 vCPUs, $1.00/hour), image digest `sha256:fc48db80c040…` (LeRobot 0.6.2). Run 4 used `a10g-large`: same GPU, 12 vCPUs (see DECISIONS.md, 2026-11-12) |
| Seed; steps, batch size, workers | 1000; 100,000, 8, 8 |
| Expected time and cost | About 4.5 hours if 4 vCPUs keep up with data loading (run 4 used about 14% of 12), so about $4.50; timeout 8 hours |
| Job ID | `6af6741c0f431c4f7b56bc87` (an earlier submission on `a10g-large`, `6af66f8b0f431c4f7b56b59b`, was cancelled while waiting for hardware) |
| Started, finished, billed time | Submitted 2026-11-13 02:21:16 UTC; dataset loaded 02:23:37; training ended 06:51:15 UTC; model pushed 06:51:18 UTC. Runtime 4 h 28 m (`hf jobs ps`), so about $4.47 at $1.00/hour |
| Seconds per step | 0.159 to 0.161 throughout after warm-up; 0.160 at step 400 (0.36 at step 200, while the data loaders warmed up); data loading 0.002 s per step; GPU memory 3.73 GB. The same as run 4 on `a10g-large`, so 4 vCPUs keep up |
| Loss at 20k, 40k, 60k, 80k, 100k steps | 0.158, 0.112, 0.093, 0.079, 0.072 (the logged line at each checkpoint step; the KL part is 0.000 from 40k on) |
| Passes over the dataset | about 9.7 (800,000 samples over 82,165 frames), against about 31 for run 4 |
| Model repo and revision | `causalerror/act-so101-p03-s2-curated`, private (confirmed on the Hub), revision `9537e8b420a56cf0f34b9d331f64d759fd490ca0` |
| Outcome | Completed. Final checkpoint (100,000 steps) chosen for evaluation, before any evaluation |

## S3: random control

| Field | Value |
|---|---|
| Config | `configs/train_act_s3.json` |
| Git commit | `86a4159` |
| Dataset | `causalerror/p03-s3-random`, revision `7a5d50ab6a1faf7cb89958e1fda67fa0f0291336` (180 episodes, 94,102 frames) |
| Hardware and image | As S2 |
| Seed; steps, batch size, workers | 1000; 100,000, 8, 8 |
| Expected time and cost | As S2 |
| Job ID | `6af674310f431c4f7b56bc9f` (an earlier submission on `a10g-large`, `6af670ee5f2f1b7284b91842`, was cancelled while waiting for hardware) |
| Started, finished, billed time | Submitted 2026-11-13 02:21:37 UTC; dataset loaded 02:23:38; training ended 06:51:21 UTC; model pushed 06:51:25 UTC. Runtime 4 h 28 m (`hf jobs ps`), so about $4.47 at $1.00/hour |
| Seconds per step | 0.160 to 0.161 throughout after warm-up; 0.161 at step 400 (0.37 at step 200, while the data loaders warmed up); data loading 0.002 s per step; GPU memory 3.73 GB |
| Loss at 20k, 40k, 60k, 80k, 100k steps | 0.184, 0.124, 0.104, 0.089, 0.082 (the logged line at each checkpoint step; the KL part is 0.000 from 40k on) |
| Passes over the dataset | about 8.5 (800,000 samples over 94,102 frames) |
| Model repo and revision | `causalerror/act-so101-p03-s3-random`, private (confirmed on the Hub), revision `2ea29fd7512a7e1947ebf5d19e3e5e9f31db90da` |
| Outcome | Completed. Final checkpoint (100,000 steps) chosen for evaluation, before any evaluation |

## Notes

- **The checkpoint to evaluate is the final one (100,000 steps),** chosen before evaluation, as in project 01.
- **Run 4's loss for reference:** 0.156, 0.110, 0.089, 0.077, 0.067 at the same steps.
- **Loss is not comparable across runs.** The training sets differ, so a lower loss on S2 or S3 says nothing about which policy is better; step 7's held-out test set and arm trials decide that.
- **Same steps, fewer passes:** with the same 100,000 steps on a larger dataset, each frame is seen about 9 times instead of 31. This is deliberate (equal compute), and the brief notes that it may favor the smaller set.
- **The final checkpoints get the same one-field conversion as run 4** (`"dtype": null` removed from `config.json`) so local LeRobot 0.6.0 can load them for evaluation.
