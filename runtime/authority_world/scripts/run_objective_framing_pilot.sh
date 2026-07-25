#!/usr/bin/env bash
set -euo pipefail

ROOT=/data/authoritylab/authority-world-v2-real72-ranked-v5-monkeycode
PROTOCOLS=/data/authoritylab/protocols
RESULTS=/data/authoritylab/results-clean-v2
ANALYSIS=/data/authoritylab/analysis-clean-v2

cd "$ROOT"
mkdir -p "$RESULTS" "$ANALYSIS/objective-framing-pilot"

python3 scripts/run_agent_economics_experiment.py \
  --protocol "$PROTOCOLS/objective-focal-pilot.json" \
  --phase discovery-pilot \
  --results "$RESULTS/objective-focal-pilot" \
  --poll-seconds 15

python3 scripts/run_agent_economics_experiment.py \
  --protocol "$PROTOCOLS/objective-none-pilot.json" \
  --phase discovery-pilot \
  --results "$RESULTS/objective-none-pilot" \
  --poll-seconds 15

python3 scripts/analyze_agent_economics.py \
  --results "$RESULTS/objective-focal-pilot" \
  --output "$ANALYSIS/objective-framing-pilot/focal" \
  --latex "$ANALYSIS/objective-framing-pilot/focal/results.tex"

python3 scripts/analyze_agent_economics.py \
  --results "$RESULTS/objective-none-pilot" \
  --output "$ANALYSIS/objective-framing-pilot/no-objective" \
  --latex "$ANALYSIS/objective-framing-pilot/no-objective/results.tex"
