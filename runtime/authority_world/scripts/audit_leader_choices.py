"""Extract auditable leader-choice evidence from an Authority World run.

This reports only observable inputs/outputs: backend events, public messages,
and gateway function calls / visible response text.  It deliberately does not
claim to recover private model reasoning.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def calls(exchange: dict[str, Any]) -> list[dict[str, Any]]:
    return exchange.get("response", {}).get("function_calls", [])


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: audit_leader_choices.py EVENTS_JSONL GATEWAY_JSONL")
    events = rows(Path(sys.argv[1]))
    gateway = rows(Path(sys.argv[2]))
    selections = [event for event in events if event["kind"] == "resource_pack_selected"]
    by_agent = Counter(event["actor"] for event in selections)
    by_pack = Counter(event["data"]["pack_id"] for event in selections)
    print(json.dumps({"selection_count": len(selections), "by_agent": by_agent, "by_pack": by_pack}, ensure_ascii=False, default=dict))
    for event in selections:
        actor, pack, at = event["actor"], event["data"]["pack_id"], event["at_wall"]
        matches = [
            entry for entry in gateway
            if entry.get("kind") == "exchange" and entry.get("agent_id") == actor
            and any(call.get("name") == "select_resource_pack" and json.loads(call.get("arguments", "{}")).get("pack_id") == pack for call in calls(entry))
        ]
        nearest = min(matches, key=lambda entry: abs(__import__("datetime").datetime.fromisoformat(entry["at"].replace("Z", "+00:00")).timestamp() - at), default=None)
        evidence = None
        if nearest:
            evidence = {
                "gateway_at": nearest["at"],
                "visible_response_text": nearest["response"].get("text", ""),
                "function_calls": calls(nearest),
            }
        print(json.dumps({"day": event["day"], "leader": actor, "pack": pack, "event_at_wall": at, "model_exchange": evidence}, ensure_ascii=False))


if __name__ == "__main__":
    main()
