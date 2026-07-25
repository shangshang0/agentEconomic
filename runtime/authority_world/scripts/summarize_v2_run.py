#!/usr/bin/env python3
"""Generate an auditable, machine-readable interim summary for a v2 run."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_consistent(state_path: Path, events_path: Path, attempts: int = 40) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read one fail-closed online cut despite state-before-events persistence."""
    problem = "no read attempted"
    for _ in range(attempts):
        state = load_json(state_path)
        events = load_jsonl(events_path)
        expected = int(state.get("event_seq", -1))
        seqs = [event.get("seq") for event in events]
        if expected >= 0 and len(events) == expected and seqs == list(range(1, expected + 1)):
            run_id = state.get("run_id")
            tagged = [event.get("run_id") for event in events if event.get("run_id") is not None]
            if tagged and (len(tagged) != len(events) or any(value != run_id for value in tagged)):
                raise ValueError("event run_id does not match state run_id")
            if not tagged and events:
                first = events[0]
                start = first.get("data", {}).get("starts_at_wall")
                if first.get("kind") != "world_scheduled" or start != state.get("world_start_wall"):
                    raise ValueError("legacy event stream cannot be tied to this state")
            return state, events
        problem = f"state event_seq={expected}, event rows={len(events)}, contiguous={seqs == list(range(1, len(events) + 1))}"
        time.sleep(0.05)
    raise RuntimeError("could not obtain a consistent online cut: " + problem)


def summarize(state: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = Counter(str(event.get("kind") or "malformed_kind") for event in events)
    leaders: dict[str, dict[str, Any]] = {}
    assignments: dict[str, list[dict[str, Any]]] = defaultdict(list)
    submissions: list[dict[str, Any]] = []
    deaths: list[dict[str, Any]] = []
    candidacies_by_day: Counter[str] = Counter()
    explicit_votes_by_day: Counter[str] = Counter()
    task_by_id = {task["id"]: task for task in state.get("tasks", []) if isinstance(task, dict) and "id" in task}

    for event in events:
        kind = event.get("kind")
        day = str(event.get("day"))
        data = event.get("data", {})
        if kind == "leader_elected_for_next_day":
            leader_day = str(int(event.get("day", 0)) + 1)
            if leader_day in leaders:
                raise ValueError("duplicate leader election event for day " + leader_day)
            leaders[leader_day] = {
                "leader": data.get("leader"),
                "reason": data.get("reason"),
                "candidates": data.get("candidates", []),
                "explicit_votes": data.get("explicit_votes"),
                "imputed_votes": data.get("imputed_votes"),
                "vote_totals": data.get("vote_totals"),
            }
        elif kind == "task_assigned":
            task = task_by_id.get(data.get("task_id"), {})
            assignments[day].append({
                "leader": event.get("actor"),
                "task_id": data.get("task_id"),
                "recipient": data.get("recipient_id"),
                "tier": task.get("tier"),
                "reward": task.get("reward"),
                "self_allocation": event.get("actor") == data.get("recipient_id"),
            })
        elif kind == "task_flag_submitted":
            correct_value = data.get("correct")
            if not isinstance(correct_value, bool):
                raise ValueError("task submission has non-boolean correct field")
            submissions.append({
                "day": event.get("day"),
                "agent": event.get("actor"),
                "task_id": data.get("task_id"),
                "correct": correct_value,
                "reward": data.get("reward", 0),
            })
        elif kind == "agent_died":
            deaths.append({"day": event.get("day"), "agent": data.get("agent_id"), "reason": data.get("reason")})
        elif kind == "candidacy_declared":
            candidacies_by_day[day] += 1
        elif kind == "election_vote_cast":
            explicit_votes_by_day[day] += 1

    energies = {agent: round(float(entry.get("energy", 0)), 4) for agent, entry in state.get("agents", {}).items()}
    living_energies = [energies[agent] for agent, entry in state.get("agents", {}).items() if entry.get("status") == "alive"]
    correct = [item for item in submissions if item["correct"]]
    failed = [item for item in submissions if not item["correct"]]
    task_states = Counter(str(task.get("state", "unknown")) for task in state.get("tasks", []))
    self_allocations = sum(item["self_allocation"] for records in assignments.values() for item in records)
    return {
        "schema": "authority-world-v2-interim-summary-2",
        "run_id": state.get("run_id"),
        "config_hash": state.get("config_hash"),
        "status": state.get("status"),
        "current_day": state.get("day"),
        "event_seq": state.get("event_seq"),
        "agents": {
            "alive": sorted(agent for agent, entry in state.get("agents", {}).items() if entry.get("status") == "alive"),
            "dead": sorted(agent for agent, entry in state.get("agents", {}).items() if entry.get("status") == "dead"),
            "energy": energies,
            "living_energy_range": round(max(living_energies) - min(living_energies), 4) if living_energies else 0,
            "all_agent_energy_range": round(max(energies.values()) - min(energies.values()), 4) if energies else 0,
        },
        "leaders_by_day": leaders,
        "assignments_by_day": dict(assignments),
        "task_outcomes": {
            "submitted": len(submissions),
            "correct": len(correct),
            "incorrect": len(failed),
            "total_reward": sum(float(item["reward"]) for item in correct),
            "records": submissions,
            "pool_state_counts": dict(sorted(task_states.items())),
            "offered_events": kinds.get("daily_tasks_offered", 0),
            "assigned_events": kinds.get("task_assigned", 0),
            "opened_events": kinds.get("task_opened", 0),
            "closed_without_submission_events": kinds.get("task_closed", 0),
            "self_allocations": self_allocations,
        },
        "communication": {
            "agent_forum_posts": kinds.get("forum_posted", 0),
            "private_messages": kinds.get("private_message_sent", 0),
        },
        "politics": {
            "candidacies": kinds.get("candidacy_declared", 0),
            "explicit_votes_cast": kinds.get("election_vote_cast", 0),
            "candidacies_by_election_day": dict(sorted(candidacies_by_day.items(), key=lambda item: int(item[0]))),
            "explicit_votes_by_election_day": dict(sorted(explicit_votes_by_day.items(), key=lambda item: int(item[0]))),
            "note": "Missing eligible votes may be deterministically imputed by the engine; older election events do not expose those counts.",
        },
        "deaths": deaths,
        "event_counts": dict(sorted(kinds.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    state, events = load_consistent(args.state, args.events)
    result = summarize(state, events)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
