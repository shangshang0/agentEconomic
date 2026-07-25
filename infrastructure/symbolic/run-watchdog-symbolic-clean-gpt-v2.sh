#!/usr/bin/env bash
set -euo pipefail
exec python3 /data/authoritylab/watchdogs/llm_api_watchdog.symbolic-clean-v2.py world \
  --root /data/authoritylab/authority-world-v2-symbolic-clean-gpt-v2 \
  --session authority-symbolic-clean-gpt-v2 \
  --process-pattern run_agent_economics_experiment.py \
  --require-root-in-cmdline \
  --interval 15 \
  --heartbeat-seconds 60 \
  --startup-grace-seconds 60 \
  --max-consecutive-errors 6 \
  --max-error-rate 0.5 \
  --min-rate-window-calls 6 \
  --rate-window-seconds 900 \
  --max-calls-per-window 250 \
  --max-stall-seconds 1200 \
  --max-outstanding-seconds 300 \
  --arm
