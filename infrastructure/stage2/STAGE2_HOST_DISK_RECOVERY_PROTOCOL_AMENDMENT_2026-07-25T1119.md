# Stage 2 host-disk recovery protocol amendment

Timestamp: `2026-07-25T11:19:55+08:00`

This infrastructure-only amendment was frozen before restarting any Stage 2
lane. No scientific outcome or AUC was read.

## Trigger

The environment supervisor correctly fail-closed I1-GPT after `/data` crossed
the 24 GiB hard limit. Once capacity recovered, automatic recovery remained
fail-closed for two independently reproduced reasons:

1. `host_disk_hard_limit` was not in the recovery controller's default allowed
   reasons, so the controller selected an older, already-processed provider
   trip.
2. The environment supervisor wrote a trip and completed runner, watchdog,
   Compose, and task-container shutdown, but did not append an `enforced`
   receipt to the per-world watchdog log.

The affected trip is
`trip-20260725T110244609709.json` for run
`v2-2026074003-bddc842128c5`. The environment supervisor's immutable JSONL log
records `global_fail_closed` at `2026-07-25T11:04:50.902745+08:00` and links the
exact trip path, run ID, and reason.

## Frozen correction

- Add `host_disk_hard_limit` to both supervisor and recovery-controller allowed
  reasons.
- Make future supervisor global fail-close operations append a durable
  trip-hash-linked `enforced` receipt only after all shutdown actions succeed.
- Do not invoke automatic recovery for non-recoverable trips.
- Only a successful recovery command may consume the global recovery cooldown;
  a provider-specific preflight failure must not block another provider's lane.
- Permit the recovery controller to use a strictly matched
  `global_fail_closed` record from the configured environment-supervisor JSONL
  when an older trip lacks a watchdog `enforced` row. The complete supervisor
  log and matched record are copied into the recovery evidence directory and
  embedded in `RECOVERY_AMENDMENT.json`.

## Code provenance

- Environment supervisor before:
  `ac959089649d3eae0acc540f83a225a25a2a5ca812ffe4d90909c17d0a646ca5`
- Environment supervisor intermediate deployment:
  `a42604a270edce7860daee491b557c0f94488dbbea6b27728bed4c40af4ad064`
- Environment supervisor final:
  `6511055ab05fbfba7e611ac46d1f5ee9c383014a878c88944c8b79106885fd9a`
- Recovery controller before:
  `6d6a92168035db204bd036c62960a9d2e0dbb48add006dfa8644f1b2a1114db1`
- Recovery controller after:
  `c43386c68ae89c25e6bd20a0b65b32e5558c02e00402d28e3c7a4642d8a16495`
- Stage 2 supervisor config before:
  `44eeeefdbf2ef48b9bc65f81680b46afe5288a4668afb1fe06646f19e422011d`
- Stage 2 supervisor config after:
  `2fbcfff688db923fb7b2b7ae6eb152fea198df6c6f0ea275baf9092e2c663e52`

Validation before final deployment: `11 passed` for supervisor safety tests and
`85 passed` for the public repository suite, including three enforcement-source
tests. Recovery still requires provider preflight, time compensation, same run
identity, committed amendment, and live runner/watchdog verification.
