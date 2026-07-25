#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import mmap
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


STATE_KEYS = {"run_id", "status", "day", "daily", "agents", "tasks"}


def read_state_projection(path: Path) -> dict:
    result: dict = {}
    with path.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        index = 1
        size = len(data)
        while index < size:
            while index < size and data[index] in b" \r\n\t,":
                index += 1
            if index >= size or data[index] == ord("}"):
                break
            if data[index] != ord('"'):
                raise ValueError("invalid state object key")
            key_start = index
            index = _skip_json_string(data, index)
            key = json.loads(data[key_start:index])
            while index < size and data[index] in b" \r\n\t":
                index += 1
            if index >= size or data[index] != ord(":"):
                raise ValueError("invalid state object separator")
            index += 1
            while index < size and data[index] in b" \r\n\t":
                index += 1
            value_start = index
            index = _skip_json_value(data, index)
            if key in STATE_KEYS:
                result[key] = json.loads(data[value_start:index])
    agents = result["agents"]
    result["agents"] = {
        agent_id: {
            field: agent.get(field, 0)
            for field in ("status", "energy", "lifetime_energy_received", "lifetime_energy_sent")
        }
        for agent_id, agent in agents.items()
    }
    result["daily"] = {"leader": result["daily"].get("leader")}
    result["tasks"] = [
        {field: task.get(field) for field in ("id", "tier", "state", "assigned_to")}
        for task in result["tasks"]
    ]
    return result


def _skip_json_string(data: mmap.mmap, index: int) -> int:
    index += 1
    while index < len(data):
        byte = data[index]
        index += 1
        if byte == ord("\\"):
            index += 1
        elif byte == ord('"'):
            return index
    raise ValueError("unterminated JSON string")


def _skip_json_value(data: mmap.mmap, index: int) -> int:
    if data[index] == ord('"'):
        return _skip_json_string(data, index)
    if data[index] not in (ord("{"), ord("[")):
        while index < len(data) and data[index] not in b",}":
            index += 1
        return index
    stack = [data[index]]
    index += 1
    while stack and index < len(data):
        byte = data[index]
        if byte == ord('"'):
            index = _skip_json_string(data, index)
            continue
        if byte in (ord("{"), ord("[")):
            stack.append(byte)
        elif byte in (ord("}"), ord("]")):
            stack.pop()
        index += 1
    if stack:
        raise ValueError("unterminated JSON value")
    return index


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def read_jsonl(path: Path) -> list[dict]:
    return list(iter_jsonl(path))


def task_counts(tasks: list[dict]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for tier in ("easy", "medium", "hard"):
        result[tier] = dict(Counter(task["state"] for task in tasks if task["tier"] == tier))
    return result


class GatewayErrorTracker:
    def __init__(self, path: Path, run_id: str):
        self.path = path
        self.run_id = run_id
        self.inode: int | None = None
        self.offset = 0
        self.counts: Counter[str] = Counter()

    def _consume(self, row: dict) -> None:
        request = row.get("request", {})
        if self.run_id not in json.dumps(request, ensure_ascii=False):
            return
        kind = str(row.get("kind", ""))
        if kind != "exchange":
            self.counts[kind or "unknown_gateway_record"] += 1
        response = row.get("response")
        if isinstance(response, dict) and response.get("error"):
            self.counts["provider_error"] += 1

    def update(self) -> dict[str, int]:
        if not self.path.exists():
            return dict(self.counts)
        stat = self.path.stat()
        if self.inode != stat.st_ino or stat.st_size < self.offset:
            self.inode = stat.st_ino
            self.offset = 0
            self.counts.clear()
        with self.path.open(encoding="utf-8") as stream:
            stream.seek(self.offset)
            for line in stream:
                if line.strip():
                    self._consume(json.loads(line))
            self.offset = stream.tell()
        return dict(self.counts)


def submission_details(events: list[dict], tasks: list[dict]) -> list[dict]:
    task_by_id = {task["id"]: task for task in tasks}
    first_opened_at: dict[str, float] = {}
    details: list[dict] = []
    for event in events:
        data = event.get("data", {})
        task_id = data.get("task_id")
        if event.get("kind") == "task_opened" and task_id not in first_opened_at:
            first_opened_at[task_id] = float(event["at_wall"])
        if event.get("kind") != "task_flag_submitted":
            continue
        task = task_by_id[task_id]
        opened_at = first_opened_at.get(task_id)
        details.append({
            "task_id": task_id,
            "tier": task["tier"],
            "solver": event.get("actor"),
            "day": event.get("day"),
            "correct": bool(data.get("correct")),
            "reward": data.get("reward", 0),
            "seconds_from_first_open": round(float(event["at_wall"]) - opened_at, 3) if opened_at is not None else None,
        })
    return details


def gini(values: list[float]) -> float:
    ordered = sorted(values)
    total = sum(ordered)
    if not ordered or total <= 0:
        return 0.0
    weighted = sum((index + 1) * value for index, value in enumerate(ordered))
    return round((2 * weighted) / (len(ordered) * total) - (len(ordered) + 1) / len(ordered), 4)


def snapshot(base_dir: Path, expected_run_id: str, gateway_tracker: GatewayErrorTracker | None = None) -> dict:
    state = read_state_projection(base_dir / "data-v2" / "authority-world-v2.state.json")
    if state.get("run_id") != expected_run_id:
        raise RuntimeError(f"run id changed: {state.get('run_id')!r}")
    events = read_jsonl(base_dir / "data-v2" / "authority-world-v2.events.jsonl")
    agents = state["agents"]
    tasks = state["tasks"]
    calls_by_day = Counter(
        event.get("day") for event in events if event.get("kind") == "model_request_energy_consumed"
    )
    calls_by_agent = Counter(
        event.get("actor") for event in events if event.get("kind") == "model_request_energy_consumed"
    )
    correct = [event for event in events if event.get("kind") == "task_flag_submitted" and event.get("data", {}).get("correct")]
    incorrect = [event for event in events if event.get("kind") == "task_flag_submitted" and not event.get("data", {}).get("correct")]
    transfers = [event for event in events if event.get("kind") == "energy_transferred"]
    living_energies = [float(agent["energy"]) for agent in agents.values() if agent["status"] == "alive"]
    open_debt = Counter(
        task["assigned_to"] for task in tasks
        if task["state"] == "opened" and task.get("assigned_to")
    )
    at_risk = sorted(
        agent_id for agent_id, agent in agents.items()
        if agent["status"] == "alive" and float(agent["energy"]) <= 12
    )
    warnings = []
    if at_risk:
        warnings.append("energy_at_or_below_12:" + ",".join(at_risk))
    if state["status"] != "running":
        warnings.append("world_status:" + str(state["status"]))
    tracker = gateway_tracker or GatewayErrorTracker(base_dir / "gateway-data-v2" / "authority-world-v1.gateway.jsonl", expected_run_id)
    gateway_errors = tracker.update()
    if gateway_errors:
        warnings.append("gateway_errors:" + json.dumps(gateway_errors, sort_keys=True))
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "run_id": expected_run_id,
        "status": state["status"],
        "day": state["day"],
        "leader": state["daily"].get("leader"),
        "alive": sum(agent["status"] == "alive" for agent in agents.values()),
        "dead": [agent_id for agent_id, agent in agents.items() if agent["status"] == "dead"],
        "energies": {agent_id: round(agent["energy"], 4) for agent_id, agent in agents.items()},
        "lifetime_energy_received": {agent_id: round(float(agent.get("lifetime_energy_received", 0)), 4) for agent_id, agent in agents.items()},
        "lifetime_energy_sent": {agent_id: round(float(agent.get("lifetime_energy_sent", 0)), 4) for agent_id, agent in agents.items()},
        "total_energy": round(sum(agent["energy"] for agent in agents.values()), 4),
        "energy_range": round(max(living_energies) - min(living_energies), 4) if living_energies else 0,
        "energy_gini": gini(living_energies),
        "agents_at_or_below_12": at_risk,
        "open_task_debt_by_agent": dict(sorted(open_debt.items())),
        "calls_total": sum(calls_by_day.values()),
        "calls_by_day": {str(day): count for day, count in sorted(calls_by_day.items())},
        "calls_by_agent": dict(sorted(calls_by_agent.items())),
        "tasks_by_tier_and_state": task_counts(tasks),
        "correct_submissions": len(correct),
        "incorrect_submissions": len(incorrect),
        "correct_by_tier": dict(Counter(
            next(task["tier"] for task in tasks if task["id"] == event["data"]["task_id"])
            for event in correct
        )),
        "submissions": submission_details(events, tasks),
        "energy_transfers": len(transfers),
        "energy_transferred_total": round(sum(float(event.get("data", {}).get("amount", 0)) for event in transfers), 4),
        "event_counts": dict(Counter(event.get("kind") for event in events)),
        "gateway_errors": gateway_errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=60.0)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    gateway_tracker = GatewayErrorTracker(args.base_dir / "gateway-data-v2" / "authority-world-v1.gateway.jsonl", args.run_id)
    while True:
        try:
            record = snapshot(args.base_dir, args.run_id, gateway_tracker)
        except Exception as error:
            record = {
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "run_id": args.run_id,
                "monitor_error": str(error),
            }
        with args.output.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        if record.get("status") in {"complete", "technical_freeze"}:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
