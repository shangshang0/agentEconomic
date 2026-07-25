#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_root="$repo_root/runtime/authority_world"
env_file="$runtime_root/.env.runtime"
compose_file="$runtime_root/docker-compose.v2.fallback.yml"

: "${OPENAI_API_KEY:?Set OPENAI_API_KEY in the calling environment}"
: "${OPENAI_BASE_URL:=https://api.openai.com/v1}"
: "${MODEL:=gpt-5.5}"
: "${WORLD_CONFIG_FILE:=world.v2.calibration.json}"
export OPENAI_API_KEY OPENAI_BASE_URL MODEL WORLD_CONFIG_FILE

command -v docker >/dev/null || { echo "docker is required" >&2; exit 2; }
docker compose version >/dev/null

DEPLOY_ENV_FILE="$env_file" python3 - <<'PY'
import json, os, secrets
from pathlib import Path
path = Path(os.environ["DEPLOY_ENV_FILE"])
tokens = {f"A{i}": secrets.token_urlsafe(32) for i in range(1, 7)}
values = {
    "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
    "OPENAI_BASE_URL": os.environ["OPENAI_BASE_URL"],
    "MODEL": os.environ["MODEL"],
    "WORLD_CONFIG_FILE": os.environ["WORLD_CONFIG_FILE"],
    "GATEWAY_TOKEN": secrets.token_urlsafe(32),
    "WORLD_CONTROL_TOKEN": secrets.token_urlsafe(32),
    "AGENT_TOKENS_JSON": json.dumps(tokens, separators=(",", ":")),
    **{f"A{i}_TOKEN": tokens[f"A{i}"] for i in range(1, 7)},
}
path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
path.chmod(0o600)
PY
unset OPENAI_API_KEY

python3 "$repo_root/scripts/open_source_smoke.py"
docker compose --project-directory "$runtime_root" --env-file "$env_file" -f "$compose_file" config --quiet
docker compose --project-directory "$runtime_root" --env-file "$env_file" -f "$compose_file" up -d --build

for _ in $(seq 1 90); do
  if docker compose --project-directory "$runtime_root" --env-file "$env_file" -f "$compose_file" exec -T backend \
      python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8100/health", timeout=2).read()' >/dev/null 2>&1; then
    echo "Agent Economic deployment is healthy. Credentials remain only in ignored mode-0600 .env.runtime."
    exit 0
  fi
  sleep 2
done

docker compose --project-directory "$runtime_root" --env-file "$env_file" -f "$compose_file" ps
echo "backend did not become healthy within 180 seconds" >&2
exit 1
