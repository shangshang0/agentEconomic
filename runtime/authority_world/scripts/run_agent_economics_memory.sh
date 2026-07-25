#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/authoritylab/authority-world-v2-real72-ranked-v5
FROZEN_DISCOVERY=/data/authoritylab/agent-economics-protocols/confirmatory-v1.json
POWER_AUDIT=/data/authoritylab/agent-economics-analysis/pilot-v1/power-audit.json
MEMORY_PROTOCOL=/data/authoritylab/agent-economics-protocols/memory-short-v1.json
MEMORY_RESULTS=/data/authoritylab/agent-economics-memory-short-v1
MEMORY_ANALYSIS=/data/authoritylab/agent-economics-analysis/memory-short-v1

cd "$ROOT"
while systemctl is-active --quiet authority-world-agent-economics-mechanisms.service; do
  sleep 60
done
if systemctl is-failed --quiet authority-world-agent-economics-mechanisms.service; then
  echo "mechanism service failed; refusing to start memory replication" >&2
  exit 1
fi

python3 scripts/freeze_agent_economics_memory.py \
  --discovery-protocol "$FROZEN_DISCOVERY" \
  --power-audit "$POWER_AUDIT" \
  --output "$MEMORY_PROTOCOL"

export RUNNER_CONTEXT_EVENTS=8
export RUNNER_CONTEXT_CHARS=3000
python3 scripts/run_agent_economics_experiment.py \
  --protocol "$MEMORY_PROTOCOL" \
  --phase mechanism-validation \
  --results "$MEMORY_RESULTS" \
  --poll-seconds 15

python3 scripts/analyze_agent_economics.py \
  --results "$MEMORY_RESULTS" \
  --output "$MEMORY_ANALYSIS" \
  --latex "$MEMORY_ANALYSIS/generated_results.memory.tex"
