#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/authoritylab/authority-world-v2-real72-ranked-v5
PILOT_RESULTS=/data/authoritylab/agent-economics-pilot-v1
PILOT_ANALYSIS=/data/authoritylab/agent-economics-analysis/pilot-v1
CONFIRM_RESULTS=/data/authoritylab/agent-economics-confirmatory-v1
CONFIRM_ANALYSIS=/data/authoritylab/agent-economics-analysis/confirmatory-v1
FROZEN_PROTOCOL=/data/authoritylab/agent-economics-protocols/confirmatory-v1.json
POWER_AUDIT=/data/authoritylab/agent-economics-analysis/pilot-v1/power-audit.json

cd "$ROOT"

while systemctl is-active --quiet authority-world-agent-economics-pilot.service; do
  sleep 60
done

if systemctl is-failed --quiet authority-world-agent-economics-pilot.service; then
  echo "pilot service failed; refusing to construct confirmation" >&2
  exit 1
fi

pilot_worlds=$(find "$PILOT_RESULTS" -mindepth 2 -maxdepth 2 -name run_metadata.json -type f | wc -l)
if [[ "$pilot_worlds" -ne 6 ]]; then
  echo "expected 6 archived pilot worlds, found $pilot_worlds" >&2
  exit 1
fi

python3 scripts/analyze_agent_economics.py \
  --results "$PILOT_RESULTS" \
  --output "$PILOT_ANALYSIS" \
  --latex "$PILOT_ANALYSIS/generated_results.pilot.tex"

python3 scripts/freeze_agent_economics_confirmation.py \
  --pilot-results "$PILOT_RESULTS" \
  --template-protocol experiments/agent_economics_protocol.json \
  --power-plan experiments/confirmatory_power_plan.json \
  --output-protocol "$FROZEN_PROTOCOL" \
  --audit "$POWER_AUDIT"

python3 scripts/run_agent_economics_experiment.py \
  --protocol "$FROZEN_PROTOCOL" \
  --phase discovery-confirmatory \
  --results "$CONFIRM_RESULTS" \
  --poll-seconds 15

python3 scripts/analyze_agent_economics.py \
  --results "$CONFIRM_RESULTS" \
  --output "$CONFIRM_ANALYSIS" \
  --latex paper/generated_results.tex

if command -v latexmk >/dev/null 2>&1; then
  latexmk -pdf -interaction=nonstopmode -halt-on-error -cd paper/paper-agent-economics-aaai27.tex
fi
