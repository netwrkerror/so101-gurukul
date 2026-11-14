"""Step 7, part B: the offline metric. How closely does each policy predict new demonstrations?

Runs S1 (project 01's run 4), S2, and S3 over the held-out test set (9 episodes, step 5b) on the Mac.
It is our own data, so decoding it here is fine. For every `stride`-th frame, each policy predicts its
100-action chunk from that frame's observation (both cameras and the joint state). Two errors against
the recorded actions (what the operator actually did):
  - first action: the predicted next action against the recorded action at that frame,
  - first second: the first 30 predicted actions against the next 30 recorded ones (the chunk the arm
    would start playing out), cut short at the end of an episode.
Errors are mean absolute differences per joint: degrees for the five body joints, the 0 to 100 scale
for the gripper. Uncertainty: a bootstrap over episodes (only 9), including paired differences.

Run from the repo root (does not touch the arm):
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/ffmpeg@8/lib \
      uv run python projects/03-ray-curation/src/offline_eval.py
Outputs:
    projects/03-ray-curation/results/offline_eval.md               (committed)
    projects/03-ray-curation/results/offline_eval_by_episode.csv   (committed)
"""

import argparse
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

TEST_REPO = "causalerror/so101-toy-to-bowl-test"
TEST_REVISION = "0683b67ac70673f7ea9f07bcaa17dae6d5b6a410"
TEST_ROOT = "~/.cache/huggingface/lerobot/causalerror/so101-toy-to-bowl-test"
POLICIES = {"S1": "outputs/act_final", "S2": "outputs/act_s2", "S3": "outputs/act_s3"}
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
RESULTS = Path("projects/03-ray-curation/results")
TASK = "Pick up the stuffed toy and place it in the bowl"


def run_policy(name: str, path: str, ds, frames: list[int], horizon: int, device: str) -> pd.DataFrame:
    import torch
    from lerobot.policies.act.modeling_act import ACTPolicy
    from lerobot.policies.factory import make_pre_post_processors

    policy = ACTPolicy.from_pretrained(path).to(device).eval()
    pre, post = make_pre_post_processors(policy.config, pretrained_path=path,
                                         preprocessor_overrides={"device_processor": {"device": device}})
    actions = ds.hf_dataset.with_format("numpy")["action"]
    ep_of = ds.hf_dataset.with_format("numpy")["episode_index"]
    rows = []
    for i in frames:
        item = ds[i]
        obs = {k: item[k] for k in ("observation.state", "observation.images.wrist", "observation.images.front")}
        obs["task"] = TASK
        with torch.no_grad():
            chunk = post(policy.predict_action_chunk(pre(obs)))[0].float().cpu().numpy()  # (100, 6)
        ep = int(ep_of[i])
        end = int(ds.meta.episodes[ep]["dataset_to_index"])
        n = min(horizon, end - i)
        recorded = np.stack(actions[i:i + n])
        first = np.abs(chunk[0] - recorded[0])
        sec = np.abs(chunk[:n] - recorded).mean(axis=0)
        rows.append({"policy": name, "episode": ep, "frame": i,
                     **{f"first_{j}": float(v) for j, v in zip(JOINTS, first)},
                     **{f"sec_{j}": float(v) for j, v in zip(JOINTS, sec)}})
    return pd.DataFrame(rows)


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
    parser.add_argument("--seed", type=int, default=1000)
    args = parser.parse_args()

    import torch
    from lerobot.datasets import LeRobotDataset

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    ds = LeRobotDataset(TEST_REPO, root=os.path.expanduser(TEST_ROOT), revision=TEST_REVISION)
    frames = list(range(0, ds.meta.total_frames, args.stride))
    print(f"Test set: {ds.meta.total_episodes} episodes, {ds.meta.total_frames} frames; evaluating {len(frames)} frames on {device}")

    per_frame = pd.concat([run_policy(n, p, ds, frames, args.horizon, device) for n, p in POLICIES.items()])
    body = JOINTS[:5]
    per_frame["first_body"] = per_frame[[f"first_{j}" for j in body]].mean(axis=1)
    per_frame["sec_body"] = per_frame[[f"sec_{j}" for j in body]].mean(axis=1)
    by_ep = per_frame.groupby(["policy", "episode"]).mean(numeric_only=True).drop(columns="frame").reset_index()
    RESULTS.mkdir(parents=True, exist_ok=True)
    by_ep.to_csv(RESULTS / "offline_eval_by_episode.csv", index=False, float_format="%.4f")

    def per_ep(metric, pol):
        d = by_ep[by_ep.policy == pol]
        return dict(zip(d.episode, d[metric]))

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain", "projects/03-ray-curation/src"], capture_output=True, text=True).stdout.strip():
        commit += " plus uncommitted changes to the code"
    lines = [
        "# Offline metric: action prediction error on the held-out test set (step 7, part B)",
        "",
        f"Built by `src/offline_eval.py` (git commit `{commit}`). Test set: `{TEST_REPO}` @ `{TEST_REVISION[:8]}`, "
        f"{ds.meta.total_episodes} episodes; every {args.stride}th frame ({len(frames)} frames per policy), on {device}. "
        "Models: S1 = run 4 (`outputs/act_final`), S2 and S3 = the final checkpoints (`src/fetch_models.py`).",
        "",
        "Mean absolute error between predicted and recorded actions. Body joints in degrees (mean of the five); gripper on its "
        "0 to 100 scale. Mean over the 9 episodes, with a 95% bootstrap interval over episodes in brackets. Lower is closer to "
        "how the operator did it.",
        "",
        "| Policy | First action, body | First second, body | First action, gripper | First second, gripper |",
        "|---|---|---|---|---|",
    ]
    for pol in POLICIES:
        cells = []
        for m in ("first_body", "sec_body", "first_gripper", "sec_gripper"):
            mean, lo, hi = bootstrap(per_ep(m, pol), 5000, args.seed)
            cells.append(f"{mean:.2f} [{lo:.2f} to {hi:.2f}]")
        lines.append(f"| {pol} | " + " | ".join(cells) + " |")
    lines += ["", "## Paired differences (same episodes)", "",
              "Mean over episodes of (first policy minus second), with a 95% bootstrap interval. Negative means the first "
              "policy is closer to the recorded actions. An interval that includes 0 is no measurable difference.", "",
              "| Comparison | First second, body (degrees) | First second, gripper |", "|---|---|---|"]
    for a, b in (("S2", "S1"), ("S3", "S1"), ("S2", "S3")):
        cells = []
        for m in ("sec_body", "sec_gripper"):
            pa, pb = per_ep(m, a), per_ep(m, b)
            mean, lo, hi = bootstrap({e: pa[e] - pb[e] for e in pa}, 5000, args.seed)
            cells.append(f"{mean:+.2f} [{lo:+.2f} to {hi:+.2f}]")
        lines.append(f"| {a} minus {b} | " + " | ".join(cells) + " |")
    lines += ["", "## Per joint, first second (mean over episodes)", "",
              "| Policy | " + " | ".join(JOINTS) + " |", "|---|" + "---|" * len(JOINTS)]
    for pol in POLICIES:
        d = by_ep[by_ep.policy == pol]
        lines.append(f"| {pol} | " + " | ".join(f"{d[f'sec_{j}'].mean():.2f}" for j in JOINTS) + " |")
    lines += ["", "## Notes", "",
              "- This measures imitation of new demonstrations of our own task, by the same operator. It does not measure "
              "success: a policy can be close on average and still miss a grasp. The arm trials decide that.",
              "- Nine episodes: the intervals are wide, and differences between policies may not be measurable here.",
              "- Each prediction starts from the recorded observation, so errors do not compound as they do on the arm."]
    (RESULTS / "offline_eval.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {RESULTS / 'offline_eval.md'} and {RESULTS / 'offline_eval_by_episode.csv'}")


if __name__ == "__main__":
    main()
