"""Step 2: can SmolVLA run on this Mac fast enough to drive the arm in-process, as ACT does?

Loads the pretrained base (lerobot/smolvla_base, at a pinned revision) with local LeRobot 0.6.0,
feeds it real observations from our own dataset (both cameras, the joints, the task string), and
times one action chunk on mps (and on cpu for reference). The base is not fine-tuned, so its actions
are meaningless; the fine-tuned model has the same architecture, so its timing is what matters here.

Two cases, because step 3 must choose how our two cameras fill the base's three camera slots:
  - 2 images: ours mapped to camera1 and camera2, the third slot left out (empty_cameras=0);
  - 3 images: the same, plus a masked blank image in the third slot (empty_cameras=1).

Run from the repo root (does not touch the arm; downloads about 0.9 GB once):
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/ffmpeg@8/lib \
      uv run python projects/04-smolvla/src/inference_check.py
Output: projects/04-smolvla/results/inference_check.md
"""

import argparse
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path

BASE = "lerobot/smolvla_base"
BASE_REVISION = "5e8d12a6e2975b0e5e5fce7c8caf47c371d257b6"
OURS = "causalerror/so101-toy-to-bowl"
OURS_ROOT = "~/.cache/huggingface/lerobot/causalerror/so101-toy-to-bowl_20261017_130943"
TASK = "Pick up the stuffed toy and place it in the bowl"
RENAME = {"observation.images.front": "observation.images.camera1", "observation.images.wrist": "observation.images.camera2"}
RESULTS = Path("projects/04-smolvla/results")
CHUNK_S = 50 / 30  # one chunk of 50 actions at 30 Hz


def sync(device: str) -> None:
    import torch

    if device == "mps":
        torch.mps.synchronize()


def time_case(device: str, empty_cameras: int, frames: list[dict], reps: int, warmup: int) -> list[float]:
    import torch
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    # The generic loader reads config.json's "type" field and returns a SmolVLAConfig.
    cfg = PreTrainedConfig.from_pretrained(BASE, revision=BASE_REVISION)
    cfg.device, cfg.empty_cameras = device, empty_cameras
    policy = SmolVLAPolicy.from_pretrained(BASE, revision=BASE_REVISION, config=cfg).to(device).eval()
    pre, post = make_pre_post_processors(cfg, pretrained_path=BASE, pretrained_revision=BASE_REVISION,
                                         preprocessor_overrides={"device_processor": {"device": device},
                                                                 "rename_observations_processor": {"rename_map": RENAME}})
    times = []
    for i in range(warmup + reps):
        obs = dict(frames[i % len(frames)])
        sync(device); t0 = time.perf_counter()
        with torch.no_grad():
            chunk = post(policy.predict_action_chunk(pre(obs)))
        sync(device)
        if i >= warmup:
            times.append(time.perf_counter() - t0)
    shape = tuple(chunk.shape)
    del policy
    return times, shape


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reps", type=int, default=20)
    parser.add_argument("--cpu-reps", type=int, default=3)
    args = parser.parse_args()

    import torch
    from lerobot.datasets import LeRobotDataset

    ds = LeRobotDataset(OURS, root=os.path.expanduser(OURS_ROOT))
    picks = [int(ds.meta.episodes[e]["dataset_from_index"]) + 60 for e in (0, 14, 29, 44)]
    frames = []
    for i in picks:
        item = ds[i]
        frames.append({"observation.state": item["observation.state"], "observation.images.front": item["observation.images.front"],
                       "observation.images.wrist": item["observation.images.wrist"], "task": TASK})

    rows = []
    for device, reps in (("mps", args.reps), ("cpu", args.cpu_reps)):
        if device == "mps" and not torch.backends.mps.is_available():
            continue
        for empty in (0, 1):
            times, shape = time_case(device, empty, frames, reps, warmup=3 if device == "mps" else 1)
            med = statistics.median(times)
            rows.append((device, 2 + empty, len(times), med, max(times), shape))
            print(f"{device}, {2 + empty} images: median {med * 1000:.0f} ms, max {max(times) * 1000:.0f} ms over {len(times)}; chunk {shape}")

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    import lerobot
    import transformers

    lines = [
        "# SmolVLA inference check on the Mac (step 2)",
        "",
        f"Built by `src/inference_check.py` (git commit `{commit}`): `{BASE}` @ `{BASE_REVISION[:8]}`, LeRobot {lerobot.__version__}, "
        f"transformers {transformers.__version__}, torch {torch.__version__}, {platform.machine()}. Real observations from our dataset "
        "(4 frames, one per spot and the last episode); cameras mapped front to camera1, wrist to camera2. Time per chunk includes "
        "pre- and post-processing, after a warm-up.",
        "",
        "| Device | Images | Runs | Median per chunk | Slowest |",
        "|---|---|---|---|---|",
        *[f"| {d} | {n} | {r} | {m * 1000:.0f} ms | {x * 1000:.0f} ms |" for d, n, r, m, x, _ in rows],
        "",
        f"- Chunk: {rows[0][5]}, i.e. 50 actions, which the arm plays out in {CHUNK_S:.2f} s at 30 Hz.",
        "- For comparison (project 02): ACT took about 88 ms per chunk natively on `mps`; in project 02's fault tests, a 200 ms "
        "delay made the arm's pauses visible but the task still worked in 3 of 4 informal trials.",
        "- In-process (`lerobot-rollout`), the arm waits for each chunk, so the time per chunk is a pause at every chunk boundary.",
        "",
        "## Decision",
        "",
        "TO FILL after reading the numbers: in-process on mps, or project 02's policy server.",
    ]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "inference_check.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {RESULTS / 'inference_check.md'}")


if __name__ == "__main__":
    main()
