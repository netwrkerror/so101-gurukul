# so101-gurukul: working agreement

This file is the working agreement between you and me for this repo. Read it at the start of every session and follow it over any default behavior.

## What this repo is

Hands-on physical AI projects on a Seeed Studio SO-ARM101 Pro (leader + follower) using Hugging Face LeRobot, covering data collection, training, evaluation, serving, and observability. Understanding matters more than speed.

## How we work

### Plan first

- Before writing or changing code, propose a plan: what you will change, why, which files, and how Aakash can verify it. Then stop and wait for approval.
- Each project starts from its `projects/<nn-name>/BRIEF.md`. If the brief is missing or unclear, ask before building.
- Keep changes small: one concept per branch and PR, small enough to read in full.
- If a request is ambiguous, ask one question instead of guessing.
- New ideas outside the current brief go into the brief's "Out of scope / later" list, not into the code.

### Who runs what

- Claude writes and edits files, and proposes commands, branch names, commit messages, and PR text.
- Aakash runs the commands. Do not execute shell commands unless he approves that specific command.
- Never run anything that moves the arm, powers motors, or writes calibration. Give the command and say what the arm will physically do, so Aakash can clear the workspace and keep a hand near the power switch.
- Never run `git push`, force operations, or anything that deletes data. Propose them.

### Git conventions

- Branches: `p<nn>/<short-topic>`, for example `p01/record-dataset`.
- Commits: imperative, one logical change each.
- PR description sections: What, Why, How to verify, Results (if any), Notes / limitations.
- Add a dated entry to `DECISIONS.md` whenever a real choice is made (policy, camera placement, hyperparameters, a dropped approach) with the reason.

## Honest results

- Report every success rate with its trial count and conditions (for example "14/20, object within the taped square, overhead camera only").
- Log failures and negative results in the project's `results/` and in `DECISIONS.md`. Do not drop bad runs.
- Never describe something as working unless it was run and observed. Say "untested" when it is.
- Keep evaluation conditions fixed when comparing policies. Flag any comparison that is not like for like.
- Do not write README or blog claims that the logged results do not support.

## Reproducibility

- The LeRobot version is pinned (see Hardware and environment). Do not upgrade it without a plan and a `DECISIONS.md` entry.
- LeRobot's CLI and APIs change between releases. Check the installed source or the docs for the pinned version before using an API. Do not rely on memory. If unsure, say so.
- Every training or eval run has a committed config file and a recorded seed, git commit, dataset ID and revision, and hardware used.
- Datasets, checkpoints, and run outputs are not committed. They go to the Hugging Face Hub and are referenced by repo ID and revision.
- One environment definition for the repo, committed. No ad hoc `pip install` without updating it.

## Privacy and secrets

- Tokens and keys live in `.env`, which is gitignored. Never print, log, or commit them. Commit a `.env.example` with names only.
- No DISH / EchoStar code, data, configs, internal names, or screenshots anywhere in this repo.
- Before any dataset is made public, remind Aakash to review camera frames for anything identifying in the background (faces, documents, screens, mail, the room).
- New Hub datasets and models are created private. Making one public is Aakash's explicit decision.
- `notes.local.md` is private and gitignored. Do not copy its contents into committed files.
- Never write absolute home-directory paths into committed files. Use `~` or repo-relative paths. Machine-specific paths go in the gitignored `common/hardware.local.yaml`. Check the staged diff for `/Users/` before proposing any commit.

## Repo layout

```
so101-gurukul/
  CLAUDE.md
  README.md
  LICENSE
  DECISIONS.md          # committed decision log
  notes.local.md        # private, gitignored
  .env.example
  common/               # shared configs, arm IDs, utilities (created when first needed)
  projects/
    BRIEF.template.md   # copied to each project's BRIEF.md
    01-baseline-act/    # BRIEF.md, src/, configs/, results/
    02-serving-observability/   # created when started
    03-ray-curation/            # created when started
```

Naming: the setup is called gurukul. `guru` is the leader arm and `shishya` is the follower. In technical sections of READMEs, configs, and results, say "leader" and "follower" alongside the names.

`.gitignore` must cover: `.env`, `notes.local.md`, datasets, checkpoints, run outputs, caches.

## Hardware and environment

Fill these in after first setup and keep them current.

| Item | Value |
|---|---|
| Leader arm (black) | `guru` |
| Follower arm (white) | `shishya` |
| LeLab device name | `gurukul` |
| Leader calibration file (as LeLab wrote it) | `~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/gurukul.json` |
| Follower calibration file (as LeLab wrote it) | `~/.cache/huggingface/lerobot/calibration/robots/so_follower/gurukul.json` |
| Calibration ID for the LeRobot CLI | `gurukul` for both arms: `--teleop.type=so101_leader --teleop.id=gurukul` and `--robot.type=so101_follower --robot.id=gurukul` |
| Leader port | In `common/hardware.local.yaml` (gitignored) |
| Follower port | In `common/hardware.local.yaml` (gitignored) |
| Cameras (name, index, resolution, fps) | TBD |
| LeRobot version | 0.6.0, git commit `30da8e687a6dfc617fcd94afc367ac7071c376ce` (tag v0.6.0), extras `core-scripts`, `feetech`, `training` |
| Python version | 3.12 (`>=3.12,<3.13`) |
| Dev machine | MacBook Pro, M5 Pro (15-core CPU, 16-core GPU), 24 GB unified memory, macOS |
| Local compute device | `mps` (Apple GPU). No CUDA on this machine: do not propose CUDA-only flags or libraries for local runs |
| Local use | Teleoperation, recording, ACT training and inference |
| Cloud use | SmolVLA and larger VLA fine-tunes (provider TBD) |
| Hugging Face user | `causalerror` |

## Clarifications

These refine the sections above. Where they differ, this section wins.

- Read-only shell commands (`git status`, `git diff`, `git log`, `ls`, searching or reading the installed LeRobot source) do not need approval. All other shell commands do.
- Docs-only edits need a one-line statement of the change, not a full plan.
- Local git commands (branch, add, commit, and the rest) are proposed by Claude and run by Aakash.
- Hub uploads are propose-only and always private.
- Machine-specific values (ports, camera indexes) live in `common/hardware.local.yaml`, which is gitignored. A committed `common/hardware.example.yaml` shows the keys without real values.
- `results/` holds committed summaries and failure logs. Raw outputs, videos, and checkpoints go to the Hub.
- Proposed commit messages do not include the `Co-Authored-By` trailer.
- The environment tool is uv. `pyproject.toml` and `uv.lock` are the one environment definition. Change dependencies with `uv add` or by editing `pyproject.toml` and re-locking, never with `pip install`. uv must be an arm64 build, 0.12.0 or newer (`required-version` enforces the version). An x86_64 uv would build an environment without MPS.

### Open items

- None right now.