#!/usr/bin/env python3
"""Offline contract smoke test for the public repository."""

from __future__ import annotations

import json
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "README.zh-CN.md", "LICENSE", "DATA_LICENSE.md", "SECURITY.md",
    "pyproject.toml", "runtime/authority_world/docker-compose.v2.fallback.yml",
    "mcp/agent_economic_mcp/server.py", "skills/agent-economic-auditor/SKILL.md",
    "scripts/deploy.sh", "scripts/scan_secrets.py", "docs/AUDIT.md",
)


def main() -> None:
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit(f"missing required public files: {missing}")
    skill = (ROOT / "skills/agent-economic-auditor/SKILL.md").read_text(encoding="utf-8")
    if "[TODO" in skill or not skill.startswith("---\nname: agent-economic-auditor\n"):
        raise SystemExit("Skill metadata/content is incomplete")
    for path in ROOT.rglob("*.py"):
        if ".venv" not in path.parts and ".git" not in path.parts:
            py_compile.compile(str(path), doraise=True)
    result = subprocess.run([sys.executable, str(ROOT / "scripts/scan_secrets.py"), str(ROOT)], check=False)
    if result.returncode:
        raise SystemExit("secret scan failed")
    compose = (ROOT / "runtime/authority_world/docker-compose.v2.fallback.yml").read_text(encoding="utf-8")
    for boundary in ("provider: {}", "a1: {internal: true}", "cap_drop: [ALL]", "no-new-privileges:true"):
        if boundary not in compose:
            raise SystemExit(f"deployment isolation contract missing: {boundary}")
    releases = ROOT / "data/catalog/releases.json"
    if releases.is_file():
        json.loads(releases.read_text(encoding="utf-8"))
    print("open-source offline smoke PASS")


if __name__ == "__main__":
    main()
