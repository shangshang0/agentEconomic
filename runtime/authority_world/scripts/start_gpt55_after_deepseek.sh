#!/usr/bin/env bash
set -euo pipefail

ROOT=/srv/authoritylab/authority-world-v2-real72-ranked-v5
ENV_FILE="$ROOT/.env.gpt55"

# docker compose reads this file itself, but the host-side health probe also
# needs the gateway bearer token in its environment.
set -a
source "$ENV_FILE"
set +a

while systemctl is-active --quiet authority-world-strict72-deepseekv4pro-worker0.service \
   || systemctl is-active --quiet authority-world-strict72-deepseekv4pro-worker1.service; do
  sleep 60
done

cd "$ROOT"
mkdir -p /data/authoritylab/strict72-gpt55-20260721-001-gateway
mkdir -p /data/authoritylab/strict72-gpt55-20260721-001-results
mkdir -p /data/authoritylab/strict72-gpt55-20260721-001-work
docker compose --env-file "$ENV_FILE" \
  -f docker-compose.strict72-gpt55-20260721-001.yml up -d gateway

for attempt in $(seq 1 30); do
  if curl -fsS -H "Authorization: Bearer ${GATEWAY_TOKEN}" \
      http://127.0.0.1:18112/health >/dev/null; then
    systemctl start authority-world-strict72-gpt55-worker0.service
    systemctl start authority-world-strict72-gpt55-worker1.service
    exit 0
  fi
  sleep 2
done

exit 1
