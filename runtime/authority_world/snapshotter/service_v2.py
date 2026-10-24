"""Barriered, immutable v2 world checkpoints.

The backend freezes new agent turns at startup and at every day boundary. The
snapshotter waits for every already-open turn to flush its audit/context trace,
then copies the durable world state, event log, agent traces, gateway log, and
configuration into an immutable bundle before acknowledging the barrier.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import traceback
import uuid
import urllib.request
from pathlib import Path

WORLD = Path(os.environ.get("WORLD_DATA_DIR", "/world-data"))
AGENTS = Path(os.environ.get("AGENT_STATE_DIR", "/agent-state"))
GATEWAY = Path(os.environ.get("GATEWAY_DATA_DIR", "/gateway-data"))
CONFIG = Path(os.environ.get("WORLD_CONFIG_DIR", "/world-config"))
OUT = Path(os.environ.get("SNAPSHOT_DIR", "/snapshots"))
BACKEND = os.environ["BACKEND_URL"].rstrip("/")
TOKEN = os.environ["WORLD_CONTROL_TOKEN"]
STATE = WORLD / "authority-world-v2.state.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def api(path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        BACKEND + path,
        data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json", "X-World-Control-Token": TOKEN},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def copy_tree(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copytree(source, target, dirs_exist_ok=False)
    else:
        target.mkdir(parents=True)


def acknowledge(snapshot_id: str) -> None:
    api("/v2/control/checkpoints/complete", {"snapshot_id": snapshot_id})


def build_trace_index(root: Path, run_id: str) -> dict:
    """Index turn-level traces inside the immutable snapshot bundle."""
    indexed: dict[str, dict] = {}
    identities: dict[str, tuple] = {}
    for path in sorted(root.rglob("*.jsonl")):
        relative = str(path.relative_to(root))
        if not any(token in relative for token in ("model-trace", "audit.raw", "context.jsonl", "gateway.jsonl")):
            continue
        counts: dict[str, int] = {}
        turns: dict[str, dict] = {}
        rows = 0
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                rows += 1
                kind = str(row.get("kind", "unknown")); counts[kind] = counts.get(kind, 0) + 1
                row_run = row.get("run_id")
                if row_run and row_run != run_id:
                    continue
                agent = row.get("agent_id")
                if not agent and "/agent-state-v2/" in ("/" + relative):
                    parts = Path(relative).parts
                    try:
                        index = parts.index("agent-state-v2")
                        agent = parts[index + 1]
                    except (ValueError, IndexError):
                        agent = None
                if row.get("trace_schema") and row.get("trace_schema") in {"authority-world-model-trace-v1", "authority-world-agent-trace-v1"}:
                    required = ("run_id", "agent_id", "request_id", "turn_seq")
                    missing = [key for key in required if row.get(key) is None]
                    if missing:
                        raise RuntimeError(f"incomplete turn trace identity in {relative}:{line_number}: {missing}")
                if agent and row.get("request_id"):
                    key = f"{agent}/{row['request_id']}"
                    identity = (row.get("run_id"), agent, row.get("turn_seq"), row.get("checkpoint_id"))
                    if row.get("turn_seq") is not None:
                        previous = identities.setdefault(key, identity)
                        if previous != identity:
                            raise RuntimeError(f"turn identity mismatch for {key}: {previous} != {identity}")
                    entry = turns.setdefault(key, {"agent_id": agent, "request_id": row["request_id"], "turn_seq": row.get("turn_seq"), "checkpoint_id": row.get("checkpoint_id"), "kinds": []})
                    if kind not in entry["kinds"]:
                        entry["kinds"].append(kind)
        indexed[relative] = {"rows": rows, "counts_by_kind": counts, "turns": list(turns.values())}
    return {"schema": "authority-world-trace-index-v1", "run_id": run_id, "files": indexed}


def take(pending: dict) -> None:
    snapshot_id = pending["snapshot_id"]
    target = OUT / snapshot_id
    if target.exists():
        manifest_path = target / "MANIFEST.json"
        if not manifest_path.is_file():
            raise RuntimeError(f"existing checkpoint has no manifest: {snapshot_id}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("snapshot_id") != snapshot_id or manifest.get("run_id") != json.loads(STATE.read_text(encoding="utf-8")).get("run_id"):
            raise RuntimeError(f"existing checkpoint identity mismatch: {snapshot_id}")
        for relative, expected in manifest.get("files", {}).items():
            file_path = target / relative
            if not file_path.is_file() or digest(file_path) != expected:
                raise RuntimeError(f"existing checkpoint hash mismatch: {snapshot_id}/{relative}")
        acknowledge(snapshot_id)
        return
    # A unique staging directory makes retries safe even if the previous
    # attempt was interrupted after writing only part of the bundle.
    staging = OUT / ("." + snapshot_id + ".partial-" + str(os.getpid()) + "-" + uuid.uuid4().hex)
    staging.mkdir(parents=True)
    try:
        copy_tree(WORLD, staging / "data-v2")
        copy_tree(AGENTS, staging / "agent-state-v2")
        copy_tree(GATEWAY, staging / "gateway-data-v2")
        copy_tree(CONFIG, staging / "config")
        captured = json.loads((staging / "data-v2" / "authority-world-v2.state.json").read_text(encoding="utf-8"))
        trace_index = build_trace_index(staging, str(captured.get("run_id")))
        (staging / "TRACE_INDEX.json").write_text(json.dumps(trace_index, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        files = sorted(path for path in staging.rglob("*") if path.is_file())
        manifest = {
            "schema": "authority-world-v2-snapshot-v2",
            "snapshot_id": snapshot_id,
            "kind": pending.get("kind"),
            "day": captured["day"],
            "event_seq": captured["event_seq"],
            "checkpoint_requested_event_seq": pending["event_seq"],
            "run_id": captured.get("run_id"),
            "trace_index": "TRACE_INDEX.json",
            "created_at": time.time(),
            "files": {str(path.relative_to(staging)): digest(path) for path in files},
        }
        manifest_path = staging / "MANIFEST.json"
        with manifest_path.open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, target)
        acknowledge(snapshot_id)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            api("/v2/control/checkpoints/register", {})
            status = api("/v2/control/checkpoints/pending")
            pending = status.get("pending")
            if isinstance(pending, dict) and status.get("active_turns", 0) == 0 and STATE.exists():
                take(pending)
        except Exception as error:
            print(f"v2 snapshotter error: {type(error).__name__}: {error}", flush=True)
            traceback.print_exc()
        time.sleep(0.25)


if __name__ == "__main__":
    main()
