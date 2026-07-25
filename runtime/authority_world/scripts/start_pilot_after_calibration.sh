#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/authoritylab/authority-world-v2-real72-ranked-v5
DEEPSEEK_RESULTS=/data/authoritylab/strict72-deepseekv4pro-20260720-001-results
GPT_RESULTS=/data/authoritylab/strict72-gpt55-20260721-001-results
PILOT_RESULTS=/data/authoritylab/agent-economics-pilot-v1

cd "$ROOT"

completed_tasks() {
  local result_dir=$1
  python3 - "$result_dir" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
tasks = set()
for path in root.glob("worker*.jsonl"):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row.get("task_id"), str):
            tasks.add(row["task_id"])
print(len(tasks))
PY
}

# Both calibration families must have attempted every frozen task and their
# workers must have exited. Time-limit censoring is retained as an outcome.
while true; do
  deepseek_count=$(completed_tasks "$DEEPSEEK_RESULTS")
  gpt_count=$(completed_tasks "$GPT_RESULTS")
  deepseek_active=0
  gpt_active=0
  systemctl is-active --quiet authority-world-strict72-deepseekv4pro-worker0.service && deepseek_active=1
  systemctl is-active --quiet authority-world-strict72-deepseekv4pro-worker1.service && deepseek_active=1
  systemctl is-active --quiet authority-world-strict72-gpt55-worker0.service && gpt_active=1
  systemctl is-active --quiet authority-world-strict72-gpt55-worker1.service && gpt_active=1
  if [[ "$deepseek_count" -eq 72 && "$gpt_count" -eq 72 && "$deepseek_active" -eq 0 && "$gpt_active" -eq 0 ]]; then
    break
  fi
  sleep 60
done

python3 scripts/preflight_real72_environment.py \
  --base-dir "$ROOT" \
  --image authority-world-task:real72-v4 \
  --output /data/authoritylab/agent-economics-preflight/real72-environment.json

python3 scripts/run_agent_economics_experiment.py \
  --phase discovery-pilot \
  --results "$PILOT_RESULTS" \
  --poll-seconds 15
