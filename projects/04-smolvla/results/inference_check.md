# SmolVLA inference check on the Mac (step 2)

Built by `src/inference_check.py` (git commit `d979d09`): `lerobot/smolvla_base` @ `5e8d12a6`, LeRobot 0.6.0, transformers 5.5.4, torch 2.11.0, arm64. Real observations from our dataset (4 frames, one per spot and the last episode); cameras mapped front to camera1, wrist to camera2. Time per chunk includes pre- and post-processing, after a warm-up.

| Device | Images | Runs | Median per chunk | Slowest |
|---|---|---|---|---|
| mps | 2 | 20 | 256 ms | 282 ms |
| mps | 3 | 20 | 319 ms | 373 ms |
| cpu | 2 | 3 | 10182 ms | 10193 ms |
| cpu | 3 | 3 | 15513 ms | 16869 ms |

- Chunk: (1, 50, 6), i.e. 50 actions, which the arm plays out in 1.67 s at 30 Hz.
- For comparison (project 02): ACT took about 88 ms per chunk natively on `mps`; in project 02's fault tests, a 200 ms delay made the arm's pauses visible but the task still worked in 3 of 4 informal trials.
- In-process (`lerobot-rollout`), the arm waits for each chunk, so the time per chunk is a pause at every chunk boundary.

## Decision

**Serve both policies through project 02's policy server and client on this Mac (`mps`), with early chunk requests** (the maintainer's choice, 2026-11-22).

- In-process, SmolVLA's 256 ms per chunk would stop the arm for about 256 ms every 1.67 s (about 13% of the time), against about 88 ms every 3.3 s for ACT. The arm evaluation would then partly measure this Mac's latency, not the model.
- With early requests (`chunk_size_threshold`, the fraction of the current chunk still queued when the next is requested), the next chunk is computed while the current one plays out. At 0.5, the request goes about 0.8 s before the queue empties, well over 256 ms.
- **ACT S1 runs through the same serving path in the same session,** so the comparison stays like for like.
- **Two images, not three:** the third camera slot is left out (`empty_cameras=0`); it is about 20% faster (256 against 319 ms) and does not feed the model a blank image.
- **CPU is not an option** (about 10 s per chunk).
