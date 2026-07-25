#!/usr/bin/env bash
set -euo pipefail
ROOT=/data/authoritylab/authority-world-v2-symbolic-clean-ds-v2
cd "$ROOT"
exec python3 scripts/run_agent_economics_experiment.py \
  --protocol experiments/bridge-nonconsequence-ds-v1.json \
  --phase mechanism-validation \
  --results /data/authoritylab/minimal-condition-ablation-v1/nonconsequential-clean-v2/ds \
  --poll-seconds 15
