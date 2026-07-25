#!/usr/bin/env bash
set -euo pipefail
ROOT=/data/authoritylab/authority-world-v2-symbolic-clean-gpt-v2
cd "$ROOT"
exec python3 scripts/run_agent_economics_experiment.py \
  --protocol experiments/bridge-nonconsequence-gpt-v1.json \
  --phase mechanism-validation \
  --results /data/authoritylab/minimal-condition-ablation-v1/nonconsequential-clean-v2/gpt \
  --poll-seconds 15
