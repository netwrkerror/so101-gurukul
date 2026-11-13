# Held-out test set (step 5b)

New demonstrations, recorded like the 45 training episodes, used only for step 7's offline metric: each policy's action prediction error on episodes none of them trained on. Settings: `configs/record_test_lelab.yaml`.

| Field | Value |
|---|---|
| Dataset | `causalerror/so101-toy-to-bowl-test`, private, revision TO FILL |
| Date and time | TO FILL |
| Episodes | 9 planned: 3 at each spot, in the order A, B, C, A, B, C, A, B, C |
| Lighting | Daylight, blinds open, as the training recording |
| Front camera check | TO FILL: compared with the first `front` frame of training episode 0 (`outputs/p03_test/reference_front_ep0.png`, local) |
| Re-recorded attempts | TO FILL: how many, and why |
| Frames | TO FILL |

## Notes

- Not used for training by S1, S2, or S3. The final checkpoints were chosen before this set was recorded.
- One operator, the same as for the training data, so the test set shares the operator's style. It measures how well each policy predicts our own demonstrations, not other people's.
- Nine episodes is small: the offline metric is a supporting signal; the 20 arm trials are the main result.
