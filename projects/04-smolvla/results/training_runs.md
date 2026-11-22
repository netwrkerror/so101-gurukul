# Training runs (step 3)

SmolVLA fine-tuned from `lerobot/smolvla_base` (revision `5e8d12a6`) on our 45 episodes (`causalerror/so101-toy-to-bowl`, revision `c6319da8`), the same data as ACT S1. Settings follow LeRobot's SmolVLA guide. Launch: `configs/train_smolvla.sh` (policy settings) with `configs/train_smolvla.json` (everything else).

Filled in from the job logs and the Hub.

## Cloud check (200 steps, not used for evaluation)

| Field | Value |
|---|---|
| Purpose | Confirm the image runs SmolVLA and loads the pinned base; measure seconds per step, GPU memory, and cost per step on `a100-large` before the full run |
| Command | `configs/train_smolvla.sh --steps=200 --job_name=p04_smolvla_check` |
| Job ID | `6b033948130a00b5aa80d857`, 3 m 14 s (including the 0.9 GB base download) |
| Settings actually used (from the pushed `train_config.json`) | base `lerobot/smolvla_base` @ `5e8d12a6`, `empty_cameras` 0, our camera mapping, batch 64, private |
| Parameters | 450,046,176 in total; 99,880,992 trained (the action expert) |
| Seconds per step, data loading per step, GPU memory | 0.563 s, 0.087 s, 14.4 GB of 80 (at step 200) |
| Projected full run (20,000 steps) | About 3.1 hours of training, so about $8 at $2.50/hour |
| Outcome | Passed: the image runs SmolVLA, loads the pinned base, and fits batch 64 with room to spare |

## Full run

| Field | Value |
|---|---|
| Git commit | `6114143` |
| Hardware and image | HF Jobs `a100-large` (1x A100 80 GB, 12 vCPUs, $2.50/hour), image digest `sha256:fc48db80c040…` (LeRobot 0.6.2), as projects 01 and 03 |
| Seed; steps, batch size, workers | 1000; 20,000, 64, 10 |
| Optimizer | SmolVLA's defaults: AdamW, learning rate 1e-4, 1,000 warm-up steps, cosine decay to 2.5e-6 over 30,000 steps |
| What trains | The action expert only; the vision encoder frozen (SmolVLA's defaults: `train_expert_only`, `freeze_vision_encoder`) |
| Cameras | `front` to `camera1`, `wrist` to `camera2`, the base's third slot left out (`empty_cameras=0`) |
| Samples seen | 1,280,000 (20,000 x 64), about 49 passes over our 25,876 frames; ACT S1 saw 800,000 (about 31 passes) |
| Job ID | `6b033cb58d268c0fbd22708e` |
| Date, billed time, cost | 2026-11-22; 2 h 42 m (training 2 h 41 m, 0.48 s per step; the check's 0.563 s included warm-up), so about $6.75 at $2.50/hour |
| Loss at 5k, 10k, 15k, 20k steps | 0.067, 0.034, 0.022, 0.019 (GPU memory 14.4 GB throughout) |
| Model repo and revision | `causalerror/smolvla-so101-toy-to-bowl` @ `a299de1f` (private; renamed on the Hub from the launcher's timestamped name, which keeps the revision). The repo root holds the 20,000-step model (same file hash as `checkpoints/020000`); the 5k, 10k, and 15k checkpoints are also there |
| Outcome | Completed all 20,000 steps and pushed the model. The pushed `train_config.json` matches the settings above (seed, steps, batch, base and revision, dataset revision, camera mapping, `empty_cameras` 0, optimizer and schedule). Not yet loaded with local LeRobot 0.6.0 (step 4 does) and not yet evaluated |

## Notes

- The final checkpoint (20,000 steps) is the one evaluated, chosen now, before any evaluation.
- **Model repo names:** with `--policy.path`, LeRobot 0.6.0's HF Jobs launcher names the model repo `<user>/<job_name>_<UTC timestamp>` and overrides `--policy.repo_id` (`lerobot/jobs/hf.py`: the policy is not resolved yet when the name is chosen). The flag is still required, because validation rejects `save_checkpoint_to_hub` without it; dropping it made the first full-run launch fail before anything was submitted. `--policy.private` is honored.
- **The base's third camera slot:** the model's `config.json` still lists `camera3` (inherited from the base). With `empty_cameras` 0, SmolVLA skips image slots missing from the batch (`prepare_images` in `modeling_smolvla.py`), so it trained on two images, as measured in step 2.
- Loss is not comparable with ACT's: different model, objective (SmolVLA uses flow matching), and chunk length.
- Not equal compute with ACT: different models and LeRobot's recommended settings for each. The write-up says so.
