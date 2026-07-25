"""Static deployment gate; it never contacts a Docker daemon or remote server."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
APP = (ROOT / "backend/app.py").read_text(encoding="utf-8")
ENGINE = (ROOT / "backend/world_engine.py").read_text(encoding="utf-8")
GATEWAY = (ROOT / "gateway/app.py").read_text(encoding="utf-8")
CODEX_EXECUTOR = (ROOT / "agent_codex/executor.py").read_text(encoding="utf-8")
CODEX_MCP = (ROOT / "agent_codex/authority_mcp.py").read_text(encoding="utf-8")
CODEX_DOCKERFILE = (ROOT / "Dockerfile.codex_agent").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require("name: authority-world-v1" in COMPOSE, "Compose project name changed")
    require("memo-authority-five-repairs" not in COMPOSE + APP + ENGINE, "memo namespace leaked into Authority World")
    require("researcher" not in COMPOSE + APP + ENGINE, "researcher path/user leaked into Authority World")
    require("127.0.0.1:18100:8100" in COMPOSE, "world control port is not isolated")
    require("./data:/world-data" in COMPOSE and "./gateway-data:/gateway-data" in COMPOSE, "backend and gateway data domains are not separate")
    require("world_provider" in COMPOSE and COMPOSE.count("world_a") >= 6, "required network separation missing")
    for agent in range(1, 7):
        require(f"agent_a{agent}:" in COMPOSE and f"AGENT_ID: A{agent}" in COMPOSE, f"agent A{agent} missing")
    backend_section = COMPOSE.split("  backend:\n", 1)[1].split("  agent_a1:\n", 1)[0]
    require("OPENAI_API_KEY" not in backend_section, "backend must not receive provider key")
    require("WORLD_SKILL.md" in APP and "panel" in APP, "backend does not inject skill/panel")
    require("consume_api_for_model_request" in APP, "model calls are not metered by backend")
    require("tool_receipts" in APP and "call_id" in APP, "world tool calls are not idempotent")
    require("sleep_until" in ENGINE and 'private_messages"][-80:]' in ENGINE, "sleep or non-destructive panel semantics missing")
    require("Dockerfile.codex_agent" in COMPOSE and "CODEX_CAPABILITY_MODE" in COMPOSE, "Codex capability condition is not configured")
    require("/v1/codex/responses" in APP and "codex_responses_exchange" in GATEWAY, "Codex requests do not traverse the auditable proxy")
    require("mcp.server.fastmcp" in CODEX_MCP and "authority_world" in CODEX_EXECUTOR, "Codex MCP-only world surface is missing")
    require("chmod 000 /bin/dash /bin/bash" in CODEX_DOCKERFILE, "locked Codex mode does not disable shell")
    require("parallel_tool_calls=False" not in GATEWAY, "gateway disables parallel tool calls")
    for network in range(1, 7):
        require(f"world_a{network}: {{internal: true}}" in COMPOSE, f"agent network {network} is not internal")
    print("Authority World v1 deployment contract PASS")


if __name__ == "__main__":
    main()
