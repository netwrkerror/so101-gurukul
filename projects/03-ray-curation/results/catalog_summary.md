# Public dataset catalog: summary (step 2)

Built from metadata only (no videos downloaded) by `src/catalog.py`. Compatible datasets: `catalog_compatible.csv`; the table of every dataset is kept locally, not in the repo.

- Public datasets tagged `so100` or `so101` (excluding our own): 6790
- Metadata fetched: 6032; failed: 758 (HfHubHTTPError 578, RemoteEntryNotFoundError 154, GatedRepoError 25, JSONDecodeError 1)
- Fetch time: 36.3 minutes
- Failed fetches were not retried, by decision. Most (`HfHubHTTPError` without a status code) look like rate limiting.

## Compatibility funnel

Each line keeps only the datasets that also pass every check above it.

| Check | Datasets remaining |
|---|---|
| Metadata fetched | 6032 |
| LeRobot format v3.0, or v2.1 (convertible) | 4636 |
| real robot, not simulation | 4299 |
| at least 10 episodes | 2608 |
| SO-100/SO-101 robot type | 1894 |
| same 6 joints, same order | 1546 |
| 30 fps | 1431 |
| at least two 640x480 cameras | 1109 |
| license allows reuse | 1006 |

**Compatible pool:** 1006 datasets, 93336 episodes.
Of those, **task-relevant** (task text mentions picking or placing into a container): 807 datasets, 78847 episodes.
Of those, cameras already named `wrist` and `front`: 70 (the rest need renaming to merge); in format v2.1 and needing conversion: 566.

## What this means for step 3

- The task-relevant pool is 807 datasets and 78847 episodes, against our 45.
- At our video size (about 11 MB per episode, two cameras), its videos would be about 867 GB. The 50 GB budget for step 3 fits about 4,545 episodes at that size, so video is only fetched for a shortlist. LeRobot v3.0 also packs many episodes into each video file, so videos cannot be fetched one episode at a time.
- Datasets with a camera named like `wrist`: 315 (46540 episodes); these map clearly onto our `wrist` camera. Most common camera sets: `laptop;phone` 215, `top;wrist` 67, `front;wrist` 61, `on_robot;phone;side_view` 19, `overhead;wrist` 18, `front;top` 18.
- Datasets that share their exact episode and frame counts with another relevant dataset: 83. Many of these are likely copies or re-uploads, so near-duplicates are collapsed before scoring.
- Joint trajectories (`data/*.parquet`) are small, so stage 1 of step 3 can score every relevant episode without video.

## Format versions (fetched datasets, normalized)

- `v2.1`: 3589
- `v2.0`: 1393
- `v3.0`: 1047
- `v2.2`: 3

## Licenses (fetched datasets, top 10)

- `apache-2.0`: 3732
- `(none)`: 2220
- `mit`: 30
- `cc-by-4.0`: 22
- `cc-by-sa-4.0`: 19
- `other`: 9

## Notes

- Ray is used here for one engine across the pipeline; fetching small metadata files is I/O-bound and would also work with plain threads.
- Joint units are not stated in the metadata; `action_min` and `action_max` per joint are recorded to compare with ours in a later step.
