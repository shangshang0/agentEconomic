#!/usr/bin/env python3
"""Create missing experiment secrets without printing or exposing their values."""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / ".env"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not PATH.exists():
        return values
    for line in PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def main() -> int:
    values = read_env()
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL", "MODEL_PROFILES_JSON", "MOCK_MODEL", "AGENT_POLL_INTERVAL"):
        if key in os.environ:
            values[key] = os.environ[key]
    for key in ("CONTROL_TOKEN", "GATEWAY_TOKEN", "DASHBOARD_TOKEN"):
        values.setdefault(key, secrets.token_urlsafe(32))
    agent_tokens = {}
    for number in range(1, 6):
        key = f"P{number}_TOKEN"
        values.setdefault(key, secrets.token_urlsafe(32))
        agent_tokens[f"P{number}"] = values[key]
    values["AGENT_TOKENS_JSON"] = json.dumps(agent_tokens, separators=(",", ":"))
    values.setdefault("MODEL", "dev/gpt-5.5")
    values.setdefault("MOCK_MODEL", "0")
    if values["MOCK_MODEL"] != "1" and not values.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is missing and MOCK_MODEL is not 1", file=sys.stderr)
        return 2
    ordered = sorted(values.items(), key=lambda item: item[0])
    PATH.write_text("".join(f"{key}={value}\n" for key, value in ordered), encoding="utf-8")
    PATH.chmod(0o600)
    print("Environment validated; secret values were not displayed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
