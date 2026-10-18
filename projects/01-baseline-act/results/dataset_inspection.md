# Dataset inspection: causalerror/so101-toy-to-bowl

Project 01, step 4. Dataset revision `c6319da870f16f94db98e029ca0f4f654d585970`: 45 episodes, 25,876 frames, 30 fps, cameras `wrist` and `front`.

## Replay check

| Date | Episode | Spot | Result |
|---|---|---|---|
| 2026-10-17 | 0 | A | Replayed on `shishya` (follower) with `lerobot-replay` from the local copy. The motion matched the demonstration. Toy grasped and placed: TO FILL |

## Episode lengths

From the frame counts at 30 fps: shortest 11.6 s, median 18.3 s, mean 19.2 s, longest 30.1 s (episode 39). No episode is short enough to suggest it was cut off.

## Episode review

What to check in each episode, in `lerobot-dataset-viz`:

- The toy starts on the episode's spot, and the bowl is on its outline.
- The toy ends fully inside the bowl.
- No hand or other object enters the `front` view during the episode.
- Both camera feeds play without freezes or jumps.
- No partial or failed attempt that should have been re-recorded (a re-recorded attempt that was kept by mistake would show up here).

Status: `ok`, or `bad` with a note. Bad episodes are listed here, not deleted; whether to drop them from training is decided after the review.

| Episode | Spot | Status | Note |
|---|---|---|---|
| 0 | A | ok | |
| 1 | A | ok | |
| 2 | A | ok | |
| 3 | A | ok | |
| 4 | A | ok | |
| 5 | A | ok | |
| 6 | A | ok | |
| 7 | A | ok | |
| 8 | A | ok | |
| 9 | A | ok | |
| 10 | A | ok | |
| 11 | A | ok | |
| 12 | A | ok | |
| 13 | A | ok | |
| 14 | B | ok | |
| 15 | B | ok | |
| 16 | B | ok | |
| 17 | B | ok | |
| 18 | B | ok | |
| 19 | B | ok | |
| 20 | B | ok | |
| 21 | B | ok | |
| 22 | B | ok | |
| 23 | B | ok | |
| 24 | B | ok | |
| 25 | B | ok | |
| 26 | B | ok | |
| 27 | B | ok | |
| 28 | B | ok | |
| 29 | C | ok | |
| 30 | C | ok | |
| 31 | C | ok | |
| 32 | C | ok | |
| 33 | C | ok | |
| 34 | C | ok | |
| 35 | C | ok | |
| 36 | C | ok | |
| 37 | C | ok | |
| 38 | C | ok | |
| 39 | C | ok | |
| 40 | C | ok | |
| 41 | C | ok | |
| 42 | C | ok | |
| 43 | C | ok | |
| 44 | A | ok | |

## Summary

Reviewed on 2026-10-17: 45 of 45 episodes `ok`, none `bad`. No kept episode shows a failed or partial attempt, which confirms that the attempts re-recorded during the session are not in the dataset. All 45 episodes are used for training.
