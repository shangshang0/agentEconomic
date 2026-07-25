# Minimal confirmatory Stage 2 launch receipt

Activation began at 2026-07-25T05:27:49+08:00 on `monkeycode`. All four independently registered worlds entered `running` after the common 45-second start delay.

| Cell | Seed | Run ID | First verified running seq |
|---|---:|---|---:|
| I1--GPT | 2026074003 | `v2-2026074003-bddc842128c5` | 25 |
| I3--GPT | 2026074203 | `v2-2026074203-b60bc3738bba` | 14 |
| I1--DeepSeek | 2026074103 | `v2-2026074103-012aa056d4b9` | 51 |
| I3--DeepSeek | 2026074303 | `v2-2026074303-bc9733d127ab` | 56 |

At the first post-start supervisor sample (2026-07-25T05:29:23+08:00), all four backends and runners were healthy, all four watchdogs were alive with no trip, automatic recovery was not pending, provider errors over 15 minutes were zero, and the oldest outstanding provider call was 13.301 seconds. All 32 Compose containers were running, with zero paused, zero restarts, and zero unhealthy. The four projects used 32 distinct `/29` networks. Host load was 7.88 on 48 cores, available memory 327.6 GiB, and available `/data` space 47.6 GiB.

Two earlier activation attempts failed before any world-control start, active marker, run ID, or experimental event. Their retained provenance and pre-outcome corrections are recorded in `STAGE2_ACTIVATION_AMENDMENT_2026-07-25T0522.md` and `STAGE2_NETWORK_ACTIVATION_AMENDMENT_2026-07-25T0526.md`.

The raw-run wall-clock ceiling without recovery downtime is approximately 6 hours 15 minutes after world start (25 days by 900 seconds), plus final archive verification. Stage 1 terminal-day experience suggests DeepSeek worlds usually finish in roughly 2--3 hours and the slowest GPT world determines block completion in roughly 4.5--6.5 hours. The operational completion window is therefore approximately 10:00--12:00 Asia/Shanghai on 2026-07-25, with any audited provider recovery extending wall time but not world time.
