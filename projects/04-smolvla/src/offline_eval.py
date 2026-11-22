"""Step 4: the offline comparison. How closely do SmolVLA and ACT S1 predict new demonstrations?

The same metric as project 03 (projects/03-ray-curation/src/offline_eval.py), on the same held-out test
set (9 episodes, 3 per spot, in the order A, B, C, ...). For every `stride`-th frame, each policy predicts
a chunk from that frame's observation (both cameras, the joint state, the task string). Two errors against
the recorded actions (what the operator actually did):
  - first action: the predicted next action against the recorded action at that frame,
  - first second: the first 30 predicted actions against the next 30 recorded ones, cut short at the end
    of an episode. Both chunks are long enough: SmolVLA predicts 50 actions, ACT 100.
Errors are mean absolute differences per joint: degrees for the five body joints, the 0 to 100 scale for
the gripper. Uncertainty: a bootstrap over episodes (only 9), including paired differences.

ACT is deterministic, so S1's numbers must match project 03's results; the script checks this.
SmolVLA turns random noise into a chunk (flow matching), so each prediction gets noise from a fixed seed
and the frame index (reproducible), and the whole run is repeated with a second seed to show how much
SmolVLA's own randomness moves the numbers.

Run from the repo root, after src/fetch_model.py (does not touch the arm):
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/ffmpeg@8/lib \
      uv run python projects/04-smolvla/src/offline_eval.py
Outputs:
    projects/04-smolvla/results/offline_eval.md               (committed)
    projects/04-smolvla/results/offline_eval_by_episode.csv   (committed)
"""

import argparse
import os
import statistics
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

TEST_REPO = "causalerror/so101-toy-to-bowl-test"
TEST_REVISION = "0683b67ac70673f7ea9f07bcaa17dae6d5b6a410"
TEST_ROOT = "~/.cache/huggingface/lerobot/causalerror/so101-toy-to-bowl-test"
SMOLVLA_PATH = "outputs/smolvla_final"  # src/fetch_model.py
S1_PATH = "outputs/act_final"  # project 01's run 4, converted copy
P03_BY_EPISODE = Path("projects/03-ray-curation/results/offline_eval_by_episode.csv")
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
SPOTS = "ABC"  # episode e was recorded at spot SPOTS[e % 3]
RESULTS = Path("projects/04-smolvla/results")
TASK = "Pick up the stuffed toy and place it in the bowl"
WARMUP = 3  # predictions left out of the timing


def sync(device: str) -> None:
    import torch

    if device == "mps":
        torch.mps.synchronize()


def load(kind: str, path: str, device: str):
    from lerobot.policies.factory import make_pre_post_processors

    if kind == "smolvla":
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy as cls
    else:
        from lerobot.policies.act.modeling_act import ACTPolicy as cls
    policy = cls.from_pretrained(path).to(device).eval()
    pre, post = make_pre_post_processors(policy.config, pretrained_path=path,
                                         preprocessor_overrides={"device_processor": {"device": device}})
    return policy, pre, post


def run_policy(name: str, policy, pre, post, ds, frames: list[int], horizon: int, device: str,
               noise_seed: int | None) -> tuple[pd.DataFrame, list[float]]:
    import torch

    actions = ds.hf_dataset.with_format("numpy")["action"]
    ep_of = ds.hf_dataset.with_format("numpy")["episode_index"]
    rows, times = [], []
    for k, i in enumerate(frames):
        item = ds[i]
        obs = {key: item[key] for key in ("observation.state", "observation.images.wrist", "observation.images.front")}
        obs["task"] = TASK
        noise = None
        if noise_seed is not None:
            gen = torch.Generator().manual_seed(noise_seed * 1_000_000 + i)
            shape = (1, policy.config.chunk_size, policy.config.max_action_dim)
            noise = torch.normal(0.0, 1.0, size=shape, generator=gen).to(device)
        sync(device); t0 = time.perf_counter()
        with torch.no_grad():
            batch = pre(obs)
            raw = policy.predict_action_chunk(batch, noise=noise) if noise is not None else policy.predict_action_chunk(batch)
            chunk = post(raw)[0].float().cpu().numpy()  # (chunk length, 6)
        sync(device)
        if k >= WARMUP:
            times.append(time.perf_counter() - t0)
        ep = int(ep_of[i])
        end = int(ds.meta.episodes[ep]["dataset_to_index"])
        n = min(horizon, end - i)
        recorded = np.stack(actions[i:i + n])
        first = np.abs(chunk[0] - recorded[0])
        sec = np.abs(chunk[:n] - recorded).mean(axis=0)
        rows.append({"policy": name, "episode": ep, "frame": i,
                     **{f"first_{j}": float(v) for j, v in zip(JOINTS, first)},
                     **{f"sec_{j}": float(v) for j, v in zip(JOINTS, sec)}})
    print(f"{name}: {len(rows)} predictions, median {statistics.median(times) * 1000:.0f} ms per chunk")
    return pd.DataFrame(rows), times


def bootstrap(values_by_ep: dict, reps: int, seed: int):
    """Mean over episodes, with a 95% interval from resampling episodes."""
    rng = np.random.default_rng(seed)
    eps = sorted(values_by_ep)
    v = np.array([values_by_ep[e] for e in eps])
    boots = v[rng.integers(0, len(v), size=(reps, len(v)))].mean(axis=1)
    return float(v.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stride", type=int, default=5, help="evaluate every Nth frame")
    parser.add_argument("--horizon", type=int, default=30, help="frames in the 'first second' error (30 fps)")
    parser.add_argument("--seed", type=int, default=1000, help="bootstrap seed and SmolVLA's main noise seed")
    parser.add_argument("--second-noise-seed", type=int, default=2000)
    args = parser.parse_args()

    import torch
    from lerobot.datasets import LeRobotDataset

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    ds = LeRobotDataset(TEST_REPO, root=os.path.expanduser(TEST_ROOT), revision=TEST_REVISION)
    frames = list(range(0, ds.meta.total_frames, args.stride))
    print(f"Test set: {ds.meta.total_episodes} episodes, {ds.meta.total_frames} frames; evaluating {len(frames)} frames on {device}")

    second = f"SmolVLA, noise seed {args.second_noise_seed}"
    results, timing = [], {}
    policy, pre, post = load("smolvla", SMOLVLA_PATH, device)
    for name, seed in (("SmolVLA", args.seed), (second, args.second_noise_seed)):
        df, times = run_policy(name, policy, pre, post, ds, frames, args.horizon, device, seed)
        results.append(df); timing[name] = times
    del policy
    policy, pre, post = load("act", S1_PATH, device)
    df, times = run_policy("S1", policy, pre, post, ds, frames, args.horizon, device, None)
    results.append(df); timing["S1"] = times

    per_frame = pd.concat(results)
    body = JOINTS[:5]
    per_frame["first_body"] = per_frame[[f"first_{j}" for j in body]].mean(axis=1)
    per_frame["sec_body"] = per_frame[[f"sec_{j}" for j in body]].mean(axis=1)
    by_ep = per_frame.groupby(["policy", "episode"]).mean(numeric_only=True).drop(columns="frame").reset_index()
    by_ep.insert(2, "spot", [SPOTS[e % 3] for e in by_ep.episode])
    RESULTS.mkdir(parents=True, exist_ok=True)
    by_ep.to_csv(RESULTS / "offline_eval_by_episode.csv", index=False, float_format="%.4f")

    # S1 against project 03's numbers: same model, test set, frames, and metric, so they should agree.
    p03 = pd.read_csv(P03_BY_EPISODE)
    p03 = p03[p03.policy == "S1"].set_index("episode")
    ours = by_ep[by_ep.policy == "S1"].set_index("episode")
    cols = [c for c in p03.columns if c.startswith(("first_", "sec_"))]
    s1_diff = float((ours[cols] - p03[cols]).abs().max().max())
    print(f"S1 against project 03: largest difference per episode and metric {s1_diff:.4f}")

    def per_ep(metric, pol):
        d = by_ep[by_ep.policy == pol]
        return dict(zip(d.episode, d[metric]))

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain", "projects/04-smolvla/src"], capture_output=True, text=True).stdout.strip():
        commit += " plus uncommitted changes to the code"
    pols = ["SmolVLA", second, "S1"]
    lines = [
        "# Offline comparison: action prediction error on the held-out test set (step 4)",
        "",
        f"Built by `src/offline_eval.py` (git commit `{commit}`). Test set: `{TEST_REPO}` @ `{TEST_REVISION[:8]}`, "
        f"{ds.meta.total_episodes} episodes (project 03's); every {args.stride}th frame ({len(frames)} frames per policy), on {device}. "
        "Models: SmolVLA = `causalerror/smolvla-so101-toy-to-bowl` @ `a299de1f`, the 20,000-step model (`src/fetch_model.py`); "
        "S1 = ACT, project 01's run 4 (`outputs/act_final`).",
        "",
        "Mean absolute error between predicted and recorded actions. Body joints in degrees (mean of the five); gripper on its "
        "0 to 100 scale. Mean over the 9 episodes, with a 95% bootstrap interval over episodes in brackets. Lower is closer to "
        f"how the operator did it. SmolVLA's rows differ only in the random noise its chunks start from (seeds {args.seed} and "
        f"{args.second_noise_seed}); the first is the main result.",
        "",
        "| Policy | First action, body | First second, body | First action, gripper | First second, gripper |",
        "|---|---|---|---|---|",
    ]
    for pol in pols:
        cells = []
        for m in ("first_body", "sec_body", "first_gripper", "sec_gripper"):
            mean, lo, hi = bootstrap(per_ep(m, pol), 5000, args.seed)
            cells.append(f"{mean:.2f} [{lo:.2f} to {hi:.2f}]")
        lines.append(f"| {pol} | " + " | ".join(cells) + " |")
    lines += ["", "## Paired differences (same episodes)", "",
              "Mean over episodes of (first minus second), with a 95% bootstrap interval. Negative means the first is closer "
              "to the recorded actions. An interval that includes 0 is no measurable difference. The last row is SmolVLA "
              "against itself with different noise: a difference smaller than that is within SmolVLA's own randomness.", "",
              "| Comparison | First action, body | First second, body | First action, gripper | First second, gripper |",
              "|---|---|---|---|---|"]
    for a, b in (("SmolVLA", "S1"), (second, "S1"), ("SmolVLA", second)):
        cells = []
        for m in ("first_body", "sec_body", "first_gripper", "sec_gripper"):
            pa, pb = per_ep(m, a), per_ep(m, b)
            mean, lo, hi = bootstrap({e: pa[e] - pb[e] for e in pa}, 5000, args.seed)
            cells.append(f"{mean:+.2f} [{lo:+.2f} to {hi:+.2f}]")
        lines.append(f"| {a} minus {b} | " + " | ".join(cells) + " |")
    lines += ["", "## Per joint, first second (mean over episodes)", "",
              "| Policy | " + " | ".join(JOINTS) + " |", "|---|" + "---|" * len(JOINTS)]
    for pol in pols:
        d = by_ep[by_ep.policy == pol]
        lines.append(f"| {pol} | " + " | ".join(f"{d[f'sec_{j}'].mean():.2f}" for j in JOINTS) + " |")
    lines += ["", "## By spot, first second (mean over 3 episodes each; descriptive only)", "",
              "| Policy | " + " | ".join(f"Spot {s}, body | Spot {s}, gripper" for s in SPOTS) + " |",
              "|---|" + "---|" * (2 * len(SPOTS))]
    for pol in pols:
        d = by_ep[by_ep.policy == pol]
        cells = [f"{d[d.spot == s][m].mean():.2f}" for s in SPOTS for m in ("sec_body", "sec_gripper")]
        lines.append(f"| {pol} | " + " | ".join(cells) + " |")
    lines += ["", "## Time per chunk on this Mac", "",
              f"Pre-processing, prediction, and post-processing, one observation at a time, after {WARMUP} warm-up predictions.", "",
              "| Policy | Predictions timed | Median | Slowest |", "|---|---|---|---|"]
    for pol in pols:
        t = timing[pol]
        lines.append(f"| {pol} | {len(t)} | {statistics.median(t) * 1000:.0f} ms | {max(t) * 1000:.0f} ms |")
    lines += ["", "## Notes", "",
              f"- **S1 matches project 03:** the largest difference from project 03's per-episode numbers is {s1_diff:.4f} "
              "(same model, test set, frames, and metric).",
              "- This measures imitation of new demonstrations of our own task, by the same operator. It does not measure "
              "success: a policy can be close on average and still miss a grasp. In project 03, S1, S2, and S3 scored about "
              "the same here and differed on the arm. The arm trials (step 6) decide.",
              "- Nine episodes: the intervals are wide, and differences may not be measurable here.",
              "- Each prediction starts from the recorded observation, so errors do not compound as they do on the arm.",
              "- SmolVLA builds its vision-language backbone from `HuggingFaceTB/SmolVLM2-500M-Video-Instruct`'s architecture "
              "(cached since step 2); the fine-tuned checkpoint then supplies all the weights."]
    (RESULTS / "offline_eval.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {RESULTS / 'offline_eval.md'} and {RESULTS / 'offline_eval_by_episode.csv'}")


if __name__ == "__main__":
    main()
