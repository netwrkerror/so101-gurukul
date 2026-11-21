# Project 03 summary: curating public robot data with Ray

**Result: with 135 curated public episodes added to our 45, the policy succeeded in 15 of 20 trials on the arm, against 8 of 20 with 135 random public episodes added (S3).** Both were evaluated the same evening, in balanced blocks, under project 01's protocol. S2 led in both blocks. Fisher's exact test gives p = 0.054: suggestive, not conclusive at 20 trials. Almost all of the difference is at one spot (A: 7 of 7 against 1 of 7). Offline, on 9 held-out demonstrations, the three policies (ours only, curated, random) predicted the operator's actions equally well. Project 01's policy, on our data alone, scored 10 of 20 in an earlier session.

This page summarizes the project. The detailed records are linked in each section, and the choices and their reasons are in [`DECISIONS.md`](../../../DECISIONS.md).

## The question

Projects 01 and 02 failed mostly in situations the 45 demonstrations never showed, such as a toy pushed off its mark. Thousands of public demonstrations exist for the same arm. Two questions:

1. How do you find the useful ones without watching them all?
2. Does adding them, curated, help, beyond what the same amount of random public data would do?

## The pipeline

```
Hub listing ─▶ catalog (metadata only) ─▶ joint scores (every relevant episode) ─▶ shortlist of whole datasets
   6,790           1,006 compatible            77,486 episodes, Ray Data              75 datasets, 50 GB of video
                                                                                              │
     arm evaluation ◀─ training (HF Jobs) ◀─ S2 and S3 built in the container ◀─ manual review ◀┴─ video scores in an isolated container
      40 trials           2 runs                 ours + 135 each                     60 episodes        11,957 clips
```

| Step | What happened | Record |
|---|---|---|
| 2. Catalog | Ray tasks read the metadata of 6,790 public datasets tagged `so100`/`so101` and checked them against our setup (format, real robot, episodes, robot type, joints, fps, cameras, license): 1,006 compatible (93,336 episodes), 807 task-relevant (78,847) | `catalog_summary.md` |
| 3a. Joint scores | Only joint data downloaded (1.6 GB). Ray Data scored 77,486 episodes in 19 s on 4 CPUs: length, idle time, hesitations, jerk, gripper openings, commanded-to-measured gap, and an exact-copy fingerprint. **37% of public episodes are exact copies** of episodes in other datasets | `scoring_stage1.md` |
| 3b. Video scores | A shortlist of 75 whole datasets (4,987 episodes, 50 GB), decoded only inside a container with no network and read-only mounts. 11,957 episode-camera clips scored in 9 minutes on 6 CPUs (sampled frames; image features from ResNet-18). **No public scene looks like ours** (median distance to our nearest episode 0.28, against 0.026 among our own) | `shortlist.md`, `scoring_stage2.md` |
| 4. Manual review | 60 episodes labeled blind, on clips re-encoded in the container. 32 of 36 random public episodes looked good, so the random part could not test the scores. Only two scores' worst cases were real problems (idle fraction, length); the other seven flagged unusual tasks, not bad demonstrations | `review_findings.md`, `review_agreement.md` |
| 5a. Training sets | From 3,972 usable public episodes: **S3** = 135 drawn at random; **S2** = 135 after the review-supported filters, task match (two gripper openings), and similarity to our scene. Both merged with our 45, built and re-encoded in the container, validated against our features | `curation_plan.md`, `sets_build.md`, `s2_episodes.csv`, `s3_episodes.csv` |
| 5b. Test set | 9 new demonstrations, 3 per spot, recorded like the training data | `test_set.md` |
| 6. Training | ACT on S2 and S3 with project 01's run 4 settings (100,000 steps, batch 8, seed 1000) on HF Jobs: 4 h 28 m and about $4.47 each | `training_runs.md` |
| 7. Evaluation | Offline on the test set; 20 arm trials each for S2 and S3, every trial recorded | `offline_eval.md`, `evaluation.md` |

## Numbers

**Arm evaluation** ([`evaluation.md`](evaluation.md)), 20 trials per policy, toy from three spots into a fixed bowl, 45-second limit:

| Policy | Training data | Successes | 95% interval | Spot A | Spot B | Spot C | Session |
|---|---|---|---|---|---|---|---|
| S1 | our 45 episodes | 10/20 | 30% to 70% | 4/7 | 3/7 | 3/6 | 2026-10-18 (project 01) |
| S2 | + 135 curated public | **15/20** | 53% to 89% | 7/7 | 7/7 | 1/6 | 2026-11-20 |
| S3 | + 135 random public | **8/20** | 22% to 61% | 1/7 | 7/7 | 0/6 | 2026-11-20 |

- S2 against S3 (like for like): p = 0.054. S2 led in both blocks of 10 (8 against 3, then 7 against 5).
- Failures were mostly missed grasps: all 12 of S3's, and 3 of S2's 5 (the others: one dropped during carry, one did not release in time).
- Every outcome matches its recording's length: successes ended early, failures ran to the time limit.

**Offline** ([`offline_eval.md`](offline_eval.md)), mean absolute error over the first second of each predicted chunk, body joints, on the 9 held-out episodes: S1 7.06°, S2 7.20°, S3 6.95°. Every paired difference's 95% interval includes zero.

## What it showed

1. **Most curation is filtering out what can never be used.** Wrong format or cameras, simulation, copies, policy rollouts, inconsistent files, mismatched joint units. The scores came last and mattered least.
2. **Most quality scores did not survive a human check.** Their worst cases were unusual tasks, not bad demonstrations. Only idle fraction and episode length flagged real problems.
3. **The public pool is mostly clean but nothing like our scene.** About 6% of random public episodes looked bad; none of 75 shortlisted datasets looked like our room.
4. **Curated public data helped on the arm, not on paper.** S2 beat S3 at spot A, yet predicted test demonstrations no more closely. Imitation error on held-out demonstrations did not predict success on the arm.
5. **Random public data did not help.** S3 scored about what our data alone did (8 against 10, in different sessions).

## Lessons from building it

- **Check counts against pagination.** A first listing said about 3,800 datasets; it was capped at 2,000 per tag. The real number was 6,790.
- **Score the cheap signal first.** Joint data for every episode (1.6 GB), video only for a shortlist (50 GB), instead of about 867 GB for all.
- **Treat downloaded media as untrusted input.** The isolated container also exposed a real environment bug: on Linux, the lock paired torch's CUDA 12.8 build with a torchcodec built for CUDA 13. Fixed in the lock; a smoke test that decodes a video now catches it.
- **LeRobot 0.6.0's dataset tools need care when merging other people's data:** no rename operation, stale columns after `remove_feature`, file numbering after `delete_episodes`, and merges that require identical features and codecs. All worked around in `src/build_sets.py`.
- **Write down wrong guesses.** The first copy fingerprint (30 frames) was suspected of false matches; hashing whole episodes showed the copies were real.

## Limitations

- **20 trials per policy:** S2 against S3 is p = 0.054, and the gain is concentrated at one spot.
- **S1 was not re-run** with S2 and S3 (the maintainer's decision, judging conditions unchanged); comparisons with S1 are across sessions.
- **Not blind:** the operator knew which policy was running. The recordings and the outcome-duration check are the mitigation.
- **Joint units were matched by range only,** and each arm's calibration differs; this may limit what public data can teach.
- **The sets differ beyond curation:** S2's episodes are shorter (median 10.5 s against 16.5 s), and S2 has fewer frames (82,165 against 94,102) at the same training steps.
- **The follower disconnected six times,** always at the start of an episode (`There is no status packet` from all six motors). No trial was cut short; the cause is unconfirmed.
- **Small checks:** one reviewer, 60 labeled episodes; a 9-episode test set.

## What would come next

- More trials of S2 and S3 (and S1 in the same session), to settle whether the gain is real.
- Find out why spot A changed and spot C did not: watch the recordings, and check which public episodes start where.
- Fix the follower disconnects before the next arm session (power supply, direct USB, retrying the read).
- A multi-node Ray cluster, and a vision-language-action model on the same task and evaluation (part 4).

## Reproducing

Commands are in each script's header and in the Dockerfile. In order:

1. `src/catalog.py`;
2. `src/score_trajectories.py`;
3. `src/shortlist.py`, then `score_video.py score` in the container, then `score_video.py summarize`;
4. `src/review_sample.py`, `score_video.py clips` in the container, the labeling page, then `src/review_agreement.py`;
5. `src/curate_plan.py`, then `src/build_sets.py` in the container;
6. `lerobot-train` with `configs/train_act_s2.json` and `configs/train_act_s3.json`;
7. `src/fetch_models.py`, `src/offline_eval.py`, then `lerobot-rollout` with `configs/eval_act_s2.json` and `configs/eval_act_s3.json`.

Datasets, models, and score tables are private on the Hugging Face Hub, referenced by revision in each record. The public datasets used are listed by name and revision in `shortlist.csv` and the episode lists. No frames from them are published.
