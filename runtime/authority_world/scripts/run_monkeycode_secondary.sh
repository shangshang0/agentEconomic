#!/usr/bin/env bash
set -euo pipefail

ROOT=/data/authoritylab/authority-world-v2-real72-ranked-v5-monkeycode
GATES=/data/authoritylab/protocols
RESULTS=/data/authoritylab/results
ANALYSIS=/data/authoritylab/analysis

FROZEN_DISCOVERY="$GATES/confirmatory-v1.json"
POWER_AUDIT="$GATES/power-audit.json"
PILOT_AGGREGATE="$GATES/pilot-aggregate.json"
MECHANISM_PROTOCOL="$GATES/mechanisms-monkeycode-v1.json"
MEMORY_PROTOCOL="$GATES/memory-short-monkeycode-v1.json"

cd "$ROOT"
mkdir -p "$RESULTS" "$ANALYSIS"

# Scientific gate: intervention worlds do not start until the registered
# discovery pilot has been archived and the power/codebook inputs are frozen.
while [[ ! -s "$FROZEN_DISCOVERY" || ! -s "$POWER_AUDIT" || ! -s "$PILOT_AGGREGATE" ]]; do
  sleep 60
done

python3 scripts/freeze_agent_economics_mechanisms.py \
  --discovery-protocol "$FROZEN_DISCOVERY" \
  --power-audit "$POWER_AUDIT" \
  --pilot-analysis "$PILOT_AGGREGATE" \
  --output "$MECHANISM_PROTOCOL"

python3 scripts/run_agent_economics_experiment.py \
  --protocol "$MECHANISM_PROTOCOL" \
  --phase mechanism-validation \
  --results "$RESULTS/mechanisms-v1" \
  --poll-seconds 15

python3 scripts/analyze_agent_economics.py \
  --results "$RESULTS/mechanisms-v1" \
  --output "$ANALYSIS/mechanisms-v1" \
  --latex "$ANALYSIS/mechanisms-v1/generated_results.tex"

python3 scripts/freeze_agent_economics_memory.py \
  --discovery-protocol "$FROZEN_DISCOVERY" \
  --power-audit "$POWER_AUDIT" \
  --output "$MEMORY_PROTOCOL"

export RUNNER_CONTEXT_EVENTS=8
export RUNNER_CONTEXT_CHARS=3000
python3 scripts/run_agent_economics_experiment.py \
  --protocol "$MEMORY_PROTOCOL" \
  --phase mechanism-validation \
  --results "$RESULTS/memory-short-v1" \
  --poll-seconds 15

python3 scripts/analyze_agent_economics.py \
  --results "$RESULTS/memory-short-v1" \
  --output "$ANALYSIS/memory-short-v1" \
  --latex "$ANALYSIS/memory-short-v1/generated_results.tex"
