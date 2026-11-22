"""Step 5, part A: does the policy server feed each policy what the offline evaluation feeds it?

Runs test-set frames through three paths, with the same noise for SmolVLA, and compares the chunks:
  - offline: the frame straight into the policy's preprocessing, as in src/offline_eval.py (and training);
  - served (ours): project 02's server class (`InstrumentedPolicyServer`), with its image-size fix and
    the camera-name mapping the runner now sends; the frame goes in as a robot would send it
    (joint positions and 480x640 uint8 camera images);
  - served (stock, cameras renamed): LeRobot's own `PolicyServer`, with the cameras named camera1 and
    camera2 on the robot side, the only way to reach SmolVLA's slots without the runner's mapping.
    Its resize step squashes each image to the config's 256x256 before SmolVLA's own preprocessing.
The server's code runs in this process (no gRPC, no arm): its policy-loading handler and its
`_predict_action_chunk`, the function a running server calls for every chunk.

Run from the repo root, after src/fetch_model.py (does not touch the arm):
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/ffmpeg@8/lib \
      uv run python projects/04-smolvla/src/serving_check.py
Output: projects/04-smolvla/results/serving_check.md
"""

import os
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "projects/02-serving-observability/src")

TEST_REPO = "causalerror/so101-toy-to-bowl-test"
TEST_REVISION = "0683b67ac70673f7ea9f07bcaa17dae6d5b6a410"
TEST_ROOT = "~/.cache/huggingface/lerobot/causalerror/so101-toy-to-bowl-test"
TASK = "Pick up the stuffed toy and place it in the bowl"
RENAME = {"observation.images.front": "observation.images.camera1", "observation.images.wrist": "observation.images.camera2"}
POLICIES = {  # name: (type, path, actions per chunk, rename map sent by the runner), as in configs/runner_*.json
    "SmolVLA": ("smolvla", "outputs/smolvla_final", 50, RENAME),
    "S1 (ACT)": ("act", "outputs/act_final", 100, {}),
}
N_FRAMES = 18
SEED = 1000
RESULTS = Path("projects/04-smolvla/results")


class _Context:  # what the server's handlers read from a gRPC context
    def peer(self):
        return "serving_check"


def robot_features(ds, cameras: dict[str, str]) -> dict:
    """The observation features a so101 follower with our cameras reports, as the client sends them."""
    from lerobot.utils.feature_utils import hw_to_dataset_features

    hw = {name: float for name in ds.meta.features["observation.state"]["names"]}
    for robot_name in cameras:
        hw[robot_name] = (480, 640, 3)
    return hw_to_dataset_features(hw, "observation", use_video=False)


def raw_observation(item, ds, cameras: dict[str, str]) -> dict:
    """A dataset frame as the robot would send it: joint positions and HxWxC uint8 images."""
    names = ds.meta.features["observation.state"]["names"]
    raw = {name: float(v) for name, v in zip(names, item["observation.state"])}
    for robot_name, dataset_key in cameras.items():
        raw[robot_name] = (item[dataset_key] * 255).round().byte().permute(1, 2, 0).numpy()
    raw["task"] = TASK
    return raw


def main() -> None:
    import torch
    from lerobot.async_inference.helpers import RemotePolicyConfig, TimedObservation
    from lerobot.async_inference.policy_server import PolicyServer
    from lerobot.datasets import LeRobotDataset
    from lerobot.transport import services_pb2  # type: ignore
    from metrics import ServerMetrics
    from server import InstrumentedPolicyServer, InstrumentedServerConfig

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    ds = LeRobotDataset(TEST_REPO, root=os.path.expanduser(TEST_ROOT), revision=TEST_REVISION)
    frames = [int(i) for i in np.linspace(0, ds.meta.total_frames - 1, N_FRAMES)]
    ours_cams = {"front": "observation.images.front", "wrist": "observation.images.wrist"}
    stock_cams = {"camera1": "observation.images.front", "camera2": "observation.images.wrist"}
    metrics = ServerMetrics()  # one set: the metrics registry accepts each name once

    def chunk_from(server, raw) -> np.ndarray:
        timed = server._predict_action_chunk(TimedObservation(timestamp=0.0, observation=raw, timestep=0))
        return torch.stack([a.get_action() for a in timed]).float().numpy()

    rows, notes = [], []
    for name, (kind, path, per_chunk, rename_map) in POLICIES.items():
        server = InstrumentedPolicyServer(InstrumentedServerConfig(), metrics)
        spec = RemotePolicyConfig(kind, path, robot_features(ds, ours_cams), per_chunk, device, dict(rename_map))
        server.SendPolicyInstructions(services_pb2.PolicySetup(data=pickle.dumps(spec)), _Context())
        policy, pre, post = server.policy, server.preprocessor, server.postprocessor

        # The stock server, sharing the loaded policy and processors; its cameras are named camera1 and
        # camera2, so the (ours) rename map finds nothing to rename and the names already match.
        stock = PolicyServer(InstrumentedServerConfig())
        stock.policy, stock.preprocessor, stock.postprocessor = policy, pre, post
        stock.device, stock.policy_type, stock.actions_per_chunk = device, kind, per_chunk
        stock.lerobot_features = robot_features(ds, stock_cams)
        stock_shape = tuple(next(iter(policy.config.image_features.values())).shape)
        # ACT's config names the cameras front and wrist, so it cannot take camera1/camera2: its stock
        # path is the same as ours, with the config's (unchanged) 480x640.
        stock_ok = kind == "smolvla"

        diffs = {"served (ours)": [], "served (stock, cameras renamed)": []}
        for k, i in enumerate(frames):
            item = ds[i]
            obs = {key: item[key] for key in ("observation.state", "observation.images.front", "observation.images.wrist")}
            obs["task"] = TASK
            torch.manual_seed(SEED + k)
            with torch.no_grad():
                offline = post(policy.predict_action_chunk(pre(obs)))[0, :per_chunk].float().cpu().numpy()
            torch.manual_seed(SEED + k)
            diffs["served (ours)"].append(np.abs(chunk_from(server, raw_observation(item, ds, ours_cams)) - offline))
            if stock_ok:
                torch.manual_seed(SEED + k)
                diffs["served (stock, cameras renamed)"].append(np.abs(chunk_from(stock, raw_observation(item, ds, stock_cams)) - offline))
        for path_name, d in diffs.items():
            if not d:
                continue
            d = np.stack(d)  # (frames, chunk, joints)
            rows.append((name, path_name, len(d), d.shape[1], float(d[..., :5].mean()), float(d[..., :5].max()),
                         float(d[..., 5].mean()), float(d[..., 5].max())))
            print(f"{name}, {path_name}: body mean {rows[-1][4]:.4f}, max {rows[-1][5]:.4f}; gripper mean {rows[-1][6]:.4f}")
        notes.append(f"{name}: config image size {stock_shape}")
        del server, stock, policy

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    if subprocess.run(["git", "status", "--porcelain", "projects/04-smolvla/src", "projects/02-serving-observability/src"],
                      capture_output=True, text=True).stdout.strip():
        commit += " plus uncommitted changes to the code"
    lines = [
        "# Serving check: the policy server against the offline path (step 5, part A)",
        "",
        f"Built by `src/serving_check.py` (git commit `{commit}`), on {device}, without the arm. {N_FRAMES} frames spread "
        f"over the test set (`{TEST_REPO}` @ `{TEST_REVISION[:8]}`), each predicted three ways with the same noise "
        "(SmolVLA): straight into the policy, as in the offline evaluation and in training; through project 02's server "
        "class with its image-size fix and the runner's camera mapping; and through LeRobot's stock server with the "
        "cameras named camera1 and camera2. The server paths get each frame as the robot sends it (joint positions, "
        "480x640 uint8 images).",
        "",
        "Difference from the offline chunk, over every action of every chunk: body joints in degrees, gripper on its "
        "0 to 100 scale.",
        "",
        "| Policy | Path | Frames | Actions per chunk | Body, mean | Body, largest | Gripper, mean | Gripper, largest |",
        "|---|---|---|---|---|---|---|---|",
        *[f"| {p} | {s} | {n} | {c} | {bm:.4f} | {bx:.4f} | {gm:.4f} | {gx:.4f} |" for p, s, n, c, bm, bx, gm, gx in rows],
        "",
        "## Notes",
        "",
        *[f"- {n}." for n in notes],
        "- The stock server cannot serve SmolVLA with our camera names at all: it resizes each image to the size the "
        "policy's config gives for that name before renaming, and the config has no `front` or `wrist` (a KeyError). "
        "Naming the cameras camera1 and camera2 avoids that, but then the resize squashes them to 256x256.",
        "- ACT's stock path is not run separately: its config declares the cameras' 480x640 under their own names, so "
        "the stock resize and ours are the same step.",
    ]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "serving_check.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {RESULTS / 'serving_check.md'}")


if __name__ == "__main__":
    main()
