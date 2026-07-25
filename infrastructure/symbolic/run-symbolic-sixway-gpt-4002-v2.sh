#!/usr/bin/env bash
set -euo pipefail
ROOT=/data/authoritylab/authority-world-v2-symbolic-gpt-2026074002-sixway-v2
cd "$ROOT"
exec python3 scripts/run_agent_economics_experiment.py \
  --protocol experiments/bridge-nonconsequence-gpt-v1.json \
  --phase mechanism-validation \
  --only-seed 2026074002 \
  --results /data/authoritylab/minimal-condition-ablation-v1-clean-reruns-v1/symbolic-gpt-2026074002-sixway-v2 \
  --poll-seconds 15
