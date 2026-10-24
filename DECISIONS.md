# Decisions

Dated log of real choices and the reasons for them. Newest entry last.

## 2026-10-11: uv environment, LeRobot pinned to LeLab's commit

**Decision:** The repo environment is a uv project on Python 3.12 (`>=3.12,<3.13`). LeRobot is pinned to git commit `30da8e687a6dfc617fcd94afc367ac7071c376ce` (tag v0.6.0) with extras `core-scripts`, `feetech`, `training`. `pyproject.toml` and `uv.lock` are committed.

**Why:**

- LeLab was installed as a uv tool and resolved LeRobot to this commit with these extras. The arms were set up and calibrated through LeLab, so matching it keeps calibration and motor code identical between the two environments.
- A commit hash cannot move; a tag can.
- uv is already on the machine and writes a lockfile with hashes.
- Python is capped below 3.13 to match LeLab's interpreter (3.12.13).

**Locked versions:** torch 2.11.0, torchvision 0.26.0, torchcodec 0.11.1 on macOS arm64, identical to LeLab's. No extra constraints were needed. The lock also carries a Linux fork with torch 2.11.0+cu128 and torchvision 0.26.0+cu128 from the PyTorch cu128 index, which has not been installed or tested.

**Dropped:** conda and plain pip with a requirements file (no lock with hashes, a second tool to maintain).

**Notes:** This machine had an x86_64 Homebrew uv (0.11.21) ahead of the arm64 uv (0.12.0) on PATH, because Homebrew here is the Intel install under `/usr/local`. The Homebrew uv was uninstalled. `required-version = ">=0.12.0"` stays as a guard against an older uv building the environment.

**Known warning:** On macOS, `opencv-python-headless` and `av` each bundle `libavdevice`, so every LeRobot CLI call prints an `objc` duplicate-class warning. LeLab's environment has the same duplicate. Left as is to stay matched to LeLab; to be checked at the first camera test.

## 2026-10-17: Project 01 task, cameras, and the first dataset

**Decision:** Project 01's task is picking up a stuffed toy and dropping it into a bowl at a fixed position. The toy starts from one of three spots (A, B, C). The dataset is `causalerror/so101-toy-to-bowl` (private; LeLab named it `so101-toy-to-bowl_20261017_130943`, renamed on the Hub the same day): 45 episodes, 15 per spot, recorded in LeLab with two cameras, `wrist` (Seeed, on the gripper) and `front` (Logitech, fixed in front, raised and angled down), both 640x480 at 30 fps.

**Why:**

- A puzzle cube was the planned object, but it was hard to grasp reliably during practice. The soft toy is more forgiving of a slightly off grasp. Dropped: the puzzle cube.
- The bowl stays fixed so the policy only has to handle where the toy starts, not where to drop it. Varying the bowl is left for later.
- Three spots with 15 episodes each give even coverage, and evaluation uses the same spots.
- Two views: the wrist camera sees the grasp up close, and the fixed front camera sees where the toy, bowl, and arm are. The front camera was first at table height, seeing the table almost edge-on; it was raised and angled down, and a laptop screen and a framed photo were moved out of its view.
- Cameras are named by viewpoint, not device, because the names become the dataset's image keys (`observation.images.wrist`, `observation.images.front`).

**Deviation from plan:** The brief planned to record from this repo with a committed config. The dataset was recorded in LeLab instead, so its settings have to be written down separately (project 01, step 3).

## 2026-10-17: FFmpeg 8 from Apple Silicon Homebrew for torchcodec

**Decision:** Install the Apple Silicon Homebrew in `/opt/homebrew` and `ffmpeg@8` from it, and set `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/ffmpeg@8/lib` in the shell profile. Homebrew's default `ffmpeg` (9.0.2) stays installed.

**Why:**

- Opening the dataset with `lerobot-dataset-viz` failed with "Could not load libtorchcodec". LeRobot decodes videos with torchcodec, which does not bundle FFmpeg and loads it from the system. There was no FFmpeg on the machine.
- The only Homebrew was the Intel one under `/usr/local`, running under Rosetta. Its libraries are x86_64 and cannot be loaded by the arm64 Python, and Rosetta is being phased out. torchcodec's library is built to look in `/opt/homebrew/opt/ffmpeg/lib`, the Apple Silicon Homebrew location.
- Homebrew's default `ffmpeg` is now 9 (`libavutil.61`). torchcodec 0.11.1 supports FFmpeg 4 to 8 (up to `libavutil.60`), so FFmpeg 9 still failed to load.
- `ffmpeg@8` (8.1.3) is keg-only, so it does not replace FFmpeg 9 and is not in torchcodec's search path. The fallback library path points torchcodec at it without overriding any library that is otherwise found.

**Result:** `import torchcodec.decoders` succeeds with the variable set.

**Dropped:**

- Upgrading torchcodec: LeRobot 0.6.0 requires `torchcodec<0.12`, so it would break the pin.
- PyAV as the decoding backend: training accepts `--dataset.video_backend=pyav`, but `lerobot-dataset-viz` has no such option.
- `brew link --force ffmpeg@8`: it would conflict with the linked FFmpeg 9, and torchcodec does not search the linked location anyway.

**Notes:** This is a system dependency outside `uv.lock`; the README setup lists it.

## 2026-10-17: Project 01 workspace marks

**Decision:** The three toy start spots (A, B, C) and the bowl's outline are taped on the table. The spots were checked against the first `front` frame of episodes 0, 14, and 29 in `lerobot-dataset-viz`.

**Why:** Evaluation has to start the toy where it started in the recorded episodes, with the bowl where it was, or the result is not comparable with the training data. The bowl was pushed by `shishya` during some recording attempts and put back on its outline each time, so the outline is the reference for evaluation too.

## 2026-10-17: Project 01 evaluation time limit raised to 45 seconds

**Decision:** An evaluation trial succeeds if the toy is in the bowl and released within 45 seconds, up from the 30 seconds in the approved brief.

**Why:** The recorded demonstrations last 11.6 to 30.1 seconds (mean 19.2, median 18.3). The longest, episode 39, is over 30 seconds, and four more are between 26 and 28.5. A 30-second limit would fail a policy for being as slow as the demonstrations, which measures speed rather than whether the task was learned. 45 seconds is the recording episode limit and about 1.5 times the slowest demonstration.

**Notes:** Decided from the demonstration lengths only, before any training or evaluation.

## 2026-10-17: Train project 01 on all 45 episodes

**Decision:** The ACT policy is trained on all 45 episodes of `causalerror/so101-toy-to-bowl` at revision `c6319da870f16f94db98e029ca0f4f654d585970`. No episode is excluded.

**Why:** Every episode was reviewed in `lerobot-dataset-viz` and marked `ok`: correct start spot, bowl on its outline, toy ends in the bowl, no hand in the `front` view, both feeds smooth, no failed attempt kept. Replaying episode 0 on `shishya` reproduced the demonstrated motion. See `projects/01-baseline-act/results/dataset_inspection.md`.

## 2026-10-17: No W&B logging for project 01 training

**Decision:** Project 01 trains with Weights & Biases logging off (LeRobot's default). Training metrics come from LeRobot's own log, saved to a gitignored file per run, and the key numbers go into `projects/01-baseline-act/results/training_runs.md`.

**Why:**

- W&B sends training metrics to an outside service and needs another account. Nothing in project 01 needs that: there is one run at a time, on one machine.
- LeRobot already prints the loss, gradient norm, and timing at a fixed interval, which is enough to plot a loss curve afterwards.
- Project 02 is about observability. Choosing a metrics stack belongs there, where it can cover training and serving together, rather than adopting one now by default.

**Revisit:** in project 02, or earlier if comparing several training runs side by side becomes painful from logs alone.

## 2026-10-17: Project 01 full training on Hugging Face Jobs, pending a cloud check

**Decision:** The full ACT training run moves from the Mac to Hugging Face Jobs, flavor `a10g-large` (1x A10G 24 GB, 12 vCPU, $1.50/hour), using LeRobot's built-in job support. The container image is pinned by digest: `huggingface/lerobot-gpu@sha256:fc48db80c040cfbc33e0a481e351b042a77422c527e5150138c354e4774e471f`. This holds only if a 50-step cloud check passes, including loading its checkpoint with local LeRobot 0.6.0.

**Why:**

- On the Mac, batch 8 runs at 0.95 s per step, so LeRobot's default 100,000 steps would take about 26 hours. Batch 32 does not fit in 24 GB of unified memory (run 2).
- A cloud GPU frees the Mac and rehearses the cloud workflow already planned for SmolVLA.
- `a10g-large` over `a10g-small`: the same GPU with 12 vCPUs instead of 4, because video decoding for each sample runs on the CPU.
- LeRobot creates the job's model repo as private.

**Version mismatch:** The image's only tags are `latest` and a pull-request build. Its build metadata shows it is built from LeRobot's source at build time; the `pyproject.toml` in the image says LeRobot 0.6.2, with torch 2.11.0, torchvision 0.26.0, and torchcodec 0.11.1, the same as this repo. This repo pins LeRobot 0.6.0, which is what evaluation uses. Pinning the digest keeps the check and the full run on identical code; the cloud check tests whether a 0.6.2 checkpoint loads in 0.6.0.

**If the check fails:** train locally on the Mac (batch 8, 100,000 steps, about 26 hours), or plan a LeRobot upgrade as its own decision.

**Check result (same day):** passed (run 3 in `projects/01-baseline-act/results/training_runs.md`). 0.16 s per step on `a10g-large`, loss within 1% of the Mac's at every logged step. The checkpoint loads in local 0.6.0 and predicts an action, with one conversion: remove `"dtype": null` from the downloaded `config.json`, a field 0.6.2 adds and 0.6.0 does not know. The decision stands, and evaluation will use a local copy of the final model converted this way.

## 2026-10-18: Project 01 evaluation settings

**Decision:** Evaluate with `lerobot-rollout` in episodic mode (`configs/eval_act.json`): 20 trials of up to 45 seconds, 30-second resets with the arm returning to its starting position, every trial recorded to the private dataset `causalerror/rollout_act_so101_toy_to_bowl_eval`, and a per-joint speed cap on the follower (`max_relative_target`). A 2-trial dry run (`configs/eval_act_dryrun.json`, private dataset `..._dryrun`) comes first and is not counted.

**Speed cap:** the cap limits, at each control step, how far the commanded position may be from the joint's current position, in degrees (gripper: its 0 to 100 scale). The values are about 1.5 times the largest leader-to-follower gap in the 25,876 recorded frames, rounded up to a multiple of 5, so no demonstrated motion would be clipped:

| Joint | Recorded median | p99 | max | Cap |
|---|---|---|---|---|
| shoulder_pan | 0.48 | 11.47 | 20.62 | 35 |
| shoulder_lift | 2.02 | 19.69 | 26.99 | 45 |
| elbow_flex | 2.20 | 20.31 | 29.98 | 45 |
| wrist_flex | 1.05 | 8.35 | 17.14 | 30 |
| wrist_roll | 0.44 | 5.71 | 15.03 | 25 |
| gripper | 0.64 | 20.10 | 45.43 | 70 |

**Why:**

- This is the first time the arm moves under a policy, and LeRobot sets no cap by default. The cap stops a sudden jump far outside anything demonstrated, without changing normal behaviour.
- Recording every trial keeps video evidence for each outcome next to the model and dataset, private like them.
- 30 seconds of reset is enough to note the outcome and place the toy on the next spot.

**Notes:** The gripper's large gap comes from grasping: the leader closes further than the follower can while the toy is between its fingers.

## 2026-10-18: Evaluate project 01 in the current lighting

**Decision:** The 20 counted trials run in the current lighting (blinds closed, evening or room light), not the recording's (open blinds, daylight around 1 pm). This departs from the brief, which lists lighting among the conditions held fixed between recording and evaluation.

**Why:** Chosen to evaluate now rather than wait for matching daylight. Both dry-run trials at spot A in this lighting succeeded, so the policy is not obviously broken by it.

**Consequence:** The evaluation is not fully like for like with the training data. The result is reported with this condition stated, and a lower success rate than the policy would get in recording-matched light cannot be ruled out. Two dry-run successes at one spot are too few to show the lighting has no effect. Evaluating again in matched light remains an option for later.

**Also changed since recording:** tape marks for the three spots and the bowl outline are now visible in the `front` view. The Intel Homebrew is still installed and should be retired separately.

## 2026-10-19: Project 02 metrics with prometheus_client, traces later

**Decision:** Project 02 instruments the policy server and robot client with `prometheus_client`, scraped by Prometheus and shown in Grafana. OpenTelemetry traces are deferred to a later step.

**Why:** A deliberate choice for simplicity. `prometheus_client` is the smallest dependency that gives Prometheus metrics, and metrics alone answer project 02's questions: loop rate, deadline misses, queue depth, and latency.

**Dropped, for now:** instrumenting through the OpenTelemetry metrics API with a Prometheus exporter. That would let traces be added later without touching the metric code. The accepted cost of choosing `prometheus_client` is that adding traces later means adding OpenTelemetry instrumentation then, and possibly moving the metrics onto it.

## 2026-10-19: Project 02 evaluates in project 01's evaluation lighting

**Decision:** Project 02's 20-trial evaluation runs in the same lighting as project 01's evaluation (blinds closed, evening or room light), not the recording's daylight.

**Why:** Project 02 measures what serving costs. Keeping the lighting the same as the 10/20 run makes serving the main change between the two evaluations.

## 2026-10-19: Project 02 async inference setup and client settings

**Decision:** Add LeRobot's `async` extra to the environment (`lerobot[core-scripts,feetech,training,async]`), which brings in `grpcio` and `matplotlib`, and serve the project 01 policy with LeRobot's own `policy_server` and `robot_client` from `lerobot.async_inference`, launched from committed configs in `projects/02-serving-observability/configs/`. Client settings:

| Setting | Value |
|---|---|
| `actions_per_chunk` | 100 |
| `chunk_size_threshold` | 0.0 |
| `aggregate_fn_name` | `latest_only` |
| `policy_device` | `mps` |
| `fps` | 30 |
| `robot.max_relative_target` | Project 01's per-joint cap |

**Why:**

- The client asks for a new chunk when its action queue falls to `chunk_size_threshold` of a chunk, and blends overlapping chunks with `aggregate_fn_name`. A threshold of 0 means a new chunk is requested only once the queue is empty, so chunks never overlap and are played out whole. That matches project 01's synchronous rollout, which keeps serving as the main difference between the two evaluations.
- The cost is a short pause at the end of each chunk while the next one is computed, as in project 01, where one step per chunk took about 51 ms. Project 02's metrics will measure it.
- The server binds to `localhost` only: it deserialises incoming data with `pickle`, which is unsafe for anything untrusted.

**Found in the source:** the stock `robot_client` has no trials, time limit, return to start, or recording, and it switches the motors off immediately when stopped. Project 02's step 3 adds a runner in `src/` for these, wrapping `RobotClient` without editing LeRobot.

## 2026-10-19: Project 02 client runner design

**Decision:** Evaluation through the server uses our own runner (`projects/02-serving-observability/src/runner.py`), which subclasses LeRobot's `RobotClient` instead of editing it, with an instrumented server (`src/server.py`) that subclasses `PolicyServer`. Metrics use `prometheus_client` (added to the environment), on localhost ports 9101 (client) and 9102 (server). The runner step now comes before the container step.

**What the runner adds:**

- **Trials:** a fixed A, B, C schedule; each trial has a 45-second limit and starts with the operator's key press.
- **Fresh starts:** before each trial, both sides are reset. The server's `Ready` call clears its state without reloading the model, and the client's queue and step counter are cleared.
- **The policy paused between trials,** so the toy is reset next to a still arm.
- **Safe stops:** after every trial, and on quit or Ctrl+C, the arm moves back to the session's start pose in a straight line over 3 seconds, under the speed cap. Only then does the client disconnect.
- **Trial log:** one JSON line per trial in `outputs/p02_trials.jsonl`. Outcomes follow the arrow-key rules: `n` after a success, `r` voids a setup mistake, a timeout is a failure. Failure types are added afterwards, as in project 01.

**Behaviour kept from the stock client:** the control loop sends queued actions and asks for a chunk under the same rule. The one change is that the observation is read once at the start of every step, to measure tracking error, and reused if a chunk is due; the stock client reads it only when sending.

**Added after the first real trials:** the runner waits between steps with LeRobot's `precise_sleep`, as `lerobot-rollout` does, instead of the stock client's `time.sleep`. With `time.sleep` the measured loop ran at about 27 Hz (mean period 36.9 ms; 2.7 ms of work per step), because sleeps overshoot by a few milliseconds on macOS. Project 01 ran at 30 Hz, so this keeps the control rate the same between the two evaluations.

**Why:**

- The stock client has no trials, time limit, or reset phase, and cuts motor power on Ctrl+C.
- In project 02's step 1 dry run, a stuck policy repeated the same motion about six times, and the toy had to be reset next to a moving arm.
- Running the runner before the container means every later arm run gets these safe stops.

**Dropped, for now:**

- **Recording trials to a dataset:** it needs an observation read and a saved frame every step, which may change loop timing; deferred until it can be measured.
- **Camera frame age:** LeRobot's camera interface does not expose frame timestamps.

## 2026-10-20: Project 02 evaluates with the native policy server

**Decision:** The counted evaluation through the served setup uses the native policy server (`src/server.py` with `uv`, policy on `mps`). The container (`projects/02-serving-observability/Dockerfile`) is kept as a validated deliverable, not used for evaluation.

**Why:** In shadow-mode measurements (`projects/02-serving-observability/results/latency_native_vs_container.md`), the containerized server took a mean of 344 ms per chunk against 88 ms natively, so the arm would wait about 0.36 s at every chunk boundary instead of about 0.09 s. Project 01 waited about 0.05 s. Using the container would add a large second difference from project 01, on top of serving itself. Docker on macOS cannot use the Apple GPU, so the container runs ACT on the CPU, inside Docker Desktop's virtual machine.

**Container details:**

- Built from the repo's `uv.lock` in two stages; the build stage has the compiler `evdev` needs.
- 7.69 GB, mostly torch's CUDA build and NVIDIA's libraries. On Linux the lock resolves torch to CUDA 12.8, so the same image would use an NVIDIA GPU on a Linux GPU machine. That is untested.
- Runs as a non-root user, with ports published on the host's loopback only and the model mounted read-only.
- `.dockerignore` is an allowlist, so `.env`, `outputs/`, and private files never reach the build.

**Dropped:** a separate CPU-only lock for a smaller image. It would be a second environment definition, and a torch build that differs from the one used everywhere else.

## 2026-10-20: Project 02 metrics stack

**Decision:** Prometheus (`prom/prometheus:v3.5.0`) and Grafana (`grafana/grafana:12.1.0`) run with Docker Compose from `projects/02-serving-observability/observability/`.

- **Scraping:** Prometheus scrapes the runner (9101) and the policy server (9102) every 2 seconds, through `host.docker.internal`, because the runner and server run natively on the Mac.
- **Ports:** both tools are published on `127.0.0.1` only.
- **Grafana setup:** the data source and the dashboard (`grafana/dashboards/gurukul.json`) are provisioned from files. The admin password comes from `GRAFANA_ADMIN_PASSWORD` in `.env`. Anonymous access and sign-up are off.
- **Alert rules:**
  - `ControlRateLow`: under 28 Hz for 10 seconds during a trial.
  - `ChunkRoundTripHigh`: the 90th percentile of the chunk round trip over 300 ms for 10 seconds.
- **Finer histogram buckets:** the latency buckets now step every 10 ms from 10 to 100 ms, then 125, 150, 200, 250, 300, 350, 400, 500 ms, and up, so percentiles in the measured range are reported more precisely.

**Why:**

- **The 2-second scrape interval:** a 45-second trial needs more than three samples; Prometheus's default is 15 seconds.
- **28 Hz:** training and project 01 ran at 30 Hz, and the `time.sleep` problem in step 2 showed up as about 27 Hz.
- **300 ms:** the native server's round trip averaged 103 ms and the containerized server's 379 ms (step 3), so the threshold separates the two.
- **Pinned versions:** reproducible, and released long enough ago to be stable.
- **Localhost only, and the password kept out of git,** following the repo's rules.

**Changed after the first dashboard sessions (2026-10-24):**

- **`ControlRateLow` false alarm.** It went pending at the start of every trial: the 10-second rate window still covered idle time, and the rate read as low as 1.0 Hz. It now applies only once the trial has been active for the last 12 seconds.
- **`ChunkRoundTripHigh` false alarm.** It fired early in a native session, because the session's first chunk was slow (the median briefly read 0.45 s) while the window held only one to three chunks. It now also requires at least 5 chunks in the window.
- **A warm-up request.** The runner now sends one throwaway observation before the first trial, so no trial pays the first-inference cost. The warm-up chunk is kept out of the round-trip metrics and reported separately as `gurukul_client_warmup_seconds`.
- **Finer loop-period buckets.** Prometheus estimates percentiles by interpolating within a bucket, so with edges at 33.3 and 36 ms, a true mean of 33.4 ms was shown as a p50 of about 34.7 ms. The buckets now step at 32, 33, 33.3, 33.5, 34, 35, and 36 ms, and the dashboard also plots the exact mean.
