#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/authoritylab/authority-world-v2-real72-ranked-v5
PILOT_ANALYSIS=/data/authoritylab/agent-economics-analysis/pilot-v1/aggregate.json
POWER_AUDIT=/data/authoritylab/agent-economics-analysis/pilot-v1/power-audit.json
FROZEN_DISCOVERY=/data/authoritylab/agent-economics-protocols/confirmatory-v1.json
MECHANISM_PROTOCOL=/data/authoritylab/agent-economics-protocols/mechanisms-v1.json
MECHANISM_RESULTS=/data/authoritylab/agent-economics-mechanisms-v1
MECHANISM_ANALYSIS=/data/authoritylab/agent-economics-analysis/mechanisms-v1

cd "$ROOT"

while systemctl is-active --quiet authority-world-agent-economics-postpilot.service; do
  sleep 60
done

if systemctl is-failed --quiet authority-world-agent-economics-postpilot.service; then
  echo "confirmation service failed; refusing to start mechanism runs" >&2
  exit 1
fi

python3 scripts/freeze_agent_economics_mechanisms.py \
  --discovery-protocol "$FROZEN_DISCOVERY" \
  --power-audit "$POWER_AUDIT" \
  --pilot-analysis "$PILOT_ANALYSIS" \
  --output "$MECHANISM_PROTOCOL"

python3 scripts/run_agent_economics_experiment.py \
  --protocol "$MECHANISM_PROTOCOL" \
  --phase mechanism-validation \
  --results "$MECHANISM_RESULTS" \
  --poll-seconds 15

python3 scripts/analyze_agent_economics.py \
  --results "$MECHANISM_RESULTS" \
  --output "$MECHANISM_ANALYSIS" \
  --latex "$MECHANISM_ANALYSIS/generated_results.mechanisms.tex"
