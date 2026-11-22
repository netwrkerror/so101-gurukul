# Training runs (step 3)

SmolVLA fine-tuned from `lerobot/smolvla_base` (revision `5e8d12a6`) on our 45 episodes (`causalerror/so101-toy-to-bowl`, revision `c6319da8`), the same data as ACT S1. Settings follow LeRobot's SmolVLA guide. Launch: `configs/train_smolvla.sh` (policy settings) with `configs/train_smolvla.json` (everything else).

Fields marked TO FILL are completed from the job logs and the Hub.

## Cloud check (200 steps, not used for evaluation)

| Field | Value |
|---|---|
| Purpose | Confirm the image runs SmolVLA and loads the pinned base; measure seconds per step, GPU memory, and cost per step on `a100-large` before the full run |
| Command | `configs/train_smolvla.sh --steps=200 --job_name=p04_smolvla_check --policy.repo_id=causalerror/smolvla-so101-cloud-check` |
| Job ID | TO FILL |
| Seconds per step, data loading per step, GPU memory | TO FILL |
| Projected full run (20,000 steps) | TO FILL |
| Outcome | TO FILL |

## Full run

| Field | Value |
|---|---|
| Git commit | TO FILL |
| Hardware and image | HF Jobs `a100-large` (1x A100 80 GB, 12 vCPUs, $2.50/hour), image digest `sha256:fc48db80c040…` (LeRobot 0.6.2), as projects 01 and 03 |
| Seed; steps, batch size, workers | 1000; 20,000, 64, 10 |
| Optimizer | SmolVLA's defaults: AdamW, learning rate 1e-4, 1,000 warm-up steps, cosine decay to 2.5e-6 over 30,000 steps |
| What trains | The action expert only; the vision encoder frozen (SmolVLA's defaults: `train_expert_only`, `freeze_vision_encoder`) |
| Cameras | `front` to `camera1`, `wrist` to `camera2`, the base's third slot left out (`empty_cameras=0`) |
| Samples seen | 1,280,000 (20,000 x 64), about 49 passes over our 25,876 frames; ACT S1 saw 800,000 (about 31 passes) |
| Job ID | TO FILL |
| Started, finished, billed time | TO FILL |
| Loss at 5k, 10k, 15k, 20k steps | TO FILL |
| Model repo and revision | `causalerror/smolvla-so101-toy-to-bowl` (private), revision TO FILL |
| Outcome | TO FILL |

## Notes

- The final checkpoint (20,000 steps) is the one evaluated, chosen now, before any evaluation.
- Loss is not comparable with ACT's: different model, objective (SmolVLA uses flow matching), and chunk length.
- Not equal compute with ACT: different models and LeRobot's recommended settings for each. The write-up says so.
