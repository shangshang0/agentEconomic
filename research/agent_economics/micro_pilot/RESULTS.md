# Micro-pilot results: resource signal × execution gate

Run date: 2026-10-24. Model: `deepseek-v4-flash` via the existing Miao provider configuration. This is a one-step stylized pilot; it did not start a full world.

## Results

Twenty matched vignette blocks produced 40 valid model proposals. At displayed energy 2, the model proposed `work` in 15/20 cases (75%); at displayed energy 5, it proposed `work` in 20/20 (100%). The paired difference is +25 percentage points. All five discordant pairs favored work at the higher reported balance; none favored work only at the lower balance; 15 pairs chose work in both conditions. The exact two-sided McNemar probability is 0.0625. This small pilot is directional evidence, not a confirmatory finding.

There were 35 work proposals. Replaying each identical proposal against the two hidden ledger states yielded:

| Hidden authoritative energy | Accepted work proposals | Verified output across the 35 proposals | Ending energy after work |
|---:|---:|---:|---:|
| 2 | 0/35 | 0 | 1 |
| 5 | 35/35 | 210 | 8 |

This gate contrast is a deterministic counterfactual replay from the registered rule, not a randomized live-backend effect. It demonstrates why proposal and execution must be logged separately; the model action is held fixed in both replays.

All 40 valid calls returned the required structured action. API usage was 15,200 prompt tokens and 1,400 completion tokens (16,600 total); mean latency was 0.879 seconds. No automatic retries were used.

## Offline replay of the three archived worlds

The trace audit independently rechecked the prior three-world no-vote/no-office sample:

- 2,383/2,383 final responses matched unique gateway requests; no missing, extra, duplicate-conflict or foreign requests were found.
- 83 requests contained transfer decisions, resulting in 217 successful transfer tool calls. All 217 had successful receipts and a recipient help message visible in the request context before the transfer.
- There were no vote or candidacy decisions, as expected in this condition.

This establishes request integrity and event ordering, not that a model attended to a visible message or that the message caused a transfer.

## Interpretation against Lean

1. The proposal/execution distinction in `CausalInterface` is directly useful: the same `work` proposal has different realized output under different ledger feasibility. The gate result itself follows the stipulated simulator rule and should not be described as a discovered agent law.
2. The higher displayed balance was associated with a higher work-proposal rate, consistent with a monotone threshold-response restriction. Lean does not imply this restriction for arbitrary agents; this pilot is only an initial test of that additional behavioral assumption.
3. The experiment does not test persistence, role specialization, multi-period survival dependence, team success correlation, or real task productivity. It does not identify training-data origins or prove anything about human imitation.

## Instrumentation correction and call accounting

The first request shape forced a named tool while DeepSeek V4 Flash thinking was enabled and returned HTTP 400. A second attempt confirmed the API error. A later 40-response attempt used automatic tool choice but left thinking enabled; all responses spent the 120-token output cap on reasoning and produced no action, so those rows are excluded. The final run disables thinking and requires the function call, as the provider API requires for forced tool calls. The failed attempts are preserved under `failed_attempts/`. The thinking-only attempt reported 25,240 tokens of usage; the rejected HTTP 400 calls produced no valid observations.

## Artifacts

- [`PROTOCOL.md`](PROTOCOL.md): frozen design and registered outcomes.
- [`run_signal_gate_pilot.py`](run_signal_gate_pilot.py): runner; reads provider credentials from an external env file and never emits them.
- [`pilot_v2.jsonl`](pilot_v2.jsonl): 40 valid synthetic-vignette responses and paired ledger replays.
- [`trace_replay_audit.json`](trace_replay_audit.json): offline summary from the three archived worlds.
- [`trace_audit_world_metrics.csv`](../../../../代码/authority_world/ablation_runs/deepseek_v4_flash_no_vote_no_office/analysis/trace_audit_world_metrics.csv): per-world trace-integrity metrics.
