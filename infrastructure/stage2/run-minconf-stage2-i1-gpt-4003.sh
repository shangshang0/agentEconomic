#!/usr/bin/env bash
set -euo pipefail
ROOT=/data/authoritylab/authority-world-v2-minconf-stage2-i1-gpt-4003-v1
cd "$ROOT"
exec python3 scripts/run_agent_economics_experiment.py \
  --protocol experiments/minconf-stage2-i1-gpt.json \
  --phase discovery-confirmatory \
  --results /data/authoritylab/minimal-confirmatory-stage2-v1/i1-gpt \
  --poll-seconds 15
