#!/usr/bin/env python3
"""Reconstruct a privacy-minimized CTF agent/day and task panel from raw worlds."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path


AGENT_RE = re.compile(r"agent-state-v2/(a\d+)/runner-v2/runs/")
TIERS = ("easy", "medium", "hard")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path: Path):
    with path.open() as f:
        for line_no, line in enumerate(f, 1):
            if line.strip():
                yield line_no, json.loads(line)


def ids_from_menu(items):
    out = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                task_id = item.get("task_id", item.get("id"))
                if task_id is not None:
                    out.append(str(task_id))
    return sorted(set(out))


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world-root", required=True, type=Path)
    ap.add_argument("--metadata", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with args.metadata.open() as f:
        meta_rows = list(csv.DictReader(f, delimiter="\t"))
    if len(meta_rows) != 24:
        raise SystemExit(f"expected 24 metadata rows, found {len(meta_rows)}")

    world_summaries = []
    agent_day_rows = []
    task_rows = []
    source_manifest = []

    for meta in meta_rows:
        run_id = meta["run_id"]
        root = args.world_root / run_id
        if not root.is_dir():
            raise SystemExit(f"missing raw world directory: {root}")
        event_files = sorted((root / "data-v2").glob("*.events.jsonl"))
        state_files = sorted((root / "data-v2").glob("*.state.json"))
        if len(event_files) != 1 or len(state_files) != 1:
            raise SystemExit(f"expected one event log/state file for {run_id}")
        event_path, state_path = event_files[0], state_files[0]
        state = json.loads(state_path.read_text())
        config = state["config"]
        events = [obj for _, obj in read_jsonl(event_path)]
        event_count = len(events)
        agents = sorted(state["agents"].keys())
        world = {
            "run_id": run_id,
            "stage": meta["stage"],
            "family": meta["family"],
            "regime": meta["regime"],
            "seed": meta["seed"],
            "pair_run_id": meta.get("pair_run_id", ""),
            "allocation_mechanism": config.get("allocation_mechanism", ""),
            "allocator_selection": config.get("allocator_selection", ""),
            "objective_prompt": config.get("objective_prompt", ""),
            "institution_semantics": config.get("institution_semantics", ""),
            "initial_energy": config.get("initial_energy"),
            "basal_energy_drain": config.get("basal_energy_drain"),
            "model_request_energy_cost": config.get("model_request_energy_cost"),
            "terminal_day": state.get("day"),
            "terminal_status": state.get("status"),
            "agents": len(agents),
            "event_count": event_count,
        }
        source_manifest.extend([
            {"run_id": run_id, "source": f"{run_id}/data-v2/{event_path.name}", "sha256": sha256(event_path), "records": event_count},
            {"run_id": run_id, "source": f"{run_id}/data-v2/{state_path.name}", "sha256": sha256(state_path), "records": 1},
        ])

        offers = {}
        task_assignment_events = defaultdict(list)
        task_open_events = defaultdict(list)
        task_submissions = defaultdict(list)
        task_closures = defaultdict(list)
        deaths = {}
        event_counts = Counter()
        started_days = []
        for e in events:
            kind, day = e.get("kind", ""), int(e.get("day", 0) or 0)
            event_counts[kind] += 1
            data = e.get("data") or {}
            if kind == "daily_tasks_offered":
                offers[day] = ids_from_menu(data.get("task_ids", []))
            elif kind == "task_assigned":
                task_assignment_events[str(data.get("task_id"))].append({
                    "day": day, "allocator": e.get("actor", ""),
                    "recipient": data.get("recipient_id", ""), "seq": e.get("seq"),
                })
            elif kind == "task_opened":
                task_open_events[str(data.get("task_id"))].append({"day": day, "agent": e.get("actor", "")})
            elif kind == "task_flag_submitted":
                task_submissions[str(data.get("task_id"))].append({
                    "day": day, "agent": e.get("actor", ""),
                    "correct": bool(data.get("correct")), "reward": data.get("reward"),
                })
            elif kind == "task_closed":
                task_closures[str(data.get("task_id"))].append({"day": day, "reason": data.get("reason", "")})
            elif kind == "agent_died":
                deaths[str(data.get("agent_id"))] = day
            elif kind == "day_started":
                started_days.append(day)

        # Replay the resource ledger from the configured initial endowment. For
        # charge/refund events, prefer the backend's recorded balance where it
        # supplies one. Basal drain is applied to agents still alive at that
        # event; task rewards accrue only on verified correct submissions.
        energy = {agent: float(config.get("initial_energy", 0.0)) for agent in agents}
        alive = {agent: True for agent in agents}
        daily_energy_start = {}
        daily_energy_end = {}
        daily_components = defaultdict(lambda: defaultdict(float))
        replay_discrepancies = []
        for e in events:
            kind, day = e.get("kind", ""), int(e.get("day", 0) or 0)
            data = e.get("data") or {}
            if kind in {"world_started", "day_started"}:
                d = int(data.get("day", day) or day)
                if d and d not in daily_energy_start:
                    daily_energy_start[d] = dict(energy)
            actor = str(e.get("actor", ""))
            if kind == "model_request_energy_consumed" and actor in energy:
                before = energy[actor]
                if "remaining" in data:
                    energy[actor] = float(data["remaining"])
                else:
                    energy[actor] -= float(data.get("amount", 0.0))
                daily_components[day][actor] += energy[actor] - before
            elif kind == "task_open_cost_paid" and actor in energy:
                amount = float(data.get("amount", 0.0))
                energy[actor] -= amount
                daily_components[day][actor] -= amount
            elif kind == "technical_model_request_energy_refunded" and actor in energy:
                before = energy[actor]
                if "energy_after" in data:
                    energy[actor] = float(data["energy_after"])
                else:
                    energy[actor] += float(data.get("amount", 0.0))
                daily_components[day][actor] += energy[actor] - before
            elif kind == "energy_transferred" and actor in energy:
                amount = float(data.get("amount", 0.0))
                recipient = str(data.get("to", ""))
                energy[actor] -= amount
                daily_components[day][actor] -= amount
                if recipient in energy:
                    energy[recipient] += amount
                    daily_components[day][recipient] += amount
            elif kind == "task_flag_submitted" and actor in energy and data.get("correct"):
                reward = float(data.get("reward", 0.0))
                energy[actor] += reward
                daily_components[day][actor] += reward
            elif kind == "basal_energy_drain":
                amount = float(data.get("amount", config.get("basal_energy_drain", 0.0)))
                for agent in agents:
                    if alive[agent]:
                        energy[agent] -= amount
                        daily_components[day][agent] -= amount
            elif kind == "agent_died":
                dead_agent = str(data.get("agent_id", ""))
                if dead_agent in alive:
                    alive[dead_agent] = False
                    energy[dead_agent] = 0.0
            if kind == "day_started":
                daily_energy_end[day - 1] = dict(energy)
        if daily_energy_start:
            last_day = max(daily_energy_start)
            daily_energy_end.setdefault(last_day, dict(energy))
        for agent in agents:
            final_state = state["agents"].get(agent, {})
            final_energy = float(final_state.get("energy", 0.0))
            if abs(energy[agent] - final_energy) > 1e-6:
                replay_discrepancies.append({"agent": agent, "replayed": energy[agent], "state": final_energy})

        # Read call traces but retain only action labels, task/recipient IDs, menu IDs,
        # and numeric energy snapshots. Response text, prompts, messages, commands,
        # flag contents, and provider metadata are deliberately discarded.
        trace_calls = defaultdict(list)
        trace_panels = defaultdict(list)
        trace_file_count = 0
        day_markers = [(float(e.get("at_wall", 0) or 0), int(e.get("day", 1) or 1))
                       for e in events if e.get("kind") in {"day_started", "world_started"}]
        day_markers.sort()

        def infer_day(timestamp):
            d = 1
            for t, day in day_markers:
                if t <= timestamp:
                    d = day
                else:
                    break
            return d

        for audit_path in sorted(root.glob("agent-state-v2/*/runner-v2/runs/*/audit.raw.jsonl")):
            match = AGENT_RE.search(str(audit_path))
            if not match:
                continue
            agent = match.group(1).upper()
            trace_file_count += 1
            calls_by_id = {}
            result_by_id = {}
            trace_hash = hashlib.sha256()
            audit_records = 0
            with audit_path.open("rb") as audit_file:
                for raw_line in audit_file:
                    trace_hash.update(raw_line)
                    audit_records += 1
                    record = json.loads(raw_line)
                    if record.get("kind") == "model_response":
                        for fc in record.get("function_calls", []):
                            call = {
                                "at": float(record.get("at", 0) or 0),
                                "name": str(fc.get("name", "")),
                                "call_id": fc.get("call_id", ""),
                                "arguments": fc.get("arguments", "{}"),
                                "day": None,
                            }
                            calls_by_id[call["call_id"]] = call
                    elif record.get("kind") == "tool_result":
                        cid = record.get("call_id", "")
                        result_by_id[cid] = record
                        call = calls_by_id.get(cid)
                        if call:
                            result = record.get("result") or {}
                            panel = result.get("panel", result) if isinstance(result, dict) else {}
                            day = panel.get("world_day") if isinstance(panel, dict) else None
                            call["day"] = int(day) if isinstance(day, int) else infer_day(float(record.get("at", call["at"])))
                            if call["name"] == "get_panel" and isinstance(panel, dict):
                                menu = ids_from_menu(panel.get("assignable_tasks", []))
                                visible = ids_from_menu(panel.get("tasks_today", []))
                                energy_value = panel.get("energy")
                                trace_panels[(agent, call["day"])].append({
                                    "at": float(record.get("at", call["at"])),
                                    "energy": energy_value,
                                    "menu": menu,
                                    "visible_tasks": visible,
                                    "status": panel.get("status"),
                                })
            source_manifest.append({
                "run_id": run_id,
                "source": f"{run_id}/agent-state-v2/{agent.lower()}/runner-v2/runs/{run_id}/audit.raw.jsonl",
                "sha256": trace_hash.hexdigest(),
                "records": audit_records,
            })
            for cid, call in calls_by_id.items():
                rec = result_by_id.get(cid)
                if call["day"] is None:
                    result = (rec or {}).get("result") or {}
                    panel = result.get("panel", result) if isinstance(result, dict) else {}
                    day = panel.get("world_day") if isinstance(panel, dict) else None
                    call["day"] = int(day) if isinstance(day, int) else infer_day(call["at"])
                args_obj = {}
                try:
                    args_obj = json.loads(call["arguments"]) if isinstance(call["arguments"], str) else call["arguments"]
                except (json.JSONDecodeError, TypeError):
                    args_obj = {}
                # Keep only fields that define an allocation proposal.
                safe = {}
                if call["name"] == "assign_task" and isinstance(args_obj, dict):
                    safe = {k: args_obj.get(k) for k in ("task_id", "recipient_id") if k in args_obj}
                trace_calls[(agent, call["day"])].append({
                    "name": call["name"], "proposal": safe,
                    "tool_call_ok": (rec.get("ok") if rec is not None else None),
                })

        if trace_file_count != len(agents):
            raise SystemExit(f"trace coverage mismatch {run_id}: {trace_file_count}/{len(agents)}")

        task_by_id = {str(t["id"]): t for t in state.get("tasks", [])}
        offer_by_task = {}
        for day, task_ids in offers.items():
            for task_id in task_ids:
                offer_by_task[task_id] = day
        all_task_ids = sorted(set(task_by_id) | set(offer_by_task))
        for task_id in all_task_ids:
            task = task_by_id.get(task_id, {})
            assign_events = task_assignment_events.get(task_id, [])
            submit_events = task_submissions.get(task_id, [])
            proposal_records = []
            for (proposer, proposal_day), calls in trace_calls.items():
                for call in calls:
                    if call["name"] == "assign_task" and call["proposal"].get("task_id") == task_id:
                        proposal_records.append({
                            "proposer": proposer,
                            "proposal_day": proposal_day,
                            "recipient": call["proposal"].get("recipient_id"),
                            "tool_call_ok": call["tool_call_ok"],
                        })
            task_rows.append({
                "run_id": run_id, "stage": meta["stage"], "family": meta["family"],
                "regime": meta["regime"], "seed": meta["seed"], "task_id": task_id,
                "offer_day": offer_by_task.get(task_id, task.get("day", "")),
                "tier": task.get("tier", "unknown"), "reward": task.get("reward", ""),
                "offered": int(task_id in offer_by_task),
                "assigned": int(bool(assign_events)),
                "allocator_proposal_count": sum(1 for entries in trace_calls.values()
                    for c in entries if c["name"] == "assign_task" and c["proposal"].get("task_id") == task_id),
                "allocator_proposal_tool_ok_count": sum(1 for entries in trace_calls.values()
                    for c in entries if c["name"] == "assign_task" and c["proposal"].get("task_id") == task_id and c["tool_call_ok"] is True),
                "allocation_proposals": json.dumps(proposal_records, sort_keys=True),
                "allocator_ids": json.dumps(sorted({a["allocator"] for a in assign_events})),
                "recipient_ids": json.dumps(sorted({str(a["recipient"]) for a in assign_events})),
                "open_agent_ids": json.dumps(sorted({o["agent"] for o in task_open_events.get(task_id, [])})),
                "submit_agent_ids": json.dumps(sorted({s["agent"] for s in submit_events})),
                "verified_attempts": len(submit_events),
                "verified_successes": sum(int(s["correct"]) for s in submit_events),
                "verified_failures": sum(int(not s["correct"]) for s in submit_events),
                "closed_reasons": json.dumps([c["reason"] for c in task_closures.get(task_id, [])]),
            })

        max_day = max(offers.keys() | set(started_days) | {int(state.get("day", 1))})
        max_day = min(max_day, 25)
        world_assignments = sum(len(v) for v in task_assignment_events.values())
        world_submits = sum(len(v) for v in task_submissions.values())
        world_successes = sum(sum(int(s["correct"]) for s in v) for v in task_submissions.values())
        world_proposals = sum(1 for calls in trace_calls.values() for c in calls if c["name"] == "assign_task")
        world["observed_days"] = max_day
        world["offered_tasks"] = sum(map(len, offers.values()))
        world["executed_assignments"] = world_assignments
        world["assignment_proposals"] = world_proposals
        world["verified_submissions"] = world_submits
        world["verified_successes"] = world_successes
        world["dead_agents"] = len(deaths)
        world["trace_agents"] = trace_file_count
        world["offered_day_count"] = len(offers)
        world["resource_ledger_replay_match"] = int(not replay_discrepancies)
        world["resource_ledger_discrepancies"] = json.dumps(replay_discrepancies, sort_keys=True)

        for day in range(1, max_day + 1):
            offered = offers.get(day, [])
            by_agent_assignments = defaultdict(list)
            for task_id, assigned_events in task_assignment_events.items():
                for ae in assigned_events:
                    if ae["day"] == day:
                        by_agent_assignments[str(ae["recipient"])].append(task_id)
            by_agent_proposals = defaultdict(list)
            call_counts = {}
            for (actor, call_day), calls in trace_calls.items():
                if call_day != day:
                    continue
                call_counts[actor] = Counter(c["name"] for c in calls)
                for call in calls:
                    if call["name"] == "assign_task":
                        by_agent_proposals[actor].append(call["proposal"])
            day_submits = defaultdict(list)
            for task_id, submissions in task_submissions.items():
                for sub in submissions:
                    if sub["day"] == day:
                        day_submits[sub["agent"]].append({"task_id": task_id, "correct": sub["correct"]})
            for agent in agents:
                panels = sorted(trace_panels.get((agent, day), []), key=lambda x: x["at"])
                start_dead_day = deaths.get(agent)
                alive_start = int(start_dead_day is None or start_dead_day >= day)
                alive_end = int(start_dead_day is None or start_dead_day > day)
                opened = sorted(task_id for task_id, opens in task_open_events.items()
                                if any(o["agent"] == agent and o["day"] == day for o in opens))
                agent_day_rows.append({
                    "run_id": run_id, "stage": meta["stage"], "family": meta["family"],
                    "regime": meta["regime"], "seed": meta["seed"], "day": day,
                    "agent_id": agent, "alive_start": alive_start, "alive_end": alive_end,
                    "offered_task_ids": json.dumps(offered),
                    "offered_task_count": len(offered),
                    "first_observed_assignable_menu": json.dumps(panels[0]["menu"] if panels else []),
                    "first_observed_visible_tasks_today": json.dumps(panels[0]["visible_tasks"] if panels else []),
                    "assignable_menu_observed": int(bool(panels)),
                    "assignable_menu_observation_count": len(panels),
                    "energy_first_panel": panels[0]["energy"] if panels else "",
                    "energy_last_panel": panels[-1]["energy"] if panels else "",
                    "energy_start_replayed": daily_energy_start.get(day, {}).get(agent, ""),
                    "energy_end_replayed": daily_energy_end.get(day, {}).get(agent, ""),
                    "energy_change_replayed": round(daily_components[day].get(agent, 0.0), 6),
                    "assign_task_proposals": json.dumps(by_agent_proposals.get(agent, []), sort_keys=True),
                    "proposal_count": len(by_agent_proposals.get(agent, [])),
                    "executed_assignments_to_agent": json.dumps(sorted(by_agent_assignments.get(agent, []))),
                    "opened_tasks": json.dumps(opened),
                    "verified_submissions": json.dumps(day_submits.get(agent, []), sort_keys=True),
                    "call_counts": json.dumps(dict(call_counts.get(agent, {})), sort_keys=True),
                })

        # Reconciliation checks: every executed assignment is represented in task rows,
        # every accepted submit has an event-level verified result, and offers join to
        # a task record (no silent zero-filling for missing outcome events).
        event_assigned_count = sum(len(v) for v in task_assignment_events.values())
        if event_assigned_count != world_assignments:
            raise SystemExit(f"assignment count mismatch in {run_id}")
        for task_id in offer_by_task:
            if task_id not in task_by_id:
                raise SystemExit(f"offered task absent from state in {run_id}: {task_id}")
        world["task_menu_join_complete"] = int(all(task_id in task_by_id for task_id in offer_by_task))
        world["verified_outcomes_from_events"] = 1
        world_summaries.append(world)

    write_csv(args.out / "agent_day_panel.csv", agent_day_rows, [
        "run_id", "stage", "family", "regime", "seed", "day", "agent_id",
        "alive_start", "alive_end", "offered_task_ids", "offered_task_count",
        "first_observed_assignable_menu", "assignable_menu_observed",
        "first_observed_visible_tasks_today",
        "assignable_menu_observation_count", "energy_first_panel", "energy_last_panel",
        "energy_start_replayed", "energy_end_replayed", "energy_change_replayed",
        "assign_task_proposals", "proposal_count", "executed_assignments_to_agent",
        "opened_tasks", "verified_submissions", "call_counts",
    ])
    write_csv(args.out / "task_panel.csv", task_rows, [
        "run_id", "stage", "family", "regime", "seed", "task_id", "offer_day", "tier",
        "reward", "offered", "assigned", "allocator_proposal_count", "allocator_proposal_tool_ok_count", "allocation_proposals", "allocator_ids",
        "recipient_ids", "open_agent_ids", "submit_agent_ids", "verified_attempts",
        "verified_successes", "verified_failures", "closed_reasons",
    ])
    write_csv(args.out / "world_summary.csv", world_summaries, list(world_summaries[0].keys()))

    # Frozen simple case law: stage1 slot frequencies, tier-stratified within
    # model-family × regime. Stage2 remains untouched for scoring.
    by_cell_tier = defaultdict(lambda: Counter())
    for row in task_rows:
        if row["stage"] != "stage1" or not row["offered"] or row["tier"] not in TIERS:
            continue
        key = (row["family"], row["regime"], row["tier"])
        c = by_cell_tier[key]
        c["offered"] += 1
        c["proposal_calls"] += int(row["allocator_proposal_count"])
        c["proposal_slots"] += int(int(row["allocator_proposal_count"]) > 0)
        c["tool_ok_calls"] += int(row["allocator_proposal_tool_ok_count"])
        c["assigned"] += int(row["assigned"])
        c["success"] += int(row["verified_successes"] > 0)
        c["failure_only"] += int(int(row["verified_failures"]) > 0 and int(row["verified_successes"]) == 0)
        c["verified_assigned"] += int(row["assigned"] and row["verified_attempts"] > 0)
        c["unattempted"] += int(row["assigned"] and row["verified_attempts"] == 0)
    frozen = {}
    for key, c in by_cell_tier.items():
        fam, regime, tier = key
        p_assign = c["assigned"] / c["offered"] if c["offered"] else None
        p_success = c["success"] / c["assigned"] if c["assigned"] else None
        frozen[key] = {"offered_n": c["offered"], "assigned_n": c["assigned"],
                       "proposal_slots_n": c["proposal_slots"], "proposal_calls_n": c["proposal_calls"],
                       "tool_ok_calls_n": c["tool_ok_calls"],
                       "verified_success_n": c["success"], "verified_failure_only_n": c["failure_only"],
                       "assigned_unattempted_n": c["unattempted"], "verified_assigned_n": c["verified_assigned"],
                       "p_proposal_slot": c["proposal_slots"] / c["offered"] if c["offered"] else None,
                       "p_tool_ok_given_proposal": c["tool_ok_calls"] / c["proposal_calls"] if c["proposal_calls"] else None,
                       "p_assign": p_assign, "p_success_given_assigned": p_success,
                       "p_failure_only_given_assigned": c["failure_only"] / c["assigned"] if c["assigned"] else None,
                       "p_unattempted_given_assigned": c["unattempted"] / c["assigned"] if c["assigned"] else None}
    predictions = []
    for w in world_summaries:
        if w["stage"] != "stage2":
            continue
        tasks = [r for r in task_rows if r["run_id"] == w["run_id"] and r["offered"] and r["tier"] in TIERS]
        pred_assigned = 0.0
        pred_success = 0.0
        cell_coverage = True
        for tier in TIERS:
            observed_n = sum(1 for r in tasks if r["tier"] == tier)
            law = frozen.get((w["family"], w["regime"], tier))
            if not law or law["p_assign"] is None or law["p_success_given_assigned"] is None:
                cell_coverage = False
                continue
            pred_assigned += observed_n * law["p_assign"]
            pred_success += observed_n * law["p_assign"] * law["p_success_given_assigned"]
        actual_assigned = sum(int(r["assigned"]) for r in tasks)
        actual_success = sum(int(r["verified_successes"] > 0) for r in tasks)
        predictions.append({
            "run_id": w["run_id"], "family": w["family"], "regime": w["regime"],
            "offered_slots": len(tasks), "coverage_complete": int(cell_coverage),
            "predicted_assignments": round(pred_assigned, 6), "observed_assignments": actual_assigned,
            "assignment_error_observed_minus_predicted": round(actual_assigned - pred_assigned, 6),
            "predicted_verified_successes": round(pred_success, 6), "observed_verified_successes": actual_success,
            "success_error_observed_minus_predicted": round(actual_success - pred_success, 6),
            "prediction_status": "retrospective_stage2_holdout; no refit",
        })
    write_csv(args.out / "stage1_frozen_stage2_predictions.csv", predictions, [
        "run_id", "family", "regime", "offered_slots", "coverage_complete",
        "predicted_assignments", "observed_assignments", "assignment_error_observed_minus_predicted",
        "predicted_verified_successes", "observed_verified_successes",
        "success_error_observed_minus_predicted", "prediction_status",
    ])

    summary = {
        "dataset": "final24 formal worlds",
        "source_metadata": args.metadata.name,
        "source_metadata_sha256": sha256(args.metadata),
        "world_count": len(world_summaries),
        "agent_day_rows": len(agent_day_rows),
        "task_rows": len(task_rows),
        "stage1_calibration_worlds": sum(w["stage"] == "stage1" for w in world_summaries),
        "stage2_holdout_worlds": sum(w["stage"] == "stage2" for w in world_summaries),
        "mechanism_worlds_not_pooled": sum(w["stage"] == "mechanism" for w in world_summaries),
        "trace_joined_worlds": sum(w["trace_agents"] == w["agents"] for w in world_summaries),
        "complete_menu_task_joins": sum(w["task_menu_join_complete"] for w in world_summaries),
        "resource_ledger_replay_matches": sum(w["resource_ledger_replay_match"] for w in world_summaries),
        "agent_days_alive_at_start": sum(int(r["alive_start"]) for r in agent_day_rows),
        "agent_day_rows_with_assignable_menu_snapshot": sum(int(r["assignable_menu_observed"]) for r in agent_day_rows),
        "agent_day_rows_with_energy_snapshot": sum(bool(r["energy_first_panel"] != "") for r in agent_day_rows),
        "i1_proposal_execution_identity_check": "asserted by generate_ctf_archive.py for every offered stage1/stage2 task slot",
        "model": {
            "outcome": "task assigned; task verified correct",
            "calibration": "stage1 only; family x regime x task tier empirical frequencies",
            "holdout": "stage2, no refit",
            "assumption": "task-slot exchangeability within family x regime x tier",
            "independence_assumption": False,
            "forecast_intervals": "not reported; calibration has few worlds and serial dependence is not modeled",
            "status": "retrospective temporal holdout, not prospectively frozen before stage2 outcomes",
        },
        "cell_laws": [
            {"family": k[0], "regime": k[1], "tier": k[2], **v}
            for k, v in sorted(frozen.items())
        ],
        "source_files": source_manifest,
    }
    (args.out / "case_model_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in (
        "world_count", "agent_day_rows", "task_rows", "stage1_calibration_worlds",
        "stage2_holdout_worlds", "mechanism_worlds_not_pooled", "trace_joined_worlds",
        "complete_menu_task_joins")}, indent=2))
    print("CELL LAWS")
    for cell in summary["cell_laws"]:
        print(cell)
    print("STAGE2 SCORES")
    for row in predictions:
        print(row)


if __name__ == "__main__":
    main()
