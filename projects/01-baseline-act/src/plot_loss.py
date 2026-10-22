"""Plot the training loss of project 01's run 4 from its Hugging Face Jobs log.

LeRobot logs one line every `log_freq` steps, for example:
    step:20K smpl:160K ep:2K epch:6.18 loss:0.156 ...
The `step:` field is rounded for display (five consecutive lines can all read
`step:20K`), so the exact step is counted instead: the k-th loss line is step
k * log_freq. The rounded field is only used as a check.

Run from the repo root:
    uv run python projects/01-baseline-act/src/plot_loss.py
"""

import argparse
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

RESULTS = Path("projects/01-baseline-act/results")
LOSS_LINE = re.compile(r"ot_train\.py:\d+ step:(\S+) smpl:\S+ ep:\S+ epch:\S+ loss:([0-9.]+)")
# Values recorded in results/training_runs.md, run 4.
RECORDED = {20_000: 0.157, 40_000: 0.110, 60_000: 0.090, 80_000: 0.077, 100_000: 0.067}


def config_int(text: str, key: str) -> int:
    # Top-level keys of the logged config start their line with one space; nested keys
    # (for example 'steps' under 'gradient_accumulation') are indented further.
    match = re.search(rf"^ '{key}': (\d+),", text, re.MULTILINE)
    if not match:
        sys.exit(f"Could not find '{key}' in the log's config dump.")
    return int(match.group(1))


def displayed_step(field: str) -> float:
    """Turn LeRobot's rounded step field ('200', '20K', '1.2M') into a number."""
    scale = {"K": 1e3, "M": 1e6}.get(field[-1], 1)
    return float(field[:-1] if scale != 1 else field) * scale


def parse(log_path: Path) -> tuple[list[int], list[float]]:
    text = log_path.read_text(errors="replace")
    log_freq = config_int(text, "log_freq")
    total_steps = config_int(text, "steps")
    matches = LOSS_LINE.findall(text)

    expected = total_steps // log_freq
    if len(matches) != expected:
        sys.exit(f"Found {len(matches)} loss lines, expected {expected} ({total_steps} steps / log_freq {log_freq}).")

    steps, losses = [], []
    for k, (field, loss) in enumerate(matches, start=1):
        step = k * log_freq
        shown = displayed_step(field)
        # The display rounds to the nearest unit of its suffix (1 for plain numbers, 1,000 for K).
        tolerance = 0 if shown < 1000 else 500
        if abs(step - shown) > tolerance:
            sys.exit(f"Line {k}: counted step {step} does not match the logged 'step:{field}'.")
        steps.append(step)
        losses.append(float(loss))
    return steps, losses


def check(steps: list[int], losses: list[float]) -> None:
    by_step = dict(zip(steps, losses))
    print(f"{'step':>8} {'parsed':>8} {'recorded':>9} {'diff':>8}")
    for step, recorded in RECORDED.items():
        parsed = by_step[step]
        print(f"{step:>8} {parsed:>8.3f} {recorded:>9.3f} {parsed - recorded:>+8.3f}")
    print(f"{len(steps)} points, steps {steps[0]} to {steps[-1]}, loss {max(losses):.3f} to {min(losses):.3f}")


def plot(steps: list[int], losses: list[float], out_path: Path) -> None:
    # 7 x 4.2 inches at 200 dpi = 1400 x 840 px: Medium's column width at 2x.
    fig, ax = plt.subplots(figsize=(7, 4.2), dpi=200, facecolor="white")
    ax.set_facecolor("white")
    ax.plot(steps, losses)
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: "0" if x == 0 else f"{x / 1000:.0f}k"))
    ax.set_xlabel("Training step")
    ax.set_ylabel("Loss (log scale)")
    ax.set_title("ACT training loss, 100k steps on an A10G")
    fig.tight_layout()
    fig.savefig(out_path, facecolor="white")
    print(f"Saved {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path, default=RESULTS / "run4_train.log")
    parser.add_argument("--out", type=Path, default=RESULTS / "run4_loss.png")
    args = parser.parse_args()

    steps, losses = parse(args.log)
    check(steps, losses)
    plot(steps, losses, args.out)


if __name__ == "__main__":
    main()
