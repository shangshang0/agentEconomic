# Stage 2 host-disk fail-close and recovery amendment

Recorded at 2026-07-25T07:10:18+08:00, after all four Stage 2 worlds had been fail-closed and before any manual recovery. No Stage 2 outcome endpoint, economic-differentiation AUC, treatment contrast, or other scientific result was read while preparing this amendment. Operational inspection was limited to run identity, world day, event sequence, provider health, outstanding-call count, watchdog/supervisor state, Compose state, disk/capacity state, and recovery provenance.

## Incident

Between 2026-07-25T06:53:11+08:00 and 2026-07-25T06:56:17+08:00, the common fail-closed watchdog stopped all four independently registered worlds because shared host storage crossed the frozen 24 GiB hard limit. Each trip reported the single hard reason `host_disk_hard_limit`, `disk_available_gib=13.7`, and zero provider errors in the preceding 15 minutes. The active-run markers remain in place because these are interrupted runs, not terminal completions.

| Cell | Run ID | Frozen day | Frozen event seq | Trip time | Trip SHA256 |
|---|---|---:|---:|---|---|
| I1--GPT | `v2-2026074003-bddc842128c5` | 6 | 988 | 2026-07-25T06:53:11.848494+08:00 | `54c3a3656ee9dc40a44b55305726f6734c3e5b4aeaf593f633f1f0a91e56367c` |
| I3--GPT | `v2-2026074203-b60bc3738bba` | 6 | 749 | 2026-07-25T06:55:53.425653+08:00 | `91f0416ab66385ea5a1f3977a2f3996342f44091d3520137d9370fd94d6cc08e` |
| I1--DeepSeek | `v2-2026074103-012aa056d4b9` | 6 | 1154 | 2026-07-25T06:56:05.636890+08:00 | `6f19d960c4c703644871ea93c9a3c6d02e8220503412cd927563e467e0f6d0b0` |
| I3--DeepSeek | `v2-2026074303-bc9733d127ab` | 6 | 1084 | 2026-07-25T06:56:17.690411+08:00 | `27e1e4f9652f0b72ef3244a998bded9f3b76000733e786f9d1b564316cafa5b0` |

At enforcement, all four runner and watchdog sessions exited and all four Compose projects were brought down. Only the environment supervisor remained alive. The four Stage 2 roots occupied approximately 467 MiB in aggregate; all Agent Economic material on the shared host occupied approximately 33.4 GiB. The exhaustion therefore arose at the shared-host storage layer, not from growth intrinsic to these four worlds. No Docker volume, model, world state, gateway log, result, or evidence archive was removed.

## Capacity remediation

The following outcome-blind host operations were used to restore capacity:

1. Pruned only rebuildable BuildKit cache and dangling/unused Docker images. The final BuildKit prune reclaimed 4.924 GB. Images referenced by any existing container remained; after cleanup Docker reported 51 images, all active, and zero image bytes reclaimable. Docker volumes were not pruned.
2. Moved the non-experimental pre-existing containerd migration backup from `/data/containerd-root-backup-20260721-before-data-root` to `/opt/containerd-root-backup-20260721-before-data-root`. The cross-filesystem move retained 61,067 files; the before/after metadata hash matched. The 8 KiB difference in directory-entry byte accounting is filesystem metadata, not a missing payload file. The source path is absent and the destination remains present.
3. Left unrelated shared models, project volumes, worlds, and results untouched.

After cleanup, `/data` had approximately 37--40 GiB available. The supervisor observed three consecutive capacity-healthy samples, resumed admission at 2026-07-25T07:08:53+08:00, and subsequently reported `admission_paused=false`, normal load, zero provider errors, and no disk-consumption-rate reason. Its configured automatic command intentionally did not allow the disk reason; the single automatic attempt returned `action=none, reason=no_recoverable_trip` and made no runtime or world-state change.

The first manual dry-run audit found an evidence-interface mismatch and also failed without mutation: the recovery controller requires a `kind=enforced` row in the supplied enforcement log, while this incident was enforced by the environment supervisor rather than the per-lane watchdog. The supervisor's durable log contains a successful `global_fail_close_runner_session` receipt for every run 13--417 ms after its trip, but the original watchdog logs correctly contain no self-enforcement row. Four supplemental `authority-supervisor-derived-enforcement-v1` JSONL receipts therefore bind the controller input to the exact successful supervisor row, its line number and SHA256, and the observed supervisor-log SHA256. Their `at` value is the successful runner-session kill time, the earliest durable point at which that world's event loop could no longer advance. The original watchdog logs are not edited. The receipts are retained under `infrastructure/stage2/recovery-receipts/` and copied into each corresponding root before the next dry-run.

## Frozen manual recovery procedure

The same four run IDs will be resumed; no replacement run, seed, cell, or provider may be introduced. Recovery must use `/data/authoritylab/recovery-tools/auto_recover_frozen_world.py`, SHA256 `6d6a92168035db204bd036c62960a9d2e0dbb48add006dfa8644f1b2a1114db1`, with the original runner/watchdog launchers and provider environment file from `environment-supervisor.minconf-stage2-v1.json`, plus:

```text
--allowed-reason host_disk_hard_limit
--classification registered_minconf_stage2_host_disk_fail_close_20260725
```

Before mutation, each lane must pass an individual `--dry-run` showing the frozen run ID/day/event sequence above, successful provider probes, an unambiguous outstanding-refund plan, and no required revival of a dead agent. The controller then preserves pre-recovery state, events, gateway traffic, active marker, watchdog log, trip, and all six agent-state trees; closes and refunds only frozen requests lacking a provider terminal; shifts the world clock by audited downtime; writes a committed recovery amendment; and starts the original runner/watchdog pair.

After each recovery, acceptance requires unchanged run identity, a committed amendment, live runner and watchdog, healthy Compose services, renewed event-sequence growth, no new watchdog trip, and zero provider errors. Final scientific use remains forbidden until all four lanes independently satisfy the original terminal-evidence gate: `terminal_status=complete`, no active marker, runner/watchdog exit, Compose count zero, and a verified final evidence archive. Recovered-world exclusions and sensitivities remain as frozen in the Stage 2 analysis plan.
