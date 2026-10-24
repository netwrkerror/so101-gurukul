# Native against containerized policy server (step 3)

Measured on 2026-10-19, one 45-second shadow-mode trial per server: the policy predicted as usual and the runner consumed its actions at 30 Hz, but discarded them, so the arm held still. Same runner config, spot A, same machine. Percentiles are histogram bucket upper bounds.

| | Native server | Containerized server |
|---|---|---|
| How it ran | `src/server.py` with `uv`, policy on `mps` | `gurukul-policy-server:dev` in Docker Desktop (`linux/arm64`), policy on CPU (torch's CUDA build, no GPU) |
| Server inference per chunk | mean 88 ms, p50 at most 75 ms, p90 at most 100 ms, max at most 500 ms (n = 15) | mean 344 ms, p50 and p90 at most 500 ms (n = 13) |
| Chunk round trip (client) | mean 103 ms, p50 and p90 at most 100 ms | mean 379 ms, p50 and p90 at most 500 ms |
| Steps with an empty queue | 39 over 15 chunks: about 2.6 steps (about 90 ms) per chunk | 140 over 13 chunks: about 11 steps (about 360 ms) per chunk |
| Control loop period | mean 33.4 ms (30 Hz), 0 deadline misses | mean 33.4 ms (30 Hz), 0 deadline misses |
| Client work per step | mean 1.5 ms, max at most 20 ms | mean 3.4 ms, max at most 33 ms |
| Observations received by the server | 52: 17 used, 35 skipped | 152: 13 used, 139 skipped |
| Size of one observation | 1.84 MB | 1.84 MB |
| Image size | not applicable | 7.69 GB |
| Container memory (`docker stats`, one sample) | not applicable | 1.04 GiB of a 3.83 GiB limit |
| Data into the container (`docker stats`) | not applicable | 308 MB |

## What it means for the arm

Each chunk is 100 actions, about 3.3 seconds of motion at 30 Hz. At the end of each chunk the arm waits for the next one: about 0.09 s with the native server and about 0.36 s with the container. Project 01's synchronous rollout waited about 0.05 s. Motion within a chunk runs at the same speed in all three.

## Findings

- **Native inference is slower than project 01's offline measurement.** Project 01 timed the network alone at 24 ms per chunk on `mps`. Here the server's time per chunk also includes turning the raw observation (two uncompressed 640x480 images) into the policy's input, plus post-processing. That conversion is the likely extra cost, but it has not been measured on its own. The mean includes the first chunk, which is slower (warm-up).
- **The stock client sends an observation on every step while its queue is empty.** With `chunk_size_threshold` at 0 the client is "ready to send" whenever the queue is empty, so during each wait it sends one observation per step. The server uses the first, which is flagged as required, and skips the rest. The container's longer waits produced 139 skipped observations, about 250 MB of traffic in 45 seconds; `docker stats` independently showed 308 MB into the container. On one machine this costs client time (the client's work per step doubled); over a network it would also cost bandwidth.
- **Each observation is 1.84 MB:** two raw camera images, pickled without compression.
- **The container runs inside Docker Desktop's virtual machine,** with a 3.83 GiB memory limit and a limited share of the CPU cores, which likely explains why it is slower than the Mac's own CPU (about 124 ms per chunk for the network alone, in project 01's offline test).

## Decision

The counted evaluation (step 6) uses the native server. See `DECISIONS.md`, 2026-10-20.

## Conditions and caveats

- One trial per server; the first chunk includes warm-up.
- Before the container session, the front camera was found pointing away from the scene, with an object in front of the lens. When the native session ran is earlier, and the camera may already have been out of position then. Latency does not depend on the view, but the predicted actions do; they were discarded in shadow mode.
- After the container session the front camera was reset. Compared with the first front frame of recorded episode 0, the arm fills about 32% of the frame height against about 40%, and the bowl is further into the frame: the camera is slightly further back and turned slightly right. To be corrected before the counted evaluation.

## Later observations (step 4)

- **The native figures above include a cold start.** The first chunk after the server loads the policy is slow (about 0.44 s natively). With a warm-up request before the first trial, the native round trip averaged 74 ms over 28 chunks, all between 60 and 90 ms (`dashboards.md`), against the 103 ms mean measured here.
- **Deadline misses in the container session.** In a later container session watched on the dashboard, the client's work per step reached about 30 to 40 ms at p99, with 2 deadline misses. The observation flood alone does not explain them: in step 5 the same flood towards the native server cost under 5 ms per step (`latency_and_faults.md`). The cause is not known.

## Sources

Session IDs are the UTC start time of each runner session. They match the trial-log entries and metrics snapshots kept locally under `outputs/` (gitignored, not in this repo).

| Run | Session ID |
|---|---|
| Native server | `20261020T043139Z` |
| Containerized server | `20261020T044939Z` |

The server metrics for these two runs were saved by hand with `curl`, before the server saved its own snapshots on shutdown.
