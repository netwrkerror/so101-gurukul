# Serving check: the policy server against the offline path (step 5, part A)

Built by `src/serving_check.py` (git commit `6ea13a5`), on mps, without the arm. 18 frames spread over the test set (`causalerror/so101-toy-to-bowl-test` @ `0683b67a`), each predicted three ways with the same noise (SmolVLA): straight into the policy, as in the offline evaluation and in training; through project 02's server class with its image-size fix and the runner's camera mapping; and through LeRobot's stock server with the cameras named camera1 and camera2. The server paths get each frame as the robot sends it (joint positions, 480x640 uint8 images).

Difference from the offline chunk, over every action of every chunk: body joints in degrees, gripper on its 0 to 100 scale.

| Policy | Path | Frames | Actions per chunk | Body, mean | Body, largest | Gripper, mean | Gripper, largest |
|---|---|---|---|---|---|---|---|
| SmolVLA | served (ours) | 18 | 50 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| SmolVLA | served (stock, cameras renamed) | 18 | 50 | 3.3584 | 54.0283 | 4.2151 | 39.3656 |
| S1 (ACT) | served (ours) | 18 | 100 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

## Notes

- SmolVLA: config image size (3, 256, 256).
- S1 (ACT): config image size (3, 480, 640).
- The stock server cannot serve SmolVLA with our camera names at all: it resizes each image to the size the policy's config gives for that name before renaming, and the config has no `front` or `wrist` (a KeyError). Naming the cameras camera1 and camera2 avoids that, but then the resize squashes them to 256x256.
- ACT's stock path is not run separately: its config declares the cameras' 480x640 under their own names, so the stock resize and ours are the same step.
