# S2 and S3: build and validation (step 5a)

Episode selection: `curation_plan.md`, `s2_episodes.csv`, `s3_episodes.csv`. Built inside the isolated container by `src/build_sets.py` from `outputs/p03_sets/plan.json`; written by hand from the build reports (`outputs/p03_sets/s2_build.json`, `s3_build.json`, local).

| | S2 (curated) | S3 (random control) |
|---|---|---|
| Hub dataset (private) | `causalerror/p03-s2-curated`, revision TO FILL | `causalerror/p03-s3-random`, revision TO FILL |
| Public source datasets | 16 | 46 |
| Episodes | 180: our 45 plus 135 public | 180: our 45 plus 135 public |
| Frames | 82,165 | 94,102 |
| Our share of frames (25,876) | 31% | 27% |
| Features identical to ours (LeRobot's merge check) | yes | yes |
| `robot_type`, fps | `so_follower`, 30 | `so_follower`, 30 |
| First frame of every episode decodes | 180 of 180 | 180 of 180 |
| Every video file, probed with PyAV | 9 files: AV1, 640x480, yuv420p | 11 files: AV1, 640x480, yuv420p |
| Build time (4 workers) | 7.5 min to prepare (8 sources reused from an earlier run), 33 s to merge | 32 min to prepare, 58 s to merge |
| Size on disk | 1.4 GB | 1.6 GB |

## How each public source was prepared

1. Copied at the revision planned in step 3a (data from step 3a, metadata and videos from step 3b; the revisions were checked to match).
2. Converted from LeRobot v2.1 to v3.0 with LeRobot's own converter, offline, where needed.
3. Only the planned episodes kept (`delete_episodes`); every camera but the mapped wrist and front cameras removed (`remove_feature`).
4. Two LeRobot 0.6.0 leftovers tidied:
   - **Stale camera columns:** removed from the episode metadata. This was needed in 3 of S2's sources and 13 of S3's.
   - **File numbering:** files renumbered from `file-000`.
5. Cameras renamed to `wrist` and `front`. Joint names, the other non-video feature definitions, and `robot_type` set to ours (metadata only; the data is unchanged).
6. Every video re-encoded to our settings (AV1, yuv420p, crf 30, GOP 2, preset 12), then the build checked that each file's codec, pixel format, size, and fps equal ours before aligning the metadata.

## Notes

- **Excluded while building:** three datasets that LeRobot's own converter cannot convert (`configs/curation.yaml`, `exclude_build`). Their episodes were replaced: the next-ranked ones in S2, and the next in the seeded order in S3.
- **Frames differ between the sets.** S3 has 15% more frames than S2, because S2's length filter removes the longest episodes. Training uses the same number of steps for both (run 4's settings), so S2's frames are each seen somewhat more often. This is a known difference, not corrected.
- **Not checked by the build:** whether public joint values mean the same pose on our arm. Each arm is calibrated separately, so they may not. Units were matched only by range (step 5a decision).
- These datasets contain other people's recordings. They stay private, and no frames from them are published.
