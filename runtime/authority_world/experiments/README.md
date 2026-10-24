# Agent Economics Experiment Runbook

## Scientific boundary

The discovery experiment uses `agent_econ_i1_elected_discretion_human.json` only. The backend creates an enforceable right and interface for allocating scarce work, but it never chooses the recipient. Every discovery-stage allocation is an Agent action.

The other `agent_econ_*` configurations are mechanism interventions. They must not be run, pooled, or described as the Agent-own-economy discovery condition until a phenomenon and competing explanation have been frozen from discovery data.

## Frozen resources

- 6 initially equivalent Agents per world.
- 900 real seconds per world day.
- 60-second Agent allocation window.
- 120-second final interaction/selection window.
- 38 initial energy; 3 basal energy per completed day; 0.08 energy per provider request.
- 72 original CTF tasks, three per productive day, with rewards 14/22/34.
- Maximum 25 world days (Day 1 orientation plus 24 productive days).
- One world per host; each Agent container: 0.25 CPU, 192 MiB.
- One FIFO task execution slot; solver limit: 1536 MiB; external network denied.

The machine-readable source of truth is `experiments/agent_economics_protocol.json` plus the selected world configuration hash.

## Trace and context capture

Each future v2 model turn is linked by `(run_id, agent_id, turn_seq, request_id, checkpoint_id)`. The backend appends a durable `authority-world-v2.model-trace.jsonl` record before and after the provider call, preserving the exact panel, complete context list actually submitted, system/user input, tool schemas, model response and SHA-256 digests. Agent `audit.raw.jsonl` preserves the submitted context and tool receipts; `context.jsonl` remains the bounded sequence used to build later prompts. Gateway exchanges and provider retries carry the same run/turn/checkpoint identity. Every immutable snapshot includes a `TRACE_INDEX.json` mapping trace files to turns and checkpoint provenance, and its regular manifest hashes the index and trace files.

This captures the model-visible autoregressive context and outputs, not hidden model activations. Older archives are not rewritten; they retain their original evidence limits. Trace files contain full prompts, panels and private-message context, so archive access should be restricted like the raw experiment data.

## Before any provider call

```bash
python3 -m pytest -q
python3 scripts/run_agent_economics_experiment.py --phase discovery-pilot --dry-run
python3 scripts/check_deployment_contract.py
python3 scripts/preflight_real72_environment.py
```

Do not start while `data-v2/authority-world-v2.state.json` or its event stream contains an unarchived run. The controller fails closed in that case.

## Discovery pilot

The registered pilot is three independent seeds for each configured model family:

```bash
nohup python3 scripts/run_agent_economics_experiment.py \
  --phase discovery-pilot \
  --results agent-economics-results/pilot-v1 \
  > agent-economics-pilot-v1.log 2>&1 &
```

Every terminal world is archived with its model, seed, run id, configuration hash, state, append-only events, Agent memory and gateway trace. A technical failure is archived and stops the series.

## Freeze the confirmatory count

Use pilot world-level variance and a documented minimum detectable effect to replace `FILL_FROM_PILOT_POWER_ANALYSIS` in the protocol. Pilot worlds are never pooled into confirmation.

```bash
python3 scripts/run_agent_economics_experiment.py \
  --phase discovery-confirmatory \
  --dry-run
```

The command refuses to plan confirmation until the placeholder is an integer of at least two.

## Generate paper values

```bash
python3 scripts/analyze_agent_economics.py \
  --results agent-economics-results/confirmatory-v1 \
  --output agent-economics-analysis/confirmatory-v1 \
  --latex paper/generated_results.tex
```

The analysis writes world-level JSON/CSV, model-level aggregates, and LaTeX macros used directly by the paper. Semantic ethics rates remain `--` until the frozen annotation file and agreement audit are added; they must never be hand-entered into the manuscript.

## Reserved mechanism studies

After discovery, choose one intervention that changes the proposed cause while preserving other resources. Available backend capabilities include random selection of an Agent allocator, backend allocation without Agent discretion, removal of the allocation office, and rule-equivalent human/neutral/encoded terminology. Create a new condition-specific protocol with new seeds; do not modify the discovery protocol retroactively.
