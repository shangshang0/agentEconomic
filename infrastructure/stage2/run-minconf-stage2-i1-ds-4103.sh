#!/usr/bin/env bash
set -euo pipefail
ROOT=/data/authoritylab/authority-world-v2-minconf-stage2-i1-ds-4103-v1
cd "$ROOT"
exec python3 scripts/run_agent_economics_experiment.py \
  --protocol experiments/minconf-stage2-i1-ds.json \
  --phase discovery-confirmatory \
  --results /data/authoritylab/minimal-confirmatory-stage2-v1/i1-ds \
  --poll-seconds 15
