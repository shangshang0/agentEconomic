#!/usr/bin/env python3
"""Build a metadata-only inventory of Agent Economic world artifacts.

The output intentionally contains no dialogue or model payloads.  It is safe to
use as the first pass over a large experiment host before deciding which
canonical evidence roots need to be copied and redacted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "containerd",
    "docker",
    "node_modules",
    "overlay2",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"_read_error": type(exc).__name__}
    return value if isinstance(value, dict) else {"_read_error": "not_object"}


def walk_named(roots: Iterable[Path], filename: str) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for current, directories, files in os.walk(root, followlinks=False):
            directories[:] = [name for name in directories if name not in SKIP_DIRS]
            if filename not in files:
                continue
            path = Path(current) / filename
            try:
                identity = path.resolve()
            except OSError:
                identity = path.absolute()
            if identity not in seen:
                seen.add(identity)
                yield path


def file_fact(path: Path, *, hash_file: bool = False) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    result: dict[str, Any] = {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if hash_file:
        try:
            result["sha256"] = sha256(path)
        except OSError as exc:
            result["hash_error"] = type(exc).__name__
    return result


def trace_facts(world: Path, run_id: str, *, hash_evidence: bool) -> dict[str, Any]:
    v2_state = world / "data-v2/authority-world-v2.state.json"
    generation = "v2" if v2_state.is_file() else "v1"
    if generation == "v2":
        paths: dict[str, Path] = {
            "metadata": world / "run_metadata.json",
            "state": v2_state,
            "events": world / "data-v2/authority-world-v2.events.jsonl",
            "gateway": world / "gateway-data-v2/authority-world-v1.gateway.jsonl",
        }
        for number in range(1, 7):
            base = world / "agent-state-v2" / f"a{number}" / "runner-v2/runs" / run_id
            paths[f"a{number}_audit"] = base / "audit.raw.jsonl"
            paths[f"a{number}_context"] = base / "context.jsonl"
    else:
        paths = {
            "metadata": world / "run_metadata.json",
            "state": world / "data/authority-world-v1.state.json",
            "events": world / "data/authority-world-v1.events.jsonl",
            "gateway": world / "gateway-data/authority-world-v1.gateway.jsonl",
        }
        for number in range(1, 7):
            paths[f"a{number}_audit"] = world / "agent-state" / f"a{number}" / "runner/events.jsonl"
    facts = {
        name: fact
        for name, path in paths.items()
        if (fact := file_fact(path, hash_file=hash_evidence)) is not None
    }
    return {
        "schema_generation": generation,
        "files": facts,
        "audit_agents": sum(f"a{number}_audit" in facts for number in range(1, 7)),
        "context_agents": sum(f"a{number}_context" in facts for number in range(1, 7)),
        "has_state": "state" in facts,
        "has_events": "events" in facts,
        "has_gateway": "gateway" in facts,
        "evidence_bytes": sum(int(fact["bytes"]) for fact in facts.values()),
    }


def inventory_world(path: Path, source_id: str, *, hash_evidence: bool) -> dict[str, Any]:
    metadata = load_object(path)
    world = path.parent
    run_id = str(metadata.get("run_id") or "")
    state_path = world / "data-v2/authority-world-v2.state.json"
    if not state_path.is_file():
        state_path = world / "data/authority-world-v1.state.json"
    state = load_object(state_path) if state_path.is_file() else {}
    return {
        "record_type": "world",
        "source_id": source_id,
        "source_path": str(world),
        "run_id": run_id or None,
        "terminal_status": metadata.get("terminal_status"),
        "ok": metadata.get("ok"),
        "phase": metadata.get("phase"),
        "model": metadata.get("model"),
        "seed": metadata.get("seed"),
        "config": metadata.get("config"),
        "config_hash": metadata.get("config_hash"),
        "protocol_hash": metadata.get("protocol_hash"),
        "task_manifest_hash": metadata.get("task_manifest_hash"),
        "archived_at": metadata.get("archived_at"),
        "state_summary": {
            "status": state.get("status"),
            "day": state.get("day"),
            "event_seq": state.get("event_seq"),
        },
        "trace": trace_facts(world, run_id, hash_evidence=hash_evidence),
    }


def registry_records(path: Path, source_id: str) -> Iterable[dict[str, Any]]:
    try:
        handle = path.open(encoding="utf-8")
    except OSError as exc:
        yield {
            "record_type": "registry_error",
            "source_id": source_id,
            "source_path": str(path),
            "error": type(exc).__name__,
        }
        return
    with handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                yield {
                    "record_type": "registry_error",
                    "source_id": source_id,
                    "source_path": str(path),
                    "line": line_number,
                    "error": "JSONDecodeError",
                }
                continue
            if not isinstance(value, dict):
                continue
            yield {
                "record_type": "registry_entry",
                "source_id": source_id,
                "source_path": str(path),
                "line": line_number,
                "run_id": value.get("run_id"),
                "terminal_status": value.get("terminal_status"),
                "status": value.get("status"),
                "ok": value.get("ok"),
                "reason": value.get("reason") or value.get("failure_reason"),
                "archived_at": value.get("archived_at") or value.get("completed_at"),
            }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--hash-evidence", action="store_true")
    args = parser.parse_args()

    records: list[dict[str, Any]] = []
    for path in walk_named(args.roots, "run_metadata.json"):
        records.append(inventory_world(path, args.source_id, hash_evidence=args.hash_evidence))
    for path in walk_named(args.roots, "run_registry.jsonl"):
        records.extend(registry_records(path, args.source_id))
    records.sort(
        key=lambda row: (
            str(row.get("record_type")),
            str(row.get("run_id")),
            str(row.get("source_path")),
            int(row.get("line") or 0),
        )
    )
    for record in records:
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
