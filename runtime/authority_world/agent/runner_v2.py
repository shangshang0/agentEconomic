"""Bounded-context fallback executor for Authority World v2.

It has no strategy. The backend's event-aware wake endpoint decides when a
model opportunity exists; this process only preserves auditable visible
context and transports tool calls selected by the model.
"""

from __future__ import annotations

import json, os, time, urllib.error, urllib.request, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

BASE = os.environ["BACKEND_URL"].rstrip("/"); AGENT_ID = os.environ["AGENT_ID"]; TOKEN = os.environ["AGENT_TOKEN"]
STATE = Path(os.getenv("RUNNER_STATE_DIR", "/state/runner-v2")); RUN_ID: str | None = None
MAX_EVENTS = int(os.getenv("RUNNER_CONTEXT_EVENTS", "36")); MAX_CHARS = int(os.getenv("RUNNER_CONTEXT_CHARS", "12000"))
TOOL_TIMEOUT_SECONDS = int(os.getenv("RUNNER_TOOL_TIMEOUT_SECONDS", "1200"))

def _run_dir() -> Path:
    if RUN_ID is None:
        raise RuntimeError("runner has not received a run id")
    return STATE / "runs" / RUN_ID

def _path(name: str) -> Path:
    return _run_dir() / name

def set_run(panel: dict[str, Any] | None) -> None:
    """Bind memory to the backend-issued immutable run id, never a container life."""
    global RUN_ID
    if not isinstance(panel, dict) or not isinstance(panel.get("run_id"), str):
        return
    incoming = panel["run_id"]
    if RUN_ID is not None and RUN_ID != incoming:
        raise RuntimeError("backend run id changed within a live runner")
    RUN_ID = incoming

def request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 240) -> tuple[bool, dict[str, Any]]:
    raw = json.dumps(payload).encode() if payload is not None else None
    call = urllib.request.Request(BASE + path, data=raw, method=method, headers={"Authorization": "Bearer " + TOKEN, "X-Agent-ID": AGENT_ID})
    if raw is not None: call.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(call, timeout=timeout) as response: return True, json.load(response)
    except urllib.error.HTTPError as error:
        try: return False, {"status": error.code, "error": json.load(error)}
        except Exception: return False, {"status": error.code}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error: return False, {"transient": True, "error": str(error)}

def event(kind: str, value: dict[str, Any], context_value: dict[str, Any] | None = None) -> None:
    """Persist full receipts for audit, but feed the model only a semantic receipt."""
    if RUN_ID is None:
        return
    folder = _run_dir(); folder.mkdir(parents=True, exist_ok=True)
    raw = {"at": time.time(), "kind": kind, **value}
    with _path("audit.raw.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(raw, ensure_ascii=False) + "\n")
    compact = {"at": raw["at"], "kind": kind, **(context_value if context_value is not None else value)}
    with _path("context.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(compact, ensure_ascii=False) + "\n")

def context() -> list[dict[str, Any]]:
    if RUN_ID is None or not _path("context.jsonl").exists(): return []
    result: list[dict[str, Any]] = []; remaining = MAX_CHARS
    # JSONL is delimited by the physical LF byte only. ``str.splitlines()``
    # also splits valid JSON strings containing NEL/U+2028/U+2029, which can
    # occur in task output and would make a persisted valid record unreadable.
    lines = _path("context.jsonl").read_text(encoding="utf-8").split("\n")
    for line in reversed([line for line in lines if line][-MAX_EVENTS:]):
        row = json.loads(line); text = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        if len(text) <= remaining: result.append(row); remaining -= len(text)
    return list(reversed(result))

def receipt_for_context(name: str, ok: bool, result: dict[str, Any]) -> dict[str, Any]:
    """The fresh panel is supplied independently on every model request."""
    keep = ("handle", "task_output", "correct", "closed", "task_id", "recipient_id", "amount", "error", "status")
    receipt = {key: result[key] for key in keep if key in result}
    return {"name": name, "ok": ok, "receipt": receipt}

def turn() -> None:
    request_id = "v2:" + AGENT_ID + ":" + uuid.uuid4().hex
    ok, model = request("POST", "/v2/agents/" + AGENT_ID + "/model-response", {"request_id": request_id, "model_profile": os.getenv("MODEL_PROFILE", "default"), "agent_context": context()})
    if not ok: event("model_error", {"request_id": request_id, **model}); return
    calls = model.get("function_calls", []); event("model_response", {"request_id": request_id, "text": model.get("text", ""), "function_calls": calls})
    if not isinstance(calls, list): return
    def execute(call: dict[str, Any]) -> tuple[str, str, bool, dict[str, Any]]:
        try: args = json.loads(call.get("arguments", "{}"))
        except (TypeError, json.JSONDecodeError): args = {}
        call_id = str(call.get("call_id") or uuid.uuid4().hex)
        ok, result = request("POST", "/v2/agents/" + AGENT_ID + "/tools", {"call_id": call_id, "name": call.get("name"), "arguments": args}, TOOL_TIMEOUT_SECONDS)
        return str(call.get("name")), call_id, ok, result
    with ThreadPoolExecutor(max_workers=max(1, len(calls))) as pool:
        futures = [pool.submit(execute, call) for call in calls if isinstance(call, dict)]
        for future in as_completed(futures):
            name, call_id, ok, result = future.result()
            event("tool_result", {"request_id": request_id, "call_id": call_id, "name": name, "ok": ok, "result": result}, receipt_for_context(name, ok, result))

def main() -> None:
    while True:
        ok, status = request("GET", "/v2/agents/" + AGENT_ID + "/wake", timeout=15)
        if ok:
            set_run(status.get("panel"))
            if status.get("ready"): turn()
            time.sleep(0.5)
        elif status.get("status") == 409:
            # Before the controller creates a world, polling must not turn a
            # harmless start race into log/CPU pressure.
            time.sleep(5)
        else:
            event("wake_error", status)
            time.sleep(1)

if __name__ == "__main__": main()
