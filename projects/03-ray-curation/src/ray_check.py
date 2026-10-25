"""Check that LeRobot datasets, including video decoding, work inside Ray workers.

Starts a local Ray instance (usage statistics off, dashboard on 127.0.0.1 only), runs one
task per episode in parallel worker processes, and has each task decode the first frame
of its episode with LeRobot. On this Mac, video decoding needs FFmpeg 8 through
DYLD_FALLBACK_LIBRARY_PATH, which is only useful if Ray's workers inherit it.

Run from the repo root (does not touch the arm):
    uv run python projects/03-ray-curation/src/ray_check.py
If decoding fails because workers lack the variable, try:
    uv run python projects/03-ray-curation/src/ray_check.py --pass-dyld
"""

import argparse
import os

# Must be set before Ray is imported.
# No usage statistics leave this machine.
os.environ["RAY_USAGE_STATS_ENABLED"] = "0"
# Under `uv run`, Ray 2.59 by default copies the repo into /tmp/ray, builds a second virtual
# environment there (1.8 GB per session), and starts workers through `uv run`; on this Mac
# that loses DYLD_FALLBACK_LIBRARY_PATH. Off: workers use this .venv's Python directly.
os.environ["RAY_ENABLE_UV_RUN_RUNTIME_ENV"] = "0"

import ray  # noqa: E402

DYLD = "DYLD_FALLBACK_LIBRARY_PATH"
DEFAULT_ROOT = "~/.cache/huggingface/lerobot/causalerror/so101-toy-to-bowl_20261017_130943"


@ray.remote
def first_frame(repo_id: str, root: str, episode: int) -> dict:
    import platform

    from lerobot.datasets import LeRobotDataset

    info = {
        "episode": episode,
        "pid": os.getpid(),
        "machine": platform.machine(),
        "worker_has_dyld": DYLD in os.environ,
    }
    try:
        ds = LeRobotDataset(repo_id, root=root, episodes=[episode])
        frame = ds[0]
        info["images"] = {k: tuple(v.shape) for k, v in frame.items() if k.startswith("observation.images.")}
        info["ok"] = True
    except Exception as e:  # report, do not hide, the failure
        info["ok"] = False
        info["error"] = f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-id", default="causalerror/so101-toy-to-bowl")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="local copy of the dataset")
    parser.add_argument("--episodes", type=int, nargs="+", default=[0, 14, 29, 44], help="one per spot, plus the last")
    parser.add_argument("--num-cpus", type=int, default=4)
    parser.add_argument("--pass-dyld", action="store_true", help=f"pass {DYLD} to workers explicitly via runtime_env")
    args = parser.parse_args()

    root = os.path.expanduser(args.root)
    print(f"Driver: {DYLD} {'set' if DYLD in os.environ else 'NOT set'}")
    runtime_env = None
    if args.pass_dyld:
        if DYLD not in os.environ:
            raise SystemExit(f"--pass-dyld needs {DYLD} set in this shell first.")
        runtime_env = {"env_vars": {DYLD: os.environ[DYLD]}}

    ray.init(num_cpus=args.num_cpus, include_dashboard=True, dashboard_host="127.0.0.1", runtime_env=runtime_env)
    print(f"Ray {ray.__version__} started. Dashboard: http://127.0.0.1:8265")
    try:
        results = ray.get([first_frame.remote(args.repo_id, root, ep) for ep in args.episodes])
    finally:
        ray.shutdown()

    for r in results:
        status = "ok" if r["ok"] else "FAILED"
        detail = r.get("images") if r["ok"] else r["error"]
        print(f"episode {r['episode']:>2} | worker pid {r['pid']} | {r['machine']} | {DYLD} in worker: {r['worker_has_dyld']} | {status}: {detail}")
    print("all workers decoded video" if all(r["ok"] for r in results) else "some workers failed: see above")


if __name__ == "__main__":
    main()
