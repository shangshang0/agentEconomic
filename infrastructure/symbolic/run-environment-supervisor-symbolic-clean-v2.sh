#!/usr/bin/env bash
set -euo pipefail
exec python3 /data/authoritylab/supervisor/experiment_environment_supervisor.symbolic-clean-v2.py \
  --config /data/authoritylab/supervisor/environment-supervisor.symbolic-clean-v2.json \
  --interval 30
