#!/usr/bin/env bash
# Fine-tune SmolVLA on our 45 episodes on HF Jobs (project 04, step 3). Submits a paid job.
# lerobot-train takes the pretrained checkpoint and every --policy.* setting from the command line
# only: with --policy.path, policy fields in the config file are replaced. Everything else is in
# train_smolvla.json. Settings follow LeRobot's SmolVLA guide (batch 64, 20,000 steps).
#
# Usage, from the repo root:
#   projects/04-smolvla/configs/train_smolvla.sh                 # the full run
#   projects/04-smolvla/configs/train_smolvla.sh --steps=200 \
#     --job_name=p04_smolvla_check                                  # the cloud check
#
# The model repo is named by LeRobot 0.6.0's HF Jobs launcher, not by --policy.repo_id: with --policy.path,
# it is <user>/<job_name>_<UTC timestamp> (lerobot/jobs/hf.py). It is created private (--policy.private).
set -euo pipefail
exec uv run lerobot-train \
  --config_path=projects/04-smolvla/configs/train_smolvla.json \
  --policy.path=lerobot/smolvla_base \
  --policy.pretrained_revision=5e8d12a6e2975b0e5e5fce7c8caf47c371d257b6 \
  --policy.push_to_hub=true \
  --policy.private=true \
  --policy.device=cuda \
  --policy.empty_cameras=0 \
  "$@"
