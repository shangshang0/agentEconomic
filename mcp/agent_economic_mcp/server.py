from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .catalog import (
    asset_path,
    find_asset,
    find_world,
    iter_jsonl,
    load_assets,
    repository_root,
    select_worlds,
    sha256,
    world_path,
)


def _compact(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[: max(0, min(limit, 500))]


def list_worlds_impl(
    tier: str | None = None,
    condition: str | None = None,
    model: str | None = None,
    terminal_status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = select_worlds(
        tier=tier,
        condition=condition,
        model=model,
        terminal_status=terminal_status,
    )
    keys = (
        "run_id",
        "evidence_tier",
        "analysis_eligible",
        "condition",
        "model",
        "seed",
        "terminal_status",
        "recovery_amendment",
        "release_part",
    )
    return _compact([{key: row.get(key) for key in keys} for row in rows], limit)


def get_world_impl(run_id: str) -> dict[str, Any]:
    return find_world(run_id)


def list_assets_impl(run_id: str | None = None, tier: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    rows = load_assets()
    if run_id is not None:
        rows = [row for row in rows if row.get("run_id") == run_id]
    if tier is not None:
        rows = [row for row in rows if row.get("evidence_tier") == tier]
    keys = (
        "asset_id",
        "asset_kind",
        "run_id",
        "evidence_tier",
        "terminal_status",
        "trace_status",
        "release_part",
        "release_path",
    )
    return _compact([{key: row.get(key) for key in keys} for row in rows], limit)


def get_asset_impl(asset_id: str) -> dict[str, Any]:
    return find_asset(asset_id)


def query_events_impl(
    run_id: str,
    kind: str | None = None,
    actor: str | None = None,
    text: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    base = world_path(run_id)
    path = base / "data-v2/authority-world-v2.events.jsonl"
    if not path.is_file():
        path = base / "data/authority-world-v1.events.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"download/extract the release containing {run_id}")
    matches: list[dict[str, Any]] = []
    for row in iter_jsonl(path):
        if kind and row.get("kind") != kind and row.get("type") != kind:
            continue
        if actor and actor not in {row.get("actor"), row.get("agent_id"), row.get("sender")}:
            continue
        if text and text.casefold() not in json.dumps(row, ensure_ascii=False).casefold():
            continue
        matches.append(row)
        if len(matches) >= min(limit, 500):
            break
    return matches


def search_dialogue_impl(run_id: str, query: str, limit: int = 50) -> list[dict[str, Any]]:
    base = world_path(run_id)
    candidates = [base / "gateway-data-v2/authority-world-v1.gateway.jsonl"]
    candidates.extend(sorted(base.glob("agent-state-v2/a*/runner-v2/runs/*/audit.raw.jsonl")))
    candidates.append(base / "gateway-data/authority-world-v1.gateway.jsonl")
    candidates.extend(sorted(base.glob("agent-state/a*/runner/events.jsonl")))
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    for path in candidates:
        if not path.is_file():
            continue
        for row in iter_jsonl(path):
            rendered = json.dumps(row, ensure_ascii=False)
            if needle in rendered.casefold():
                matches.append({"source": str(path.relative_to(base)), "record": row})
                if len(matches) >= min(limit, 200):
                    return matches
    return matches


def verify_world_impl(run_id: str) -> dict[str, Any]:
    catalog = find_world(run_id)
    base = world_path(run_id)
    manifest_path = repository_root() / "data/manifests/public-data-manifest.json"
    if not base.is_dir():
        return {"run_id": run_id, "downloaded": False, "catalog": catalog}
    state_path = base / "data-v2/authority-world-v2.state.json"
    events_path = base / "data-v2/authority-world-v2.events.jsonl"
    if not state_path.is_file() and not events_path.is_file():
        state_path = base / "data/authority-world-v1.state.json"
        events_path = base / "data/authority-world-v1.events.jsonl"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    event_lines = sum(1 for _ in events_path.open(encoding="utf-8"))
    result = {
        "run_id": run_id,
        "downloaded": True,
        "state_status": state.get("status"),
        "state_event_seq": state.get("event_seq"),
        "event_lines": event_lines,
        "event_sequence_matches": state.get("event_seq") == event_lines,
        "state_sha256": sha256(state_path),
        "manifest_available": manifest_path.is_file(),
    }
    return result


def verify_release_manifest_impl(manifest: str) -> dict[str, Any]:
    root = repository_root()
    path = (root / manifest).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError("manifest must be an existing file inside the repository")
    document = json.loads(path.read_text(encoding="utf-8"))
    records = document.get("files")
    if not isinstance(records, list):
        raise ValueError("manifest has no files array")
    errors: list[str] = []
    base = path.parent
    seen: set[str] = set()
    for record in records:
        relative = str(record.get("path", ""))
        candidate = (base / relative).resolve()
        if not relative or relative in seen or base not in candidate.parents:
            errors.append(f"unsafe/duplicate path: {relative}")
            continue
        seen.add(relative)
        if not candidate.is_file():
            errors.append(f"missing: {relative}")
            continue
        if candidate.stat().st_size != record.get("bytes"):
            errors.append(f"size mismatch: {relative}")
        if sha256(candidate) != record.get("sha256"):
            errors.append(f"sha256 mismatch: {relative}")
    return {"manifest": manifest, "files": len(records), "valid": not errors, "errors": errors[:100]}


def registered_analysis_plan_impl(tier: str = "confirmatory") -> dict[str, Any]:
    worlds = [row for row in select_worlds(tier=tier) if row.get("analysis_eligible")]
    run_ids = [str(row["run_id"]) for row in worlds]
    return {
        "analysis_unit": "world",
        "evidence_tier": tier,
        "run_ids": run_ids,
        "worlds": len(run_ids),
        "command": "make reproduce",
        "warnings": [
            "Do not use messages, agents, calls, or events as independent replicates.",
            "Apply only the frozen pairing/blocking and sensitivity rules recorded in the release.",
        ],
    }


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised in packaging smoke
        raise SystemExit("Install the MCP extra: pip install -e '.[mcp]'") from exc

    server = FastMCP("agent-economic")
    server.tool()(list_worlds_impl)
    server.tool()(get_world_impl)
    server.tool()(list_assets_impl)
    server.tool()(get_asset_impl)
    server.tool()(query_events_impl)
    server.tool()(search_dialogue_impl)
    server.tool()(verify_world_impl)
    server.tool()(verify_release_manifest_impl)
    server.tool()(registered_analysis_plan_impl)

    @server.resource("agent-economic://catalog")
    def catalog_resource() -> str:
        return "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in select_worlds())

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
