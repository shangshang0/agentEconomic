#!/usr/bin/env python3
"""Audit that a world preserves every agent turn, tool receipt, and exchange."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any, Iterable


def jsonl(
    path: Path,
    parse_errors: list[str] | None = None,
    label: str | None = None,
) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8", errors="strict") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                if parse_errors is None:
                    raise
                parse_errors.append(
                    f"{label or path.name}: invalid JSON at line {number} ({exc.msg})"
                )
                continue
            if not isinstance(value, dict):
                if parse_errors is None:
                    raise ValueError(f"{path}:{number}: record is not an object")
                parse_errors.append(
                    f"{label or path.name}: non-object JSON record at line {number}"
                )
                continue
            yield number, value


def kind(row: dict[str, Any]) -> str:
    return str(row.get("kind") or row.get("type") or "<none>")


def call_identity(call: dict[str, Any]) -> str | None:
    value = call.get("call_id") or call.get("id")
    return str(value) if value else None


def context_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    """Return the fields that the compact execution context promises to retain.

    ``audit.raw.jsonl`` is the authoritative receipt stream.  In runtime v2 the
    context copy deliberately stores an empty receipt object for tool results,
    so comparing raw rows would incorrectly reject intact worlds.  Model turns,
    by contrast, are expected to be byte-for-byte equivalent as parsed JSON.
    """

    row_kind = kind(row)
    if row_kind == "model_response":
        return (
            row_kind,
            row.get("request_id"),
            row.get("text"),
            row.get("function_calls"),
        )
    if row_kind == "tool_result":
        return (row_kind, row.get("name"), row.get("ok"))
    # Error records vary slightly between runtime revisions.  Compare every
    # stable field present in both streams below, after enforcing kind order.
    return (row_kind,)


def audit(world: Path, allow_partial: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    metadata_path = world / "run_metadata.json"
    if not metadata_path.is_file():
        raise ValueError("run_metadata.json is missing")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    run_id = str(metadata.get("run_id", ""))
    if not run_id:
        raise ValueError("run_metadata has no run_id")
    state_path = world / "data-v2/authority-world-v2.state.json"
    events_path = world / "data-v2/authority-world-v2.events.jsonl"
    schema_generation = "v2"
    if not state_path.is_file() and not events_path.is_file():
        schema_generation = "v1"
        state_path = world / "data/authority-world-v1.state.json"
        events_path = world / "data/authority-world-v1.events.jsonl"
    if not state_path.is_file() or not events_path.is_file():
        errors.append("state/events pair is incomplete")
        state: dict[str, Any] = {}
        event_rows: list[tuple[int, dict[str, Any]]] = []
    else:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        event_rows = list(jsonl(events_path, errors, "events JSONL"))
        if state.get("event_seq") != len(event_rows):
            errors.append("state event_seq differs from nonblank event records")
        sequences = [row.get("seq") or row.get("event_seq") for _, row in event_rows]
        if all(isinstance(value, int) for value in sequences):
            first = int(sequences[0]) if sequences else 1
            if sequences != list(range(first, first + len(sequences))):
                errors.append("event sequence is not contiguous")

    matrix: dict[str, Any] = {}
    total_model_responses = 0
    model_request_agents: dict[str, str] = {}
    result_call_ids: set[str] = set()
    requested_call_ids: set[str] = set()
    requested_calls: dict[str, tuple[str, str, str | None]] = {}
    missing_tool_payloads: collections.Counter[str] = collections.Counter()
    agent_model_counts: dict[str, int] = {}
    for number in range(1, 7):
        agent = f"A{number}"
        if schema_generation == "v2":
            base = world / "agent-state-v2" / agent.lower() / "runner-v2/runs" / run_id
            audit_path = base / "audit.raw.jsonl"
            context_path: Path | None = base / "context.jsonl"
            if not audit_path.is_file() or not context_path.is_file():
                errors.append(f"{agent}: audit/context pair is incomplete")
                continue
        else:
            base = world / "agent-state" / agent.lower() / "runner"
            audit_path = base / "events.jsonl"
            context_path = None
            if not audit_path.is_file():
                errors.append(f"{agent}: legacy runner event stream is missing")
                continue
        audit_rows = list(jsonl(audit_path, errors, f"{agent} audit.raw.jsonl"))
        context_rows = (
            list(jsonl(context_path, errors, f"{agent} context.jsonl"))
            if context_path
            else []
        )
        audit_kinds = collections.Counter(kind(row) for _, row in audit_rows)
        context_kinds = collections.Counter(kind(row) for _, row in context_rows)
        if context_path:
            if len(audit_rows) != len(context_rows) or audit_kinds != context_kinds:
                errors.append(f"{agent}: audit/context row or kind counts differ")
            comparable_audit = [context_identity(row) for _, row in audit_rows]
            comparable_context = [context_identity(row) for _, row in context_rows]
            if comparable_audit != comparable_context:
                errors.append(f"{agent}: audit/context record ordering differs")
        for line, row in audit_rows:
            row_kind = kind(row)
            if row_kind == "model_response":
                total_model_responses += 1
                if not row.get("request_id") or "text" not in row or "function_calls" not in row:
                    errors.append(f"{agent}: malformed model_response at audit line {line}")
                elif str(row["request_id"]) in model_request_agents:
                    errors.append(f"duplicate model response request ID at {agent} audit line {line}")
                else:
                    model_request_agents[str(row["request_id"])] = agent
                calls = row.get("function_calls") or []
                if not isinstance(calls, list):
                    errors.append(f"{agent}: function_calls is not a list at audit line {line}")
                else:
                    for call in calls:
                        identity = call_identity(call) if isinstance(call, dict) else None
                        if identity:
                            requested_call_ids.add(identity)
                            requested_calls[identity] = (
                                agent,
                                str(call.get("name") or "<unnamed>"),
                                str(row.get("request_id")) if row.get("request_id") else None,
                            )
                        else:
                            errors.append(f"{agent}: tool call lacks call ID at audit line {line}")
            elif row_kind == "tool_result":
                identity = call_identity(row)
                if not identity or not row.get("name"):
                    errors.append(f"{agent}: malformed tool_result at audit line {line}")
                elif identity in result_call_ids:
                    errors.append(f"duplicate tool result call ID: {identity}")
                else:
                    result_call_ids.add(identity)
                    if "result" not in row and "error" not in row:
                        missing_tool_payloads[str(row.get("name") or "<unnamed>")] += 1
        agent_model_counts[agent] = audit_kinds.get("model_response", 0)
        matrix[agent] = {
            "audit_rows": len(audit_rows),
            "context_rows": len(context_rows) if context_path else None,
            "kinds": dict(sorted(audit_kinds.items())),
            "audit_bytes": audit_path.stat().st_size,
            "context_bytes": context_path.stat().st_size if context_path else None,
        }

    missing_results = requested_call_ids - result_call_ids
    orphan_results = result_call_ids - requested_call_ids
    if missing_results:
        errors.append(f"{len(missing_results)} function call(s) lack tool_result")
    if orphan_results:
        warnings.append(f"{len(orphan_results)} tool_result(s) have no model function_call in retained audit")
    if missing_tool_payloads:
        errors.append(
            f"{sum(missing_tool_payloads.values())} tool_result receipt(s) lack result/error payload"
        )

    gateway_path = world / "gateway-data-v2/authority-world-v1.gateway.jsonl"
    if schema_generation == "v1":
        gateway_path = world / "gateway-data/authority-world-v1.gateway.jsonl"
    gateway_counts: collections.Counter[str] = collections.Counter()
    gateway_by_agent: collections.Counter[str] = collections.Counter()
    gateway_request_agents: dict[str, str] = {}
    if not gateway_path.is_file():
        errors.append("gateway trace is missing")
    else:
        for line, row in jsonl(gateway_path, errors, "gateway JSONL"):
            row_kind = kind(row)
            gateway_counts[row_kind] += 1
            if row_kind == "exchange":
                if not row.get("request_id") or "request" not in row or "response" not in row:
                    errors.append(f"malformed gateway exchange at line {line}")
                agent_id = str(row.get("agent_id"))
                gateway_by_agent[agent_id] += 1
                if row.get("request_id"):
                    gateway_request_agents[str(row["request_id"])] = agent_id
        if gateway_counts["exchange"] != total_model_responses:
            errors.append("gateway exchange count differs from agent model_response count")
        for agent, count in agent_model_counts.items():
            if gateway_by_agent[agent] != count:
                errors.append(f"{agent}: gateway/model-response count differs")

    evidence_complete = not errors
    if allow_partial and errors:
        warnings.extend(f"partial evidence: {message}" for message in errors)
    missing_result_tools = collections.Counter(
        requested_calls[identity][1] for identity in missing_results if identity in requested_calls
    )
    missing_result_calls = [
        {
            "call_id": identity,
            "agent_id": requested_calls[identity][0],
            "tool": requested_calls[identity][1],
            "request_id": requested_calls[identity][2],
        }
        for identity in sorted(missing_results)
        if identity in requested_calls
    ]
    gateway_without_model = set(gateway_request_agents) - set(model_request_agents)
    model_without_gateway = set(model_request_agents) - set(gateway_request_agents)
    return {
        "schema_version": 1,
        "trace_schema_generation": schema_generation,
        "context_streams_emitted": schema_generation == "v2",
        "run_id": run_id,
        "terminal_status": metadata.get("terminal_status") or state.get("status"),
        "complete": evidence_complete,
        "audit_passed": evidence_complete or allow_partial,
        "partial_allowed": allow_partial,
        "errors": errors,
        "warnings": warnings,
        "events": len(event_rows),
        "model_responses": total_model_responses,
        "function_calls": len(requested_call_ids),
        "tool_results": len(result_call_ids),
        "missing_result_tools": dict(sorted(missing_result_tools.items())),
        "missing_result_calls": missing_result_calls,
        "missing_tool_payloads": dict(sorted(missing_tool_payloads.items())),
        "gateway": dict(sorted(gateway_counts.items())),
        "gateway_alignment": {
            "gateway_without_model": len(gateway_without_model),
            "gateway_without_model_by_agent": dict(
                sorted(collections.Counter(gateway_request_agents[value] for value in gateway_without_model).items())
            ),
            "model_without_gateway": len(model_without_gateway),
            "model_without_gateway_by_agent": dict(
                sorted(collections.Counter(model_request_agents[value] for value in model_without_gateway).items())
            ),
        },
        "agents": matrix,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("world", type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.world, args.allow_partial)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not result["audit_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
