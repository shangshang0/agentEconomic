# Public data layout

The release format supports three deliberately separate classes:

```text
worlds/<asset_id>/              canonical complete world assets
reference/<asset_id>/           failed, contaminated, legacy, or partial assets
operator/<asset_id>.cas/        deduplicated operator/recovery history
```

`public-data-v1` uses only `worlds/` and contains exactly the 20 complete
assets frozen in `data/selections/public-data-v1.jsonl`. Reference and
operator assets are intentionally local-custody-only and are not uploaded to
GitHub.

A v2 world retains every available six-agent interaction stream:

```text
run_metadata.json
registry_record.json
data-v2/
  authority-world-v2.state.json
  authority-world-v2.events.jsonl
  EVIDENCE_STATUS.json
gateway-data-v2/
  authority-world-v1.gateway.jsonl
agent-state-v2/a1..a6/runner-v2/runs/<run_id>/
  audit.raw.jsonl
  context.jsonl
  memory.json                         when emitted by that runtime
technical-recovery/
supervision/
TRACE_COMPLETENESS.json
PUBLIC_MANIFEST.json
REDACTION_LEDGER.jsonl
```

Legacy v1 assets use `data/`, `gateway-data/`, and
`agent-state/a1..a6/runner/events.jsonl`. That runtime did not emit a separate
`context.jsonl`; absence is recorded as a schema property, not filled in.
Known missing tool payloads or trace discontinuities remain explicit in
`TRACE_COMPLETENESS.json` and force the asset into the reference tier.

The gateway trace and agent audits contain the redacted provider request and
response, model-visible messages, model output, tool-call ID/arguments,
receipt/result/error, and retained context or memory. The event/state streams
retain world communication and mutations. No successful analysis-eligible
world is reduced to a sampled transcript.

Task source trees with incompatible or uncertain upstream licenses are not
redistributed. They are represented by SHA-256 inventories, upstream license
and URL metadata, and a fetch recipe; the agents' task-related calls and
results remain in their traces.

`data/catalog/worlds.jsonl` has exactly one canonical record per unique run.
`data/catalog/assets.jsonl` has one record per physical evidence root, so a
failed root and a later complete root for the same run remain separately
auditable. `data/catalog/releases.json` maps those assets to immutable Release
parts.

Operator recovery trees can contain many byte-identical checkpoints. Their
CAS bundle stores each SHA-256 object once and a path/mode/object manifest;
`scripts/restore_cas_bundle.py` reconstructs the original redacted tree.
`PUBLIC_MANIFEST.json` covers public files, while `REDACTION_LEDGER.jsonl`
records source/public hashes and redaction counts without publishing original
secret values.
