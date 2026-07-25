"""Summarise an immutable Authority World run from state + append-only events.

Usage: python3 scripts/audit_run.py RUN_DIRECTORY_OR_DATA_DIRECTORY
The output is deliberately descriptive: it labels office events, material
allocation and language/communication traces without calling any pattern
"authority" by itself.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def locate(root: Path) -> tuple[Path, Path]:
    state = root / "authority-world-v1.state.json"
    events = root / "authority-world-v1.events.jsonl"
    if state.exists():
        return state, events
    matches = list(root.rglob("authority-world-v1.state.json"))
    if len(matches) != 1:
        raise SystemExit("give a directory containing exactly one run state")
    state = matches[0]
    return state, state.with_name("authority-world-v1.events.jsonl")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit_run.py RUN_DIRECTORY_OR_DATA_DIRECTORY")
    state_path, events_path = locate(Path(sys.argv[1]))
    state: dict[str, Any] = json.loads(state_path.read_text())
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    kinds = Counter(event["kind"] for event in events)
    elected = [event["data"] for event in events if event["kind"] == "leader_elected"]
    selections = [event for event in events if event["kind"] in {"resource_pack_selected", "puzzle_assigned"}]
    settlements = [event for event in events if event["kind"] == "resource_decision_settled"]
    audit_responses = [event for event in events if event["kind"] == "allocation_audit_response"]
    deaths = [event["data"] for event in events if event["kind"] == "agent_died"]
    leaders = Counter(item.get("leader") for item in elected if item.get("leader"))
    print(json.dumps({
        "run_id": state.get("run_id"), "config_hash": state.get("config_hash"), "status": state.get("status"),
        "final_day": state.get("day"), "event_count": len(events), "leadership": dict(leaders),
        "communication": {"public_posts": kinds["forum_posted"], "private_messages": kinds["private_message_sent"], "energy_transfers": kinds["energy_transferred"]},
        "office_actions": {"selections_or_assignments": len(selections), "resource_settlements": len(settlements), "voluntary_audit_responses": [item["data"] for item in audit_responses]},
        "survival": {"deaths": deaths, "agents": {key: {"status": value["status"], "energy": value["energy"], "api_quota": value["api_quota"]} for key, value in state["agents"].items()}},
        "technical": {"technical_failure_events": kinds["technical_failure"], "checkpoint_completed": kinds["checkpoint_completed"]},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
