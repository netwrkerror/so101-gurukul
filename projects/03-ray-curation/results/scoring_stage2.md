# Video scores for the shortlist: summary (step 3b)

Decoded inside the container (`projects/03-ray-curation/Dockerfile`: no network, videos mounted read-only), summarized on the Mac by `src/score_video.py` with `configs/scoring_stage2.yaml`.

- Code: git commit `21ddb90`; image digest `sha256:b4ef3244dc0deb39c12697af35aef67418152d3eb3d693ad4ac477f21dcdf318`
- Versions in the container: ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers; torchcodec 0.11.1+cu128; torch 2.11.0+cu128; Ray 2.59.0; aarch64, 6 CPUs
- Datasets: 76 (ours included)
- Episode-camera items: 11957; scored 11912; failed 45
- Failures: RuntimeError 45
- Decoding and scoring: 9.0 min, 1,323 items per minute
- Episode-camera items whose first frame nearly matches a scene in another dataset: 278

## Distributions

Median, with the 10th to 90th percentile in brackets, per camera role (`wrist`, or `fixed` for any other camera). `dist_to_ours` for our own episodes is to the nearest of our other 44.

| Score | Role | Ours | Public | Ours in public |
|---|---|---|---|---|
| `sharpness` | wrist | 58.7 [49.2 to 86.3] | 99.2 [6.97 to 847] | 36% |
| `sharpness` | fixed | 622 [351 to 647] | 512 [69.4 to 1.61e+03] | 55% |
| `brightness` | wrist | 139 [136 to 146] | 131 [98.8 to 162] | 69% |
| `brightness` | fixed | 125 [121 to 132] | 125 [104 to 153] | 50% |
| `motion_diff` | wrist | 6.24 [3.56 to 10.4] | 4.28 [1.13 to 11.9] | 66% |
| `motion_diff` | fixed | 2 [1.41 to 5.08] | 2.09 [0.928 to 5.36] | 48% |
| `frozen_fraction` | wrist | 0 [0 to 0.111] | 0 [0 to 0.333] | 0% |
| `frozen_fraction` | fixed | 0.111 [0 to 0.289] | 0.111 [0 to 0.444] | 48% |
| `dist_to_ours` | wrist | 0.0511 [0.0272 to 0.0863] | 0.311 [0.262 to 0.367] | 0% |
| `dist_to_ours` | fixed | 0.0256 [0.018 to 0.0359] | 0.281 [0.237 to 0.333] | 0% |

## Notes

- `sharpness`: variance of the Laplacian (higher is sharper), median over 5 frames. `brightness`: mean gray level, 0 to 255.
- `motion_diff` and `frozen_fraction`: change between 10 consecutive frames at the middle of the episode. A frozen camera has a low `motion_diff` while the joints move (compare with 3a's idle fraction). A fixed camera watching a still arm also gives identical frames, so `frozen_fraction` alone does not mean a fault.
- `scene_dup_elsewhere` uses a cosine distance below 0.02, stricter than "same room": our own episodes are often closer than that to each other. It catches near-identical scenes; `dist_to_ours` measures likeness.
- `dist_to_ours`: cosine distance of ResNet-18 ImageNet features of the first frame to the nearest of our episodes. Lower means a scene that looks more like ours. It is a proxy; it says nothing about the task.
- **Sampled, not fully decoded:** each episode-camera item decodes 5 frames spread through the episode plus 10 consecutive frames at the middle, and embeds 2 of them (first and middle), with approximate seeking. That is about 15 of roughly 400 frames at our episode lengths, which is why scoring is fast; here downloading (16 min for 50 GB) took longer than scoring. The scores describe those samples: a stretch of frozen frames or blur elsewhere in an episode can be missed. Step 4's manual review checks whether that matters; the counts are settings in `configs/scoring_stage2.yaml`.
- No public frames are committed or uploaded. Full table (with embeddings): `outputs/p03_video_scores_full.parquet`, uploaded privately to the Hub.

## Findings (written by hand after the run; a rerun of `summarize` drops this section)

- **No public scene looks like ours.** On the fixed camera, our episodes are a median cosine distance of 0.026 from their nearest other episode (90th percentile 0.036). Public episodes are a median 0.28 from our nearest episode, and the closest public dataset (`Cornito/so101_test3`) has a median of 0.20. None of the 75 datasets has a median within our own spread. The embedding can rank public datasets from least to most different, but none is a close match.
- **The 45 failures are one dataset:** all 15 episodes and 3 cameras of `ryanpennings/so100_pegcrate_e1`. Its videos are shorter than the episode lengths in its metadata (`frame pts is 8.17; must be less than 6`). It is inconsistent and is excluded in step 5.
- **One camera is portrait:** `DorayakiLin/so100_test_Lucas3` stores its wrist camera at 640x480 (ours: 480x640). The catalog passed it because its other two cameras are 480x640. A merge needs the same shape per camera, so it is excluded in step 5 (or its wrist video rotated).
- **Near-duplicate scenes:** 278 items in 14 datasets have a near-identical first frame in another dataset.
- **Isolation checks** (before the run): inside the container a network request failed (`Temporary failure in name resolution`), and writing to the video mount and to the image failed (`Read-only file system`).

## Why scoring was fast (written by hand after the run)

The scorer samples each episode instead of decoding the whole video. Frame counts are from 3a's episode table.

| | Per episode-camera item | All 11,957 items |
|---|---|---|
| Frames decoded | 15 (5 spread through the episode, 10 consecutive at the middle) | about 179,000 |
| Images through ResNet-18 | 2 (first and middle frame) | about 24,000 |
| Decoding every frame instead | median 409 | 5,480,855, about 31 times more |

Other things that helped:

- **Seeking instead of reading through:** torchcodec's `approximate` seek mode jumps close to each timestamp using the file's index, instead of decoding from the start. This matters most for v3.0 files, which hold many episodes each.
- **Six CPU workers in parallel, each loading the model once** (Ray Data's actor pool), so there is no model start-up per episode.
- **A small model on small images:** ResNet-18 on 224x224 inputs is cheap, even on CPU.

The pipeline is limited by I/O, not compute: downloading 50 GB took 16.2 minutes, and scoring took 9.0.

