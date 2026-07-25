# Public evidence schema

`data/catalog/worlds.jsonl` contains one final row per run ID. Required fields
are `run_id`, `evidence_tier`, `analysis_eligible`, `condition`, and
`terminal_status`. Rows also identify provider/model, seed, frozen config and
runtime hashes, release part, recovery amendments, and incident history.

Extracted worlds live at
`data/releases/<release-tag>/extracted/worlds/<asset_id>/`:

- `run_metadata.json`: frozen design and runtime provenance.
- `registry_record.json`: terminal registry record; historical records remain
  in provenance when a technical failure preceded a committed rerun.
- `data-v2/authority-world-v2.state.json`: terminal state and `event_seq`.
- `data-v2/authority-world-v2.events.jsonl`: append-only world event stream.
- `gateway-data-v2/authority-world-v1.gateway.jsonl`: redacted provider
  requests/responses.
- `agent-state-v2/a*/runner-v2/runs/*/audit.raw.jsonl`: redacted model-visible
  context, responses, tool calls, and receipts.
- `technical-recovery/`: committed amendments and activation receipts.
- `supervision/`: watchdog, runner, Compose, and supervisor evidence.

Every release contains `PUBLIC_MANIFEST.json`, `REDACTION_LEDGER.jsonl`, and
`OMISSION_LEDGER.jsonl`. Redaction rows map a relative path's source SHA-256 to
its public SHA-256 and replacement counts. Source bytes and original secret
values are never public. Licensing omissions include upstream provenance and
hash/fetch instructions rather than republished third-party payloads.
