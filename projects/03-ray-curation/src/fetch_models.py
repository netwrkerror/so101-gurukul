"""Step 7, part A: download the S2 and S3 final checkpoints and prepare them for local LeRobot 0.6.0.

Each model is downloaded at the revision recorded in results/training_runs.md, then given the same
one-field conversion as project 01's run 4: the cloud image ran LeRobot 0.6.2, whose config.json adds
`"dtype": null`, a field 0.6.0 rejects (DECISIONS.md, 2026-10-17). S1 is run 4's converted copy,
already at outputs/act_final/.

Run from the repo root (does not touch the arm; downloads two private models):
    uv run python projects/03-ray-curation/src/fetch_models.py
"""

import json
from pathlib import Path

from huggingface_hub import snapshot_download

MODELS = {
    "s2": ("causalerror/act-so101-p03-s2-curated", "9537e8b420a56cf0f34b9d331f64d759fd490ca0", "outputs/act_s2"),
    "s3": ("causalerror/act-so101-p03-s3-random", "2ea29fd7512a7e1947ebf5d19e3e5e9f31db90da", "outputs/act_s3"),
}


def main() -> None:
    for name, (repo_id, revision, dest) in MODELS.items():
        dest = Path(dest)
        # Top-level files only: the final model and its processors (checkpoints/ holds the earlier ones).
        snapshot_download(repo_id, revision=revision, local_dir=dest, allow_patterns=["*.json", "*.safetensors"],
                          ignore_patterns=["checkpoints/*"])
        cfg_path = dest / "config.json"
        cfg = json.loads(cfg_path.read_text())
        removed = cfg.pop("dtype", "absent")
        cfg_path.write_text(json.dumps(cfg, indent=4))
        (dest / "SOURCE.json").write_text(json.dumps({"repo_id": repo_id, "revision": revision,
                                                      "converted": "removed config.json dtype (was " + str(removed) + ")"}, indent=2))
        print(f"{name}: {repo_id} @ {revision[:8]} -> {dest} (dtype: {removed})")

    # Load-and-predict check with local LeRobot 0.6.0, on a dummy observation (zeros and random images):
    # it shows each model loads and runs, not that its predictions are good (that is offline_eval.py).
    import torch
    from lerobot.policies.act.modeling_act import ACTPolicy
    from lerobot.policies.factory import make_pre_post_processors

    for name, path in [("s1", "outputs/act_final")] + [(n, m[2]) for n, m in MODELS.items()]:
        policy = ACTPolicy.from_pretrained(path).eval()
        # The S2 and S3 processors were saved on a cloud GPU ("cuda"); override the device as lerobot-rollout does.
        pre, post = make_pre_post_processors(policy.config, pretrained_path=path,
                                             preprocessor_overrides={"device_processor": {"device": str(policy.config.device)}})
        obs = {"observation.state": torch.zeros(6), "observation.images.wrist": torch.rand(3, 480, 640),
               "observation.images.front": torch.rand(3, 480, 640), "task": "Pick up the stuffed toy and place it in the bowl"}
        with torch.no_grad():
            chunk = post(policy.predict_action_chunk(pre(obs)))
        print(f"{name}: loads in LeRobot 0.6.0; predicted chunk shape {tuple(chunk.shape)}")


if __name__ == "__main__":
    main()
