# Evaluation on the arm: S1, S2, and S3 (step 7, part C)

The protocol and schedule below were written before any trial was run. Results are filled in after the session.

## What is evaluated

| Policy | Model (private) | Local copy | Config |
|---|---|---|---|
| S1: our 45 episodes (project 01's run 4) | `causalerror/act-so101-toy-to-bowl` @ `2ecffdd4` | `outputs/act_final/` | not re-run on the arm (see Schedule); `configs/eval_act_s1.json` kept, unused |
| S2: ours plus 135 curated public episodes | `causalerror/act-so101-p03-s2-curated` @ `9537e8b4` | `outputs/act_s2/` | `configs/eval_act_s2.json` |
| S3: ours plus 135 random public episodes | `causalerror/act-so101-p03-s3-random` @ `2ea29fd7` | `outputs/act_s3/` | `configs/eval_act_s3.json` |

- **Final checkpoints,** chosen before evaluation, each converted for LeRobot 0.6.0 by removing `"dtype": null` (`src/fetch_models.py`).
- **Run with** `lerobot-rollout`, episodic strategy, in-process, on `mps`, LeRobot 0.6.0.
- **The configs are project 01's `eval_act.json`** with only the policy path, the recording name, and 10 episodes per run changed. The speed cap (`max_relative_target`), timing, and task string are unchanged.
- **Every trial is recorded** (private): `causalerror/rollout_act_p03_<policy>_eval_<timestamp>`, one dataset per block.

## Protocol (project 01's, unchanged)

- **Task string:** `Pick up the stuffed toy and place it in the bowl`.
- **20 trials per policy,** 7 at spot A, 7 at B, 6 at C, in project 01's fixed order: trials 1 to 10 are A, B, C, A, B, C, A, B, C, A; trials 11 to 20 are B, C, A, B, C, A, B, C, A, B.
- **Start of each trial:** the follower in its starting position, and the toy placed by hand on the marked spot, as close as possible to how it was placed during recording.
- **Success:** the toy fully inside the bowl and released within 45 seconds, with no human contact with either arm.
- **Failure types:** grasp missed, dropped during carry, missed the bowl, timed out, or other (with a note). A trial stopped for safety is "other: safety stop".
- **Keys:** right arrow ends a trial early only after a success, or when a failure is certain (as in project 01). Left arrow (discard and re-run) only for a setup mistake, such as the toy on the wrong spot; the voided attempt is still listed with its reason. A policy failure is never discarded.
- **Held fixed:** both camera positions, the evening lighting with the blinds closed (as project 01 and 02's evaluations), the bowl on its outline, the three spots, the toy, and the calibration files.

## Schedule: balanced blocks of 10

Four runs of 10 trials, in this order, so S2 and S3 each have one block early and one late in the session (light, operator fatigue, and motor warmth all drift over an evening):

| Run | Policy | Block | Trials (spots) |
|---|---|---|---|
| 1 | S2 | 1 | 1 to 10 (A, B, C, A, B, C, A, B, C, A) |
| 2 | S3 | 1 | 1 to 10 |
| 3 | S3 | 2 | 11 to 20 (B, C, A, B, C, A, B, C, A, B) |
| 4 | S2 | 2 | 11 to 20 |

**S1 is not re-run on the arm** (the maintainer's decision, made before the session): the setup and conditions are judged unchanged since October (no recalibration, the same taped spots and bowl outline, the same evening lighting, a matching camera view). S1's result is project 01's 10/20 from 2026-10-18.

## Session conditions (to fill)

| Check | Value |
|---|---|
| Date | 2026-11-20, evening (the setup was first checked on 2026-11-13; the trials ran on 2026-11-20) |
| Git commit | TO FILL (the commit with the S1 change, made before trial 1) |
| Camera indexes (`lerobot-find-cameras`) | `wrist` 0, `front` 1, confirmed from stills taken on 2026-11-20 before trial 1 |
| `front` view against the reference still | First check on 2026-11-20: the camera had shifted (arm about 7 to 9% lower and further right in the frame than in training episode 0's first frame) and an object intruded at the top left. The camera was nudged back and the object removed before any trial. Second check: arm's top edge about 15% from the top (training: 14%), its center about 57% across (training: 52%; the accepted 2026-11-13 check: 55%), bowl at the right edge. A bright patch seen in that still was a display artifact, not a light source (operator) |
| Lighting | Evening, blinds closed, room light, as project 01 and 02's evaluations |
| Bowl on its outline, spots taped | Yes |
| No recalibration since recording | None (confirmed by the operator) |

## Voided and test recordings (not counted)

Every recording that ran a policy is listed here or in the trials. Reasons as reported by the operator.

| Date | Policy | Recordings (episodes) | Reason |
|---|---|---|---|
| 2026-11-13 | S2 | 7 (3, 1, 1, 1, 1, 6, 1) | Setup attempts and tests before the protocol started; the follower was disconnecting |
| 2026-11-20 | S2 | 3 (1, 1, 1 frame) | Setup attempts before the protocol started; the follower was disconnecting |
| 2026-11-20 | S3 | 1 (1 frame) | A false start before block 1 |
| 2026-11-20 | S2 | 3 (3, 2, 2; each interrupted) | Block 2: the follower disconnected at the start of trials 13, 14, and 15. Each interrupted episode is a single frame and is voided; the completed trials in these recordings count (11, 12, 13, 14). Kept locally |
| 2026-11-20 | S3 | 1 (10; interrupted) | Block 2's main run: the follower disconnected at the start of trial 20. Trials 11 to 19 count; trial 20 is re-run as a separate recording. Kept locally |
| 2026-11-20 | S3 | 1 (8; interrupted) | Block 1's main run: the follower disconnected during trial 8. Trials 1 to 7 count; trial 8's attempt is voided, and trials 8 to 10 are re-run as a separate recording. Kept locally |
| 2026-11-20 | S2 | 1 (9; interrupted) | Block 1's main run: the follower disconnected during trial 9. Trials 1 to 8 count (outcomes below); trial 9's attempt is voided as a hardware disconnect, and trials 9 and 10 are re-run as a separate recording. This recording is kept locally (its episode index was not written, so it is not uploaded); its videos show trials 1 to 8 |

The follower disconnecting repeatedly is a hardware problem, not a policy failure. The error was `ConnectionError: Failed to sync read 'Present_Position' on ids=[1, 2, 3, 4, 5, 6] after 1 tries. [TxRxResult] There is no status packet!`: none of the six motors answered a position read, and LeRobot did not retry. All six silent at once points to the shared link (USB adapter, cable, or the motors' power supply) rather than one servo. The exact cause is not confirmed. All six mid-run disconnects happened at the very start of a new episode, right after the reset period (the interrupted episode has a single frame), so no trial was cut short while the policy was moving. After each mid-run disconnect, LeRobot 0.6.0 also failed to close the recording (`ArrowInvalid: ... stats/observation.images.wrist/min expected length 8 but got length 7`: the interrupted episode had no camera statistics), so those recordings have no episode index. Their data and videos were written and are kept.

## Trials

Outcomes and notes as reported by the operator after each run. Time to success was not noted; it can be read from the recordings.

### S2 (curated)

Block 1 (run 1, 2026-11-20): trials 1 to 8 from the interrupted recording (kept locally), trials 9 and 10 from `causalerror/rollout_act_p03_s2_eval_<timestamp>` (the 2-episode re-run).

| Trial | Spot | Outcome | Failure type | Notes |
|---|---|---|---|---|
| 1 | A | Success |  |  |
| 2 | B | Success |  | Grasped and released |
| 3 | C | Failure | Other: did not release in time | Slow; hesitated to drop; tried 3 times |
| 4 | A | Success |  | Slow and jerky while returning to the rest position |
| 5 | B | Success |  | Good; extended the grip |
| 6 | C | Success |  | Picked; hesitated twice before releasing |
| 7 | A | Success |  | Tried to release early, then slowed down and released in the bowl |
| 8 | B | Success |  | Slow, careful wrist extension |
| 9 | C | Failure | Grasp missed | Jerky; could not grab; tried several times |
| 10 | A | Success |  | Grabbed on the 2nd attempt |

Block 1: 8 of 10.

Block 2 (run 4, 2026-11-20): four recordings, because the follower disconnected three times, each at the start of a new episode. Trials 11 and 12 come from the 1st recording, 13 from the 2nd, 14 from the 3rd (these three kept locally, without an episode index), and 15 to 20 from the 4th, which finished normally.

| Trial | Spot | Outcome | Failure type | Notes |
|---|---|---|---|---|
| 11 | B | Success |  | Displaced the toy on the 1st attempt; grabbed it on the 2nd |
| 12 | C | Failure | Dropped during carry | Lifted the toy, then dropped it outside the bowl on the way; hesitated, then many jerky movements |
| 13 | A | Success |  | Jerky movement while releasing |
| 14 | B | Success |  | Not that smooth |
| 15 | C | Failure | Grasp missed | Went through the full motion without grasping, several times |
| 16 | A | Success |  | Nice |
| 17 | B | Success |  | Nice |
| 18 | C | Failure | Grasp missed | Readjusted; tried several times; jerky |
| 19 | A | Success |  | Hesitated while releasing |
| 20 | B | Success |  | Nice |

Block 2: 7 of 10. **S2 total: 15 of 20.**

Observation (operator): at spot A, S2 reaches for the toy's handle (its loop) rather than grasping or squeezing it anywhere.

### S3 (random)

Block 1 (run 2, 2026-11-20): trials 1 to 7 from an interrupted recording (kept locally), trials 8 to 10 from a 3-episode re-run.

| Trial | Spot | Outcome | Failure type | Notes |
|---|---|---|---|---|
| 1 | A | Failure | Grasp missed | Tried to grasp from a height, not close to the toy; came closer later |
| 2 | B | Success |  | Slow wrist extension; gripped and dropped correctly |
| 3 | C | Failure | Grasp missed | Slow and jerky; tried to grasp; all attempts poor |
| 4 | A | Failure | Grasp missed | Tried to pick rather than grab; tried several times |
| 5 | B | Success |  | Missed the grab on the 1st attempt; picked on the 2nd |
| 6 | C | Failure | Grasp missed | Misjudged depth; jerky grabbing, tried several times; went through the full motion without grabbing |
| 7 | A | Failure | Grasp missed | Went to the left of the toy, toward spot B, then slowly came to A |
| 8 | B | Success |  | Good |
| 9 | C | Failure | Grasp missed | Missed the grab; moved toward B, then A; hesitated; went to the bowl without the toy |
| 10 | A | Failure | Grasp missed | Did not touch the toy; tried several times |

Block 1: 3 of 10.

Block 2 (run 3, 2026-11-20): trials 11 to 19 from an interrupted recording (kept locally), trial 20 from a 1-episode re-run.

| Trial | Spot | Outcome | Failure type | Notes |
|---|---|---|---|---|
| 11 | B | Success |  | Hesitated to drop the first time |
| 12 | C | Failure | Grasp missed | Repositioned and tried to grab; moved to the bowl without the toy; tried several times |
| 13 | A | Failure | Grasp missed | Went toward C, came back toward B; tried to grasp from a height |
| 14 | B | Success |  | Slow extension; adjusted its approach ("recalibrated", operator) |
| 15 | C | Failure | Grasp missed | Tried several times; a lot of force from the shoulder |
| 16 | A | Failure | Grasp missed | Missed the grasp; tried several times |
| 17 | B | Success |  | Slow, jerky movement; good |
| 18 | C | Failure | Grasp missed | Started toward A, adjusted to C; never managed to grab; misjudged depth |
| 19 | A | Success |  | Perfect |
| 20 | B | Success |  | Slow, jerky movement |

Block 2: 5 of 10. **S3 total: 8 of 20.**

Check against the recordings: in every recording, successes ended early (18.7 to 24.2 s for S3; 15.3 to 21.9 s for S2) and failures ran the full 44.4 to 44.6 s, consistent with the marks (a success is ended early with the right arrow; a failure runs to the 45-second limit).

Observation (operator): in trials 7 and 9, S3 moved toward the wrong spot (B) before turning to the toy's actual spot.

## Known limits

- **Not blind:** the operator knows which policy is running. The success rule is objective, and every trial is recorded, so judgment calls can be checked on video.
- **With 20 trials per policy,** only a large difference (for example 15/20 against 10/20) would be meaningful. The write-up reports intervals.
- **S1 against S2 and S3 is across sessions:** S1's 10/20 is from 2026-10-18, so that comparison is not like for like, however similar the conditions. S2 against S3 (same session, balanced blocks) is the like-for-like comparison.

## Results

| Policy | Training data | Block 1 | Block 2 | Total | 95% interval (Wilson) | Session |
|---|---|---|---|---|---|---|
| S1 | our 45 episodes | | | 10 of 20 | 30% to 70% | 2026-10-18 (project 01) |
| S2 | ours + 135 curated public | 8 of 10 | 7 of 10 | **15 of 20** | 53% to 89% | 2026-11-20 |
| S3 | ours + 135 random public | 3 of 10 | 5 of 10 | **8 of 20** | 22% to 61% | 2026-11-20 |

By spot (successes, counted from the trial tables): S2: A 7 of 7, B 7 of 7, C 1 of 6. S3: A 1 of 7, B 7 of 7, C 0 of 6.

Exact tests (Fisher, two-sided): S2 against S3, p = 0.054; S2 against S1, p = 0.19 (across sessions); S3 against S1, p = 0.75 (across sessions).

- **S2 against S3 is the like-for-like comparison** (same evening, balanced blocks). S2 scored higher in both blocks (8 against 3, then 7 against 5). At 20 trials each, the difference is just short of the conventional 5% level: suggestive, not conclusive.
- **S1 against S2 and S3 is across sessions** and is not like for like.
- **Spot C stays the hardest for all policies;** S2's advantage over S3 comes from spot A (7 of 7 against 1 of 7). Spot B was solved by both (7 of 7 each).
- **Every outcome matches its recording's duration** (successes ended early, failures ran to the limit).
- **Not blind:** the operator knew which policy was running. The recordings allow every call to be checked.
