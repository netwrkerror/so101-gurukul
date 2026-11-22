# Project 04: a pretrained vision-language-action model against ACT

## Goal

Fine-tune SmolVLA, a pretrained vision-language-action model (VLA), on the same 45 demonstrations that trained ACT in project 01, and compare the two on the same task, evaluation protocol, and arm session. At the end there is a fine-tuned SmolVLA policy, an offline comparison on the held-out test set, and 20 arm trials each for SmolVLA and ACT, run side by side.

## Why it matters

ACT (projects 01 to 03) is trained from scratch on one task. VLAs start from a model pretrained on images, language, and many robots' demonstrations, then fine-tune on a small task dataset; most current robot learning work uses them. The question is whether that pretraining pays off at this scale: 45 demonstrations, one low-cost arm, one task. It also exercises the parts of a real stack that change with model size: cloud fine-tuning, inference latency on the robot's computer, and serving if local inference is too slow.

## Steps

Ordered, each one branch and PR. Steps 5 and 6 move the arm.

| # | Step | Branch | Done when |
|---|---|---|---|
| 1 | Add SmolVLA to the environment | `p04/environment` | LeRobot's `smolvla` extra added in `pyproject.toml`; the lock changes only by adding packages (LeRobot, torch, torchvision, torchcodec unchanged); `DECISIONS.md` entry |
| 2 | Inference check on the Mac | `p04/inference-check` | The pretrained base (`lerobot/smolvla_base`) loads with local LeRobot 0.6.0 and predicts a chunk from our cameras and joints; time per chunk on `mps` measured; decision recorded: run in-process (as ACT) or through project 02's policy server |
| 3 | Fine-tune on our 45 episodes | `p04/train` | A short cloud check (speed, memory, cost per step), then the full run on HF Jobs with LeRobot's SmolVLA fine-tuning settings, checked in the installed source; config committed; the final checkpoint chosen before evaluation; model private on the Hub |
| 4 | Offline comparison | `p04/offline-eval` | SmolVLA and ACT S1 scored on project 03's 9-episode held-out test set (action error, first action and first second), with bootstrap intervals and paired differences |
| 5 | Serving setup and dry run | `p04/serving` | Project 02's trial runner records every trial (video and joints, privately); both policies run through project 02's policy server with early chunk requests; a short dry run on the arm per policy (not counted) shows the queue never empties at chunk boundaries |
| 6 | Arm evaluation | `p04/eval` | 20 trials each for SmolVLA and ACT S1 under project 01's protocol, both served the same way, in the same session, balanced blocks of 10 (SmolVLA, S1, S1, SmolVLA), every trial recorded |
| 7 | Write-up | `p04/writeup` | README and a results summary match the logs; part 4 of the blog |

## Definition of done

- **Same task and protocol as project 01:**
  - **Task:** pick up the stuffed toy from one of three marked spots (7 A, 7 B, 6 C, project 01's fixed order) and place it in the bowl, within 45 seconds.
  - **Success rule, failure types, and re-run rule:** project 01's, unchanged.
  - **The setup:** the same cameras, bowl, toy, task string, and evening lighting, and the same speed cap.
- **Same session and same serving path:** SmolVLA and ACT S1 run on the same evening, in balanced blocks, both through project 02's policy server with early chunk requests, so the comparison is like for like (project 03's S1 was from another session; ACT's earlier results were in-process or served without early requests).
- **Reported:** successes out of 20 for each, with 95% intervals and an exact test; by spot; the offline comparison; inference time per chunk; training time and cost.
- **No success target.** With 20 trials, only a large difference is meaningful, and the write-up says so.

## Inputs and outputs

- **Inputs:**
  - `causalerror/so101-toy-to-bowl` (our 45 episodes);
  - ACT S1, project 01's run 4 (`causalerror/act-so101-toy-to-bowl`);
  - the test set `causalerror/so101-toy-to-bowl-test` (project 03);
  - the pretrained base `lerobot/smolvla_base`;
  - project 01's evaluation protocol, and project 02's policy server if needed.
- **Outputs:**
  - **Committed:** the configs, the inference measurements, the offline and arm results, and a summary.
  - **Private on the Hub:** the fine-tuned model and the trial recordings.

## Risks and unknowns

- **Inference speed on the Mac.** SmolVLA is about 450M parameters against ACT's much smaller model. If a chunk takes too long on `mps`, the arm waits at every chunk boundary (project 02 measured exactly this). Step 2 measures it first; the fallbacks are project 02's async policy server, locally, or on a cloud GPU.
- **Different chunking:** SmolVLA predicts 50 actions per chunk, ACT 100. That is part of each model, not changed to match.
- **The cloud image runs LeRobot 0.6.2,** local 0.6.0 (project 01 needed one conversion for ACT). The SmolVLA checkpoint may need its own; step 2 or 3 checks.
- **Camera names:** the pretrained base was trained on other camera setups; fine-tuning uses our `wrist` and `front`, which LeRobot may need mapped (`rename_map`). Checked in step 2.
- **Training settings:** LeRobot's SmolVLA defaults differ from ACT's (steps, batch size, frozen vision encoder). Training budget is not equal compute with ACT; the write-up says so.
- **Cost:** a larger model may need more GPU memory or time than ACT's run 4 (about $7). The step 3 check measures it before the full run.
- **Follower disconnects** (six in project 03's session): handled as they come, as in project 03. Non-starts are voided and re-run, and every recording is listed.

## Out of scope / later

- **SmolVLA fine-tuned on S2** (ours plus 135 curated public episodes), as an add-on after this comparison. For a like-for-like answer it must be tested in the same session as ACT S2, so that add-on re-runs S2 alongside.
- Other VLAs in LeRobot 0.6.0 (for example π0, π0.5, GR00T).
- Fixing the follower disconnects (power supply, USB, a read retry).
- Fine-tuning the vision encoder, or a longer training budget.
