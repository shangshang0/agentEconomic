#!/usr/bin/env python3
"""Freeze world-level Agent Economics endpoints and LaTeX result macros."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def gini(values: Iterable[float]) -> float:
    data = sorted(float(value) for value in values)
    if not data or sum(data) == 0:
        return 0.0
    n = len(data)
    return sum((2 * index - n - 1) * value for index, value in enumerate(data, 1)) / (n * sum(data))


def realized_outcome(events: list[dict[str, Any]], target: str, outcome: str, day: int) -> int:
    day_events = [event for event in events if int(event.get("day", -1)) == day]
    if outcome == "receives_task":
        return int(any(event.get("kind") == "task_assigned" and event.get("data", {}).get("recipient_id") == target for event in day_events))
    if outcome == "solves_task":
        return int(any(event.get("kind") == "task_flag_submitted" and event.get("actor") == target and event.get("data", {}).get("correct") is True for event in day_events))
    if outcome == "transfers_energy":
        return int(any(event.get("kind") == "energy_transferred" and event.get("actor") == target for event in day_events))
    if outcome == "registers_for_office":
        return int(any(event.get("kind") == "candidacy_declared" and event.get("actor") == target for event in day_events))
    if outcome == "is_selected_for_office":
        return int(any(event.get("kind") == "leader_elected_for_next_day" and event.get("data", {}).get("leader") == target for event in events if int(event.get("day", -1)) == day - 1))
    raise ValueError(outcome)


def summarize(run: Path) -> dict[str, Any]:
    state_path = run / "data-v2/authority-world-v2.state.json"
    events_path = run / "data-v2/authority-world-v2.events.jsonl"
    metadata_path = run / "run_metadata.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    events = rows(events_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if len(events) != int(state["event_seq"]):
        raise RuntimeError(f"non-contiguous event export: {run}")
    agents = sorted(state["agents"])
    horizon = int(state["day"])
    death_day = {event["data"]["agent_id"]: int(event["day"]) for event in events if event.get("kind") == "agent_died"}
    alive_agent_days = sum(min(death_day.get(agent, horizon), horizon) for agent in agents)
    assignments = Counter(event["data"]["recipient_id"] for event in events if event.get("kind") == "task_assigned")
    offices = Counter(event["data"].get("leader") for event in events if event.get("kind") == "leader_elected_for_next_day" and event.get("data", {}).get("leader"))
    submissions = [event for event in events if event.get("kind") == "task_flag_submitted"]
    solved = [event for event in submissions if event.get("data", {}).get("correct") is True]
    model_calls = sum(event.get("kind") == "model_request_energy_consumed" for event in events)
    forecasts = [event for event in events if event.get("kind") == "peer_action_forecast"]
    brier = []
    for event in forecasts:
        data = event["data"]
        actual = realized_outcome(events, data["target_id"], data["outcome"], int(data["target_day"]))
        brier.append((float(data["probability"]) - actual) ** 2)
    office_total = sum(offices.values())
    return {
        "run": run.name,
        "phase": metadata.get("phase"),
        "condition": metadata.get("condition"),
        "estimand": metadata.get("estimand"),
        "model": metadata.get("model"),
        "seed": metadata.get("seed"),
        "status": state.get("status"),
        "config_hash": state.get("config_hash"),
        "alive_agent_days": alive_agent_days,
        "verified_production": sum(float(event["data"].get("reward", 0)) for event in solved),
        "solved_tasks": len(solved),
        "model_calls": model_calls,
        "calls_per_solved_task": model_calls / len(solved) if solved else None,
        "assignment_gini": gini(assignments.get(agent, 0) for agent in agents),
        "energy_gini": gini(float(state["agents"][agent]["energy"]) for agent in agents),
        "office_concentration": max(offices.values()) / office_total if office_total else None,
        "forecast_count": len(brier),
        "forecast_brier_loss": fmean(brier) if brier else None,
        "forum_posts": sum(event.get("kind") == "forum_posted" for event in events),
        "private_messages": sum(event.get("kind") == "private_message_sent" for event in events),
        "energy_transfers": sum(event.get("kind") == "energy_transferred" for event in events),
        "technical_failure": state.get("status") == "technical_failed"
    }


def mean_available(worlds: list[dict[str, Any]], key: str) -> float | None:
    values = [float(world[key]) for world in worlds if world.get(key) is not None and not world.get("technical_failure")]
    return fmean(values) if values else None


def fmt(value: float | None) -> str:
    return "--" if value is None or not math.isfinite(value) else f"{value:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--latex", type=Path, required=True)
    args = parser.parse_args()
    runs = sorted(path for path in args.results.iterdir() if path.is_dir() and (path / "run_metadata.json").exists())
    worlds = [summarize(run) for run in runs]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "world_metrics.json").write_text(json.dumps(worlds, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if worlds:
        with (args.output / "world_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(worlds[0])); writer.writeheader(); writer.writerows(worlds)
    aggregate: dict[str, Any] = {"worlds": len(worlds), "technical_failures": sum(world["technical_failure"] for world in worlds), "by_model": {}}
    for model in sorted({str(world["model"]) for world in worlds}):
        selected = [world for world in worlds if str(world["model"]) == model]
        aggregate["by_model"][model] = {key: mean_available(selected, key) for key in ("alive_agent_days", "verified_production", "calls_per_solved_task", "assignment_gini", "energy_gini", "office_concentration", "forecast_brier_loss")}
    conditions = sorted({str(world["condition"]) for world in worlds if world.get("condition")})
    if conditions:
        aggregate["by_condition"] = {}
        for condition in conditions:
            aggregate["by_condition"][condition] = {}
            for model in sorted({str(world["model"]) for world in worlds if str(world.get("condition")) == condition}):
                selected = [world for world in worlds if str(world.get("condition")) == condition and str(world["model"]) == model]
                aggregate["by_condition"][condition][model] = {key: mean_available(selected, key) for key in ("alive_agent_days", "verified_production", "calls_per_solved_task", "assignment_gini", "energy_gini", "office_concentration", "forecast_brier_loss")}
    (args.output / "aggregate.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pooled = {key: mean_available(worlds, key) for key in ("alive_agent_days", "verified_production", "calls_per_solved_task", "assignment_gini", "energy_gini", "office_concentration", "forecast_brier_loss")}
    latex = [
        "% Generated from frozen world exports; do not hand edit.",
        f"\\newcommand{{\\ResultWorlds}}{{{len(worlds)}}}",
        f"\\newcommand{{\\ResultAliveAgentDays}}{{{fmt(pooled['alive_agent_days'])}}}",
        f"\\newcommand{{\\ResultVerifiedProduction}}{{{fmt(pooled['verified_production'])}}}",
        f"\\newcommand{{\\ResultCallsPerSolve}}{{{fmt(pooled['calls_per_solved_task'])}}}",
        f"\\newcommand{{\\ResultAssignmentGini}}{{{fmt(pooled['assignment_gini'])}}}",
        f"\\newcommand{{\\ResultEnergyGini}}{{{fmt(pooled['energy_gini'])}}}",
        f"\\newcommand{{\\ResultOfficeConcentration}}{{{fmt(pooled['office_concentration'])}}}",
        f"\\newcommand{{\\ResultForecastBrier}}{{{fmt(pooled['forecast_brier_loss'])}}}",
        "\\newcommand{\\ResultEthicsRate}{--}",
    ]
    args.latex.parent.mkdir(parents=True, exist_ok=True)
    args.latex.write_text("\n".join(latex) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
