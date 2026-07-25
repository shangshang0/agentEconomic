"""Create a fresh Authority World .env without printing provider secrets.

Only OPENAI_API_KEY, OPENAI_BASE_URL and MODEL are read from a specified
root-owned source env. All world-facing tokens are newly generated.
"""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path


def parse(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key] = value
    return result


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: prepare_env.py SOURCE_ENV")
    source = parse(Path(sys.argv[1]))
    if not source.get("OPENAI_API_KEY"):
        raise SystemExit("source environment has no OPENAI_API_KEY")
    tokens = {f"A{index}": secrets.token_urlsafe(32) for index in range(1, 7)}
    values = {
        "MODEL": source.get("MODEL", "dev/gpt-5.5"),
        "OPENAI_BASE_URL": source.get("OPENAI_BASE_URL", ""),
        "OPENAI_API_KEY": source["OPENAI_API_KEY"],
        "GATEWAY_TOKEN": secrets.token_urlsafe(32),
        "WORLD_CONTROL_TOKEN": secrets.token_urlsafe(32),
        "AGENT_TOKENS_JSON": json.dumps(tokens, separators=(",", ":")),
        **{f"A{index}_TOKEN": tokens[f"A{index}"] for index in range(1, 7)},
    }
    output = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    Path(".env").write_text(output, encoding="utf-8")
    print("Prepared fresh Authority World credentials without printing secrets.")


if __name__ == "__main__":
    main()
