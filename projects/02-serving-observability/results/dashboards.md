# Prometheus and Grafana: checks (step 4)

Stack: `observability/docker-compose.yml` (Prometheus v3.5.0, Grafana 12.1.0), scraping the runner (9101) and the policy server (9102) every 2 seconds. Dashboard: "Gurukul: policy serving" (`observability/grafana/dashboards/gurukul.json`). All sessions in shadow mode, so the arm held still.

## First check, 2026-10-24

One native session and one containerized session, one trial each, queried back from Prometheus afterwards.

What worked:

- Both targets came up. Prometheus in Docker reached the runner and server on the Mac's `127.0.0.1` through `host.docker.internal`.
- The control loop peaked at 30.02 Hz during trials.
- `ChunkRoundTripHigh` fired for the container from 12 seconds into its trial. Round trip there: p50 0.38 to 0.63 s, p90 0.42 to 0.73 s.
- Every panel rendered with data. "Tracking error p90" was empty, as expected in shadow mode, where no command reaches the arm.

Problems found, and fixed:

| Problem | Cause | Fix |
|---|---|---|
| `ChunkRoundTripHigh` also fired in the native session, 14 to 32 s into the trial | The session's first chunk was slow (p50 briefly 0.45 s) while the 1-minute window held only 1 to 3 chunks | The rule needs at least 5 chunks in the window; the runner sends a warm-up request before trial 1 |
| `ControlRateLow` went pending at the start of both trials (lowest reading 1.0 Hz) | The 10-second rate window still covered idle time before the trial | The rule applies only once the trial has been active for 12 seconds |
| "Loop period" showed p50 about 34.7 ms against a true mean of 33.4 ms | Percentiles are interpolated within a bucket, and the edges were 33.3 and 36 ms | Finer buckets around 33 ms, plus an exact mean line |
| "Observation size" repeated "1.8 MB" on every label | Values differ only in the third decimal place | Two decimals |
| "Scrape targets up" only showed the current state | Single-number panel | State timeline |

Also seen: 2 deadline misses in the container session, with the client's work per step reaching about 30 to 40 ms at p99. The likely cause is the observation flood: while waiting for each slow chunk, the client serialises and sends a 1.8 MB observation every step (see `latency_native_vs_container.md`). With the native server's short waits, the same flood is small.

## Re-check after the fixes, 2026-10-24

One native session, two 45-second trials (session `20261024T185307Z`; snapshot `outputs/p02_client_metrics_20261024T185307Z.prom`, local).

| Check | Result |
|---|---|
| Warm-up chunk (before trial 1, excluded from trial metrics) | 0.44 s |
| Chunk round trip, all 28 chunks | All between 60 and 90 ms (4 at 60 to 70, 22 at 70 to 80, 2 at 80 to 90); mean 74 ms |
| First chunk of trial 2 | Not slow: the slow chunk is a once-per-session cold start |
| Chunk round trip p90, 1-minute windows | 79 to 89 ms |
| Alerts | None pending, none firing |
| Loop period | p50 33.4 ms, p99 33.5 to 33.6 ms; exact mean 33.36 ms |
| Empty-queue steps | 56 over 28 chunks: 2.0 steps (about 67 ms) per chunk |
| Deadline misses | 0 |

The cold start had inflated the earlier native measurements. Step 3's native mean round trip (103 ms) included it; without it, the native round trip averages 74 ms.
