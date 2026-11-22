"""Step 4, part A: download the fine-tuned SmolVLA and prepare it for local LeRobot 0.6.0.

The model is downloaded at the revision recorded in results/training_runs.md. The cloud image ran
LeRobot 0.6.2, so two files get small fixes for 0.6.0:
  - config.json: drop `"dtype"`, a field 0.6.0 rejects (the same fix as ACT, DECISIONS.md, 2026-10-17);
  - policy_preprocessor.json: the tokenizer step names its tokenizer `"tokenizer"`, a folder 0.6.2 saved
    next to the model; 0.6.0 would look for a Hub repo of that name, so it is pointed at the local folder.
Both fixes are recorded in outputs/smolvla_final/SOURCE.json. Then a load-and-predict check.

Run from the repo root (does not touch the arm; downloads about 0.9 GB once):
    uv run python projects/04-smolvla/src/fetch_model.py
"""

import json
from pathlib import Path

from huggingface_hub import snapshot_download

REPO = "causalerror/smolvla-so101-toy-to-bowl"
REVISION = "a299de1f1bf2b52fb171b60f2b1e88d2c07b6bab"
DEST = Path("outputs/smolvla_final")
BASE_TOKENIZER = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"  # what the pretrained base's preprocessor names
TASK = "Pick up the stuffed toy and place it in the bowl"


def main() -> None:
    # Top-level files only: the final model, its processors, and its tokenizer (checkpoints/ holds the earlier ones).
    snapshot_download(REPO, revision=REVISION, local_dir=DEST, allow_patterns=["*.json", "*.safetensors", "tokenizer/*"],
                      ignore_patterns=["checkpoints/*"])
    fixes = []

    cfg_path = DEST / "config.json"
    cfg = json.loads(cfg_path.read_text())
    if "dtype" in cfg:
        fixes.append(f"removed config.json dtype (was {cfg.pop('dtype')})")
        cfg_path.write_text(json.dumps(cfg, indent=4))

    pre_path = DEST / "policy_preprocessor.json"
    pre = json.loads(pre_path.read_text())
    tok_dir = (DEST / "tokenizer").resolve()
    for step in pre["steps"]:
        if step.get("registry_name") == "tokenizer_processor" and step["config"].get("tokenizer_name") == "tokenizer":
            step["config"]["tokenizer_name"] = str(tok_dir)
            fixes.append("pointed policy_preprocessor.json tokenizer_name at the downloaded tokenizer/ folder")
    pre_path.write_text(json.dumps(pre, indent=4))

    # Does the saved tokenizer tokenize our task as the base's does? Its tokenizer.json is not byte-identical:
    # 0.6.2 re-saved it with padding and truncation (48 tokens) stored in the file, and without the base's
    # digit-splitting step. Neither matters for a 12-token task with no digits; this checks the token ids.
    from transformers import AutoTokenizer

    text = TASK + "\n"  # SmolVLA's preprocessor appends a newline to the task
    ours, base = AutoTokenizer.from_pretrained(str(tok_dir)), AutoTokenizer.from_pretrained(BASE_TOKENIZER)
    same = ours(text)["input_ids"] == base(text)["input_ids"] and ours.get_vocab() == base.get_vocab()
    source = DEST / "SOURCE.json"
    if not fixes and source.exists():  # a re-run on already-fixed files keeps the first run's record
        fixes = json.loads(source.read_text()).get("converted", [])
    source.write_text(json.dumps({"repo_id": REPO, "revision": REVISION, "converted": fixes or ["already converted"],
                                                  "task_tokens_and_vocab_same_as_base": same}, indent=2))
    print(f"{REPO} @ {REVISION[:8]} -> {DEST}")
    for f in fixes or ["already converted"]:
        print(f"  {f}")
    print(f"  task token ids and vocabulary same as {BASE_TOKENIZER}'s: {same}")

    # Load-and-predict check with local LeRobot 0.6.0, on a dummy observation (zeros and random images):
    # it shows the model loads and runs, not that its predictions are good (that is offline_eval.py).
    import torch
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    policy = SmolVLAPolicy.from_pretrained(str(DEST)).to(device).eval()
    # The processors were saved on a cloud GPU ("cuda"); override the device as lerobot-rollout does.
    pre_p, post_p = make_pre_post_processors(policy.config, pretrained_path=str(DEST),
                                             preprocessor_overrides={"device_processor": {"device": device}})
    obs = {"observation.state": torch.zeros(6), "observation.images.wrist": torch.rand(3, 480, 640),
           "observation.images.front": torch.rand(3, 480, 640), "task": TASK}
    with torch.no_grad():
        chunk = post_p(policy.predict_action_chunk(pre_p(obs)))
    print(f"Loads in LeRobot 0.6.0 on {device}; predicted chunk shape {tuple(chunk.shape)}")


if __name__ == "__main__":
    main()
