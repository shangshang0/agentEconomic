"""Recoverable constrained participant executor (fallback-v1).

This is intentionally not an autonomous strategy script.  It owns only
durable context, idempotent transport and wake-up lifecycle; the upstream
model selects every world action through backend tool schemas.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


BASE = os.environ["BACKEND_URL"].rstrip("/")
AGENT_ID = os.environ["AGENT_ID"]
TOKEN = os.environ["AGENT_TOKEN"]
PROFILE = os.getenv("MODEL_PROFILE", "default")
STATE = Path(os.getenv("RUNNER_STATE_DIR", "/state/runner"))
EVENTS = STATE / "events.jsonl"
CHECKPOINT = STATE / "checkpoint.json"
HEARTBEAT = Path("/state/executor.heartbeat")
DEGRADED = Path("/state/executor.degraded")
MAX_EVENTS = int(os.getenv("RUNNER_CONTEXT_EVENTS", "36"))
MAX_CHARS = int(os.getenv("RUNNER_CONTEXT_CHARS", "12000"))


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def _event(kind: str, value: dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    row = {"at": time.time(), "kind": kind, **value}
    with EVENTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush(); os.fsync(handle.fileno())


def _checkpoint(**value: Any) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    prior = json.loads(CHECKPOINT.read_text()) if CHECKPOINT.exists() else {}
    prior.update(value); prior["updated_at"] = time.time()
    _atomic_json(CHECKPOINT, prior)


def request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 240) -> tuple[bool, dict[str, Any]]:
    raw = json.dumps(payload).encode() if payload is not None else None
    call = urllib.request.Request(BASE + path, data=raw, method=method, headers={"Authorization": "Bearer " + TOKEN, "X-Agent-ID": AGENT_ID})
    if raw is not None:
        call.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(call, timeout=timeout) as response:
            return True, json.load(response)
    except urllib.error.HTTPError as error:
        try: detail = json.load(error)
        except Exception: detail = {"status": error.code}
        return False, {"status": error.code, "error": detail}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return False, {"transient": True, "error": str(error)}


def context() -> list[dict[str, Any]]:
    """Return only auditable, bounded visible history; never hidden reasoning."""
    if not EVENTS.exists():
        return []
    rows = [json.loads(line) for line in EVENTS.read_text(encoding="utf-8").splitlines() if line.strip()][-MAX_EVENTS:]
    out: list[dict[str, Any]] = []
    remaining = MAX_CHARS
    for row in reversed(rows):
        # Large panels recur in every tool output and are supplied separately by
        # backend; retaining them would create artificial context collapse.
        row.pop("panel", None)
        encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > remaining:
            continue
        out.append(row); remaining -= len(encoded)
    return list(reversed(out))


def run_turn() -> None:
    request_id = f"fallback-v1:{AGENT_ID}:{uuid.uuid4().hex}"
    _checkpoint(inflight_request_id=request_id, phase="model")
    ok, model = request("POST", f"/v1/agents/{AGENT_ID}/model-response", {
        "request_id": request_id, "model_profile": PROFILE, "agent_context": context(),
    })
    if not ok:
        _event("model_error", {"request_id": request_id, **model}); _checkpoint(phase="idle")
        return
    _event("model_response", {"request_id": request_id, "text": model.get("text", ""), "function_calls": model.get("function_calls", [])})
    calls = model.get("function_calls", [])
    if not isinstance(calls, list) or not calls:
        _checkpoint(phase="idle"); return
    prepared: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for call in calls:
        try: arguments = json.loads(call.get("arguments", "{}"))
        except (TypeError, json.JSONDecodeError):
            _event("invalid_call", {"request_id": request_id, "call": call}); continue
        call_id = str(call.get("call_id") or f"fallback:{uuid.uuid4().hex}")
        prepared.append((call, arguments, call_id))
    _checkpoint(inflight_request_id=request_id, inflight_call_ids=[call_id for _, _, call_id in prepared], phase="tool")

    def execute(call: dict[str, Any], arguments: dict[str, Any], call_id: str) -> tuple[dict[str, Any], str, bool, dict[str, Any]]:
        ok, result = request("POST", f"/v1/agents/{AGENT_ID}/tools", {
            "turn_id": request_id, "call_id": call_id, "name": call.get("name"), "arguments": arguments,
        }, timeout=60)
        return call, call_id, ok, result

    # Preserve the complete provider call bundle as genuinely concurrent
    # requests.  The backend lock + receipt IDs determine atomic order and
    # idempotency; the runner must not secretly serialize a model strategy.
    slept = any(call.get("name") == "sleep" for call, _, _ in prepared)
    with ThreadPoolExecutor(max_workers=max(1, len(prepared))) as pool:
        futures = [pool.submit(execute, call, arguments, call_id) for call, arguments, call_id in prepared]
        for future in as_completed(futures):
            call, call_id, ok, result = future.result()
            compact = dict(result)
            compact.pop("panel", None)
            _event("tool_result", {"request_id": request_id, "call_id": call_id, "name": call.get("name"), "ok": ok, **compact})
    _checkpoint(phase="sleeping" if slept else "idle", inflight_request_id=None, inflight_call_ids=[])


def main() -> None:
    consecutive_wake_failures = 0
    while True:
        HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT.write_text(str(time.time()), encoding="utf-8")
        ok, status = request("GET", f"/v1/agents/{AGENT_ID}/wake", timeout=15)
        if ok and status.get("ready"):
            consecutive_wake_failures = 0
            DEGRADED.unlink(missing_ok=True)
            run_turn()
            continue
        if ok:
            consecutive_wake_failures = 0
            DEGRADED.unlink(missing_ok=True)
        elif status.get("status") not in {409}:
            consecutive_wake_failures += 1
            _event("wake_error", status)
            if consecutive_wake_failures >= 3:
                DEGRADED.write_text(json.dumps({"agent_id": AGENT_ID, "consecutive_wake_failures": consecutive_wake_failures, "last": status}), encoding="utf-8")
        time.sleep(0.4)


if __name__ == "__main__":
    main()
