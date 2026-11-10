# Manual review: findings (step 4)

Written by hand after the review; the numbers are in `review_agreement.md` and `review_labels.csv`.

## What the labels say

- **Most public episodes look fine.** Of the 36 random public episodes from the 75 shortlisted datasets, 32 were labeled good, 2 bad, and 2 unsure. That is 2 bad out of 34 decided, about 6% (a 95% interval of roughly 2% to 19%). The filters before scoring had already removed most unusable data: wrong format or cameras, simulation, copies, policy rollouts, and inconsistent files.
- **So the random part cannot test the scores.** With 2 bad episodes, no agreement number can be bounded; the report says "too few to bound" for every score. This is neither evidence for nor against the scores.
- **Two scores' worst cases were real problems; seven were not.**
  - `idle_fraction`: both of its 2 worst episodes were labeled bad (recording problems: a 1-second fragment and an episode that was mostly standing still).
  - `length_deviation`: 1 bad (the video did not play), 1 unsure (the video seemed to cut off).
  - The worst cases of `hesitations`, `jerk`, `gripper_deviation`, `action_state_gap`, `sharpness_min`, `brightness_deviation`, and `frozen_max` were all labeled good or unsure. Their extremes were mostly **unusual tasks, not bad demonstrations**: picking 9 sponges one by one (many gripper openings), opening a drawer, fitting a puzzle piece. A score built on "one pick and one place" calls those abnormal.
- **The task varies more than the catalog's keyword filter suggested.** 6 of the 60 episodes were tagged "different task" (4 of the 36 random ones), and the notes describe more: stacking cubes, opening a lid, a handover, sorting by color, several objects per episode.
- **Near-duplicates the fingerprint missed.** 5 notes point to an episode that looked like one already seen, including a 1-second fragment that was the end of another clip. Exact hashing catches only identical copies.
- **Self-consistency:** 6 of 8 repeated clips got the same label as the first time.
- **Ours:** 6 of 6 labeled good. Our own scene is recognizable, so blinding did not hold for these 6.

## Caveats

- One reviewer; clips at 10 fps and 240 pixels high, so fine blur or small jerks may not be visible.
- One extreme clip (`rlodhi/screw_picking_deprecated`, episode 19, a `jerk` extreme) was cut to 6.2 s of 13.9 s, because one of its camera segments is shorter than its metadata says. It was labeled unsure.
- The clip maker ran out of memory once with 6 workers; Ray retried the task and all 60 clips completed. Use fewer clip workers next time.

## What this means for step 5

- **As filters, use only what the review supports:** drop extreme `idle_fraction` and `length_deviation`, and the inconsistent datasets found earlier.
- **Do not rank episodes by jerk, sharpness, brightness, frozen frames, hesitations, or the commanded-to-measured gap.** Their worst cases did not look worse to a person, and the random part had too few bad episodes to test them.
- **Task match matters more than quality here.** The number of gripper openings is better read as a task-type signal (a single pick and place opens about twice) than as a quality score.
- **Scene similarity** (`dist_to_ours` from step 3b) was not part of this review; it measures likeness, not quality.
