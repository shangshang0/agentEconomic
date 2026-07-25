#!/usr/bin/env bash
set -euo pipefail
ROOT=/data/authoritylab/authority-world-v2-minconf-stage2-i3-ds-4303-v1
cd "$ROOT"
exec python3 scripts/run_agent_economics_experiment.py \
  --protocol experiments/minconf-stage2-i3-ds.json \
  --phase discovery-confirmatory \
  --results /data/authoritylab/minimal-confirmatory-stage2-v1/i3-ds \
  --poll-seconds 15
