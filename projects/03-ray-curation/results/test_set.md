# Held-out test set (step 5b)

New demonstrations, recorded like the 45 training episodes, used only for step 7's offline metric: each policy's action prediction error on episodes none of them trained on. Settings: `configs/record_test_lelab.yaml`.

| Field | Value |
|---|---|
| Dataset | `causalerror/so101-toy-to-bowl-test`, private (confirmed on the Hub), revision `0683b67ac70673f7ea9f07bcaa17dae6d5b6a410` |
| Date | 2026-11-13 |
| Episodes | 9 planned: 3 at each spot, in the order A, B, C, A, B, C, A, B, C |
| Lighting | Daylight, blinds open, as the training recording. Mean brightness of the first `front` frame: 115.8 to 132.6 over the 9 episodes, against 111.5 to 129.5 over 6 training episodes |
| Front camera check | Close: same position, angle, and framing as the first `front` frame of training episode 0 (`outputs/p03_test/reference_front_ep0.png`, local); the bowl slightly further into the frame. Camera indexes unchanged (wrist 0, front 1) |
| Re-recorded attempts | 3 or 4 (the exact number was not recorded), for displacements such as a pushed toy or bowl; the 9 kept episodes are complete demonstrations |
| Frames | 4,302 (episodes of 13.1 to 19.0 s; training median 18.3 s). Cameras, size, codec, task string, and robot type identical to training |

## Notes

- Not used for training by S1, S2, or S3. The final checkpoints were chosen before this set was recorded.
- One operator, the same as for the training data, so the test set shares the operator's style. It measures how well each policy predicts our own demonstrations, not other people's.
- Nine episodes is small: the offline metric is a supporting signal; the 20 arm trials are the main result.
