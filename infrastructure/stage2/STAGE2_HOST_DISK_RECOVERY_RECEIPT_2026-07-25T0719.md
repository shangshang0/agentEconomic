# Stage 2 host-disk recovery receipt

Recorded at 2026-07-25T07:19:16+08:00. This receipt closes the operational recovery procedure declared in `STAGE2_HOST_DISK_RECOVERY_AMENDMENT_2026-07-25T0710.md`. No scientific endpoint, AUC, treatment contrast, or other Stage 2 outcome was read.

## Dry-run disposition

The initial four dry-runs failed safely because the default per-lane watchdog log had no self-enforcement row: this incident had been enforced by the environment supervisor. No world file changed. Four supervisor-derived enforcement receipts were then installed without modifying the original watchdog logs. With `--watchdog-log watchdog/supervisor-derived-enforcement.jsonl`, all four dry-runs returned `action=would_recover`, matched the frozen run ID/day/event sequence, and passed all three provider probes. Three lanes had no unmatched charge. I3--DeepSeek had one unambiguous unmatched charge, A5 sequence 1084 for 0.08 energy; A5 was alive and its energy field was numeric, so no agent revival was required.

## Committed recovery

All four frozen controllers ran concurrently with classification `registered_minconf_stage2_host_disk_fail_close_20260725`. Each returned `action=recovered`, preserved its original run ID and day 6, reconciled frozen outstanding calls to zero, shifted the world clock by audited downtime, started the original runner/watchdog pair, and wrote a committed amendment.

| Cell | Run ID | Recovery directory | Compensated downtime (s) | Frozen outstanding before/after | Committed amendment SHA256 |
|---|---|---|---:|---|---|
| I1--GPT | `v2-2026074003-bddc842128c5` | `automatic-20260725T071617` | 1386.434911 | 0 / 0 | `42b63458500200654f59de1078f91156bcfc440b7fd9313da54f1391bfc4bdd8` |
| I3--GPT | `v2-2026074203-b60bc3738bba` | `automatic-20260725T071617` | 1224.429434 | 0 / 0 | `59fba733afbae6cd49ecd596f50e9d7fa63bf0ae0dfa61435b4f8d240efde61a` |
| I1--DeepSeek | `v2-2026074103-012aa056d4b9` | `automatic-20260725T071616` | 1211.875992 | 0 / 0 | `dd1e4d7d00d91e3c7357e29944db0fd0b4252933d6a4bf20bb30c5268f7d5b96` |
| I3--DeepSeek | `v2-2026074303-bc9733d127ab` | `automatic-20260725T071616` | 1199.291476 | 1 / 0 | `c42733e386763e1023c8fb8584a6a0f4a7121bc1b6e3498b8883d03628bf4b88` |

I3--DeepSeek received exactly one `technical_model_request_energy_refunded` record and one matching `automatic-recovery-abort` gateway terminal for the frozen A5 request. The other three lanes received no recovery refund. Provider-error-attributable refund count was zero in every lane.

## Post-recovery acceptance

By the 2026-07-25T07:17:29+08:00 supervisor heartbeat:

- admission remained open with no pause reason; `/data` had 36.277 GiB available and disk consumption had fallen to 0.004 GiB/min;
- provider errors over 15 minutes were zero;
- all four backends and runners were healthy, all four watchdogs were alive, recovery was not pending, and no lane had a current trip;
- all 32 Compose containers were running, none paused or restarting, none had a nonzero restart count, and none was unhealthy;
- all four event streams had advanced after recovery: I1--GPT to at least 993, I3--GPT to at least 780, I1--DeepSeek to at least 1176, and I3--DeepSeek to at least 1097;
- no new `authority-llm-watchdog-trip-v1` receipt existed. The `authority-automatic-recovery-hold-v1` files are controller provenance, not watchdog trips.

The four committed amendments are mirrored under `infrastructure/stage2/recovery-receipts/committed/`. These worlds remain in progress and are not yet scientifically eligible. The original terminal-evidence gate remains unchanged.
