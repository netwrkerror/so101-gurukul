# Project 03: Curating robot data with Ray

Status: approved, 2026-10-24.

## Goal

A Ray pipeline that scores robot demonstrations for quality, coverage, and redundancy across our 45 episodes and public SO-100/SO-101 datasets from the Hugging Face Hub; a training set chosen with those scores; an ACT policy retrained on it; and a measurement, offline and on the arm, of whether the curated data makes the robot succeed more often than project 01's 10/20.

## Why it matters

A policy learns only what its demonstrations show it. Most failures in projects 01 and 02 came from situations the 45 demonstrations never covered, such as the toy pushed off its mark. Robot learning teams spend much of their effort on data: finding failed or low-quality demonstrations, removing near-duplicates, spotting gaps in coverage, and deciding which other people's data helps. That needs every episode's video decoded and analyzed, which is slow one episode at a time and independent per episode, so it suits a distributed engine such as Ray.

## Steps

Ordered, each one branch and PR. Steps 5 (recording the held-out test episodes) and 7 move the arm.

| # | Step | Branch | Done when |
|---|---|---|---|
| 1 | Add Ray to the environment | `p03/environment` | Ray (with Ray Data) pinned in `pyproject.toml`; the lock changes only by adding packages (LeRobot, torch, torchvision, torchcodec unchanged); a local Ray instance starts on the Mac; `DECISIONS.md` entry |
| 2 | Catalog public datasets | `p03/catalog` | A Ray job reads the metadata of candidate public SO-100/SO-101 datasets (format version, robot type, fps, camera names and sizes, episode count, task strings, license) without downloading videos; a committed catalog of candidates with a compatibility flag for merging with ours |
| 3a | Episode scoring from joint data | `p03/scoring` | A Ray pipeline downloads only the joint data (`data/*.parquet`, no video) of our 45 episodes and every task-relevant compatible public dataset, and computes per-episode trajectory scores (below) with Ray Data; throughput measured (episodes per minute, locally) |
| 3b | Episode scoring from video | `p03/scoring-video` | For a shortlist chosen from 3a's scores, within about 50 GB of video, the camera and embedding scores (below); the download-security measures (see Out of scope / later) decided first |
| 4 | Check the scores against a manual review | `p03/review` | A sample of episodes is labeled by hand (good, bad, why); agreement between the scores and the labels is reported |
| 5 | Build the training sets and the test set | `p03/curated-set` | S2 and S3 (below) are each merged into one dataset with `lerobot-edit-dataset`, uploaded privately to the Hub, and documented episode by episode; about 9 held-out test episodes (3 per spot) are recorded and uploaded privately |
| 6 | Retrain ACT | `p03/train` | Two runs, on S2 and on S3, on HF Jobs with run 4's settings (100,000 steps, batch 8, seed 1000), only the dataset changed; checkpoints private on the Hub |
| 7 | Evaluate | `p03/eval` | Offline metric (below) for S1, S2, and S3, and 20 arm trials each for the S2 and S3 policies under project 01's protocol, using `lerobot-rollout` in-process as in project 01, so the comparison with 10/20 is like for like |
| 8 | Write-up | `p03/writeup` | README and a results summary match the logs |

Episode scores, proposed for step 3:

- **Basic:** length, fraction of time the arm is idle, number of gripper close and open events.
- **Smoothness:** jerk (how abruptly joint motion changes), and hesitations (pauses mid-motion).
- **Camera quality:** frame sharpness and brightness, and frozen or dropped frames.
- **Visual embeddings:** image features from a pretrained vision model, on a few frames per episode, used for near-duplicate detection and for coverage (clustering where the object starts, and how the scene looks).

Training sets:

- **S1, ours only:** the existing 45 episodes. Project 01's policy is already trained on this, so it needs no new run.
- **S2, ours plus curated public episodes.**
- **S3, the control: ours plus the same number of public episodes, chosen at random** from the same compatible pool, without curation.

Comparing S2 with S1 shows whether adding curated data helps. Comparing S2 with S3 shows whether the *curation* helps, beyond simply adding more data. Without S3, a better S2 result could not be credited to the curation rather than to the extra data. It costs a second training run (about $7) and a second 20-trial evaluation.

Offline metric: each policy's action prediction error on a small held-out test set of about 9 new episodes, 3 per spot, recorded for this project. Using some of the existing 45 as a test set would remove them from training and break the comparison with project 01.

## Definition of done

- The pipeline has run over our episodes and the compatible public subset, with throughput reported.
- Score agreement with the manual review is reported.
- The curated set is documented: which episodes, from which datasets, and why.
- The S2 and S3 policies are evaluated offline and in 20 arm trials each, under project 01's protocol and its evaluation lighting; project 01's policy (S1) is evaluated offline on the same test set.
- The results are reported next to project 01's 10/20, and S2 next to S3. There is no success target: with 20 trials, only a large difference (for example 15/20 against 10/20) would be meaningful, and the write-up says so.

Evaluation protocol: as in project 01. Same spots, bowl, toy, cameras, task string, 45-second limit, 7/7/6 trials in the fixed A, B, C order, the same failure types and key rules, `lerobot-rollout` with trial recordings, and the speed cap.

## Inputs and outputs

- Inputs:
  - `causalerror/so101-toy-to-bowl` (our 45 episodes).
  - Public SO-100/SO-101 datasets on the Hub: 6,790 are tagged `so100` or `so101` (an earlier estimate of about 3,800 came from a listing capped at 2,000 per tag). Step 2's catalog found 1,006 compatible datasets (93,336 episodes), of which 807 (78,847 episodes) are task-relevant. See `results/catalog_summary.md`.
  - Project 01's training config and evaluation protocol.
- Outputs:
  - Committed: the Ray pipeline code, the dataset catalog, the episode scores for our 45 episodes and per-dataset score summaries, the manual review labels, and the curated set's episode list.
  - Private on the Hub: the full per-episode score table (about 79,000 rows), referenced by revision.
  - Private on the Hub: the merged training sets, the held-out test set, the two retrained checkpoints, and the evaluation recordings.
  - `results/`: throughput, score agreement, offline metric, the evaluation, and a summary.

## Risks and unknowns

- **LeRobot 0.6.0 cannot train on several datasets at once,** so public episodes must be merged into one dataset first. Merging needs matching features (camera names, image sizes, fps); public datasets with different camera names may need renaming or may be unusable. Step 2 checks this before any scoring. The merge also needs the same `robot_type` string and the same camera `dtype` (video, as ours), as checked in LeRobot 0.6.0's `aggregate.py`; public datasets use several robot type names (`so100`, `so101_follower`, and others), so step 5 may need to rewrite it in their `info.json`.
- **Joint values may not mean the same pose on someone else's arm.** Each SO-101 is calibrated separately, so the same angle on two arms can be a slightly different pose. Their actions may not transfer cleanly to ours.
- **Other people's scenes differ:** rooms, lighting, objects, camera placement. Public data may help, do nothing, or hurt; all three are valid results.
- **Format versions:** LeRobot 0.6.0 reads its own v3.0 dataset format; older datasets may need converting or be skipped.
- **Licenses:** each public dataset's license must allow this use. Datasets without a clear license are excluded.
- **Video decoding inside Ray workers:** torchcodec needs `DYLD_FALLBACK_LIBRARY_PATH` on this Mac. Whether Ray's worker processes inherit it is untested (macOS strips it in some cases, as found in project 01).
- **Disk and download time:** the relevant pool's videos would be several hundred gigabytes. Step 3 therefore scores trajectories for every relevant episode first, and fetches video only for a shortlist, within about 50 GB.
- **Same training budget:** keeping 100,000 steps means fewer passes per episode on a larger dataset. That is deliberate (equal compute), but it may favor the smaller set.
- **Privacy:** public datasets show other people's rooms. Nothing from them is published in this repo beyond dataset names and scores.

## Out of scope / later

- A multi-node Ray cluster (cloud, or Kubernetes with KubeRay). Planned as a follow-on once the local pipeline works.
- Evaluation at scale in simulation, with Ray running many simulated robots as clients of project 02's policy server.
- Recording a large new dataset, beyond the held-out test set.
- Training policies other than ACT, or vision-language-action models.
- **Hardening downloads of public data** (deferred from step 2): size caps on downloaded files, a separate cache for public data (`HF_HUB_CACHE`), keeping FFmpeg and torchcodec current, optional decoding of untrusted video in a container, and a rule that downloaded files are only parsed as data (never unpickled, never run as code). To be raised again before step 3 downloads public video.
- Recovery demonstrations (episodes starting with the toy pushed off its mark), unless the coverage scores single them out as the main gap; then a separate, small, follow-up project.
