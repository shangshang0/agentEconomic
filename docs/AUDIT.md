# Independent audit protocol

An auditor should be able to reject a result without trusting the authors'
working directory, spreadsheet, or manuscript macros.

## 1. Verify custody and redaction

1. Download every part named by `data/catalog/releases.json`.
2. Verify the release-level SHA-256 values before extraction.
3. Extract with `scripts/fetch_release.py`; it rejects absolute paths, `..`,
   links/devices, and duplicate members. Per-file manifest coverage is checked
   separately after extraction.
4. Run `scripts/verify_manifest.py` on the extracted tree.
5. Inspect `REDACTION_LEDGER.jsonl`. Each source hash maps to one public hash,
   a deterministic rule-set version, and a count by redaction class. Source
   hashes permit the custodian to prove correspondence without publishing a
   secret-bearing source.

## 2. Verify each world

For every catalog row selected by the registered analysis:

- `run_id` agrees across registry, run metadata, state, events, gateway trace,
  and agent audit paths;
- `terminal_status` and archive status agree;
- the event stream is append-only, has contiguous sequence numbers, and ends at
  the state `event_seq`;
- provider charges reconcile to terminal provider responses after applying only
  committed recovery amendments;
- active markers, live runners, and Compose resources are absent for terminal
  archives;
- configuration, protocol, task manifest, runtime, launcher, and recovery files
  match the hashes recorded in the catalog.

`python3 scripts/audit_catalog.py data/catalog/worlds.jsonl --assets
data/catalog/assets.jsonl --release-root
data/releases/public-data-v1/extracted` performs the catalog and downloaded
state/event checks. The world catalog is unique by run ID; the asset catalog
may retain several historical roots for the same run. It does not upgrade a
reference-tier asset to confirmatory.

`python3 scripts/audit_trace_completeness.py WORLD` additionally requires all
six agent `audit.raw.jsonl`/`context.jsonl` pairs, every model response and
function-call ID, every tool result or error, the full provider gateway
exchange, and a matching append-only event/state sequence. Its JSON output is
stored per world in the public release. Reference-tier partial worlds use
`--allow-partial`; their warnings remain visible and they cannot become
analysis eligible.

## 3. Recompute outcomes

Run `make reproduce`. The script reads raw world/event/gateway data and writes
world-level dots before any aggregation. The experimental unit is the world.
Provider-blocked paired differences are formed only from registered cells.
Message counts and message semantics are outcomes or manipulation checks, not
independent replicates.

Required robustness outputs include all world dots, leave-one-world-out,
provider strata, bootstrap intervals, and the registered exact permutation
test. Recovered-world exclusions and the disclosed GPT symbolic micro-pause are
reported as sensitivity analyses rather than hidden cleaning decisions.

## 4. Rebuild the manuscript

`make paper` regenerates macros/tables before compiling LaTeX. `make audit`
then checks that every numeric claim in generated material has a data/analysis
provenance record. Hand-entered scientific result macros fail the audit.

## 5. Evidence that must remain separate

The `confirmatory`, `mechanism`, `discovery`, and `reference` tiers are separate
catalog fields. Contaminated, technical-failed, and infrastructure-invalid
worlds may explain engineering failure modes or motivate hypotheses but cannot
silently increase inferential sample size.
