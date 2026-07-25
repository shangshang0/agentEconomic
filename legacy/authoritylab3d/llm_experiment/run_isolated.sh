#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
python3 scripts/prepare_env.py
mkdir -p data
if [ "$(id -u)" -eq 0 ]; then
  chown 10001:10003 data
  chmod 770 data
else
  # Docker Desktop does not preserve Linux container UID/GID ownership on the
  # host bind mount. Production Linux deployments take the stricter branch.
  chmod 777 data
fi

docker compose --env-file .env config --quiet

# Remove containers from the superseded Last City pilot. Data files remain in
# ./data and are never treated as v3 observations.
for name in authoritylab-observer-proxy authoritylab-gateway authoritylab-backend authoritylab-agent-aer authoritylab-agent-grid authoritylab-agent-med authoritylab-agent-hab authoritylab-agent-log authoritylab-agent-h authoritylab-agent-g authoritylab-agent-t authoritylab-agent-c; do
  docker rm -f "$name" >/dev/null 2>&1 || true
done
docker network rm authoritylab_control authoritylab_internal >/dev/null 2>&1 || true

docker compose --env-file .env up -d --build --remove-orphans

attempt=0
until curl -fsS http://127.0.0.1:8126/health >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 90 ]; then
    docker compose --env-file .env ps
    exit 1
  fi
  sleep 1
done

python3 scripts/check_isolation.py
docker compose --env-file .env ps
curl -fsS http://127.0.0.1:8126/health
