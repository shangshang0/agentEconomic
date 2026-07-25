#!/usr/bin/env bash
set -euo pipefail

LOG=/data/authoritylab/minimal-confirmatory-stage2-v1/logs
mkdir -p "$LOG"

sessions=(
  al-minconf2-i1-gpt-4003
  al-minconf2-i3-gpt-4203
  al-minconf2-i1-ds-4103
  al-minconf2-i3-ds-4303
  al-minconf2-wd-i1-gpt-4003
  al-minconf2-wd-i3-gpt-4203
  al-minconf2-wd-i1-ds-4103
  al-minconf2-wd-i3-ds-4303
  al-minconf2-supervisor
)
for session in "${sessions[@]}"; do
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "refusing duplicate session: $session" >&2
    exit 2
  fi
done

tmux new-session -d -s al-minconf2-wd-i1-gpt-4003 \
  "bash -lc '/data/authoritylab/supervisor/run-watchdog-minconf-stage2-i1-gpt-4003.sh >> $LOG/i1-gpt-watchdog.log 2>&1'"
tmux new-session -d -s al-minconf2-wd-i3-gpt-4203 \
  "bash -lc '/data/authoritylab/supervisor/run-watchdog-minconf-stage2-i3-gpt-4203.sh >> $LOG/i3-gpt-watchdog.log 2>&1'"
tmux new-session -d -s al-minconf2-wd-i1-ds-4103 \
  "bash -lc '/data/authoritylab/supervisor/run-watchdog-minconf-stage2-i1-ds-4103.sh >> $LOG/i1-ds-watchdog.log 2>&1'"
tmux new-session -d -s al-minconf2-wd-i3-ds-4303 \
  "bash -lc '/data/authoritylab/supervisor/run-watchdog-minconf-stage2-i3-ds-4303.sh >> $LOG/i3-ds-watchdog.log 2>&1'"

tmux new-session -d -s al-minconf2-i1-gpt-4003 \
  "bash -lc '/data/authoritylab/supervisor/run-minconf-stage2-i1-gpt-4003.sh >> $LOG/i1-gpt-runner.log 2>&1'"
tmux new-session -d -s al-minconf2-i3-gpt-4203 \
  "bash -lc '/data/authoritylab/supervisor/run-minconf-stage2-i3-gpt-4203.sh >> $LOG/i3-gpt-runner.log 2>&1'"
tmux new-session -d -s al-minconf2-i1-ds-4103 \
  "bash -lc '/data/authoritylab/supervisor/run-minconf-stage2-i1-ds-4103.sh >> $LOG/i1-ds-runner.log 2>&1'"
tmux new-session -d -s al-minconf2-i3-ds-4303 \
  "bash -lc '/data/authoritylab/supervisor/run-minconf-stage2-i3-ds-4303.sh >> $LOG/i3-ds-runner.log 2>&1'"

tmux new-session -d -s al-minconf2-supervisor \
  "bash -lc '/data/authoritylab/supervisor/run-environment-supervisor-minconf-stage2-v1.sh >> $LOG/environment-supervisor.log 2>&1'"

date -Is
tmux list-sessions | grep al-minconf2 | sort
