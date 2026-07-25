#!/usr/bin/env bash
set -euo pipefail
exec python3 /data/authoritylab/watchdogs/llm_api_watchdog.symbolic-clean-v2.py world \
  --root /data/authoritylab/authority-world-v2-symbolic-ds-2026074102-sixway-v2 \
  --session authority-symbolic-sixway-ds-4102-v2 \
  --process-pattern run_agent_economics_experiment.py --require-root-in-cmdline \
  --interval 15 --heartbeat-seconds 60 --startup-grace-seconds 120 \
  --max-consecutive-errors 6 --max-error-rate 0.5 --min-rate-window-calls 6 \
  --rate-window-seconds 900 --max-calls-per-window 120 \
  --max-stall-seconds 1200 --max-outstanding-seconds 300 --arm
