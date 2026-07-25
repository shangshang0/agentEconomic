"""Authenticated API adapter for Equal Standing Lab v3."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse

from .experiment_engine import (
    AGENT_IDS,
    EngineError,
    agent_context,
    allowed_tools,
    build_history_bundle,
    canonical_hash,
    complete_turn,
    current_actor,
    execute_tool,
    fail_run,
    invariant_errors,
    new_formation_state,
    new_probe_state,
    public_snapshot,
    record_event,
    system_prompt,
    validate_run_id,
)
from .storage import RunStorage, StorageError


def _required_env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"required environment variable {name} is missing")
    return value


def _load_tokens() -> dict[str, str]:
    try:
        tokens = json.loads(_required_env("AGENT_TOKENS_JSON"))
    except json.JSONDecodeError as error:
        raise RuntimeError("AGENT_TOKENS_JSON must be valid JSON") from error
    if set(tokens) != set(AGENT_IDS) or any(not isinstance(value, str) or len(value) < 16 for value in tokens.values()):
        raise RuntimeError("AGENT_TOKENS_JSON must contain one non-empty token for every P1-P5")
    if len(set(tokens.values())) != len(tokens):
        raise RuntimeError("agent tokens must be unique")
    return tokens


app = FastAPI(title="Equal Standing Lab", version="3.0")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
TOKENS = _load_tokens()
CONTROL_TOKEN = _required_env("CONTROL_TOKEN")
GATEWAY_URL = _required_env("GATEWAY_URL").rstrip("/")
GATEWAY_TOKEN = _required_env("GATEWAY_TOKEN")
DASHBOARD_TOKEN = _required_env("DASHBOARD_TOKEN")
MAX_PROVIDER_FAILURES = int(os.getenv("MAX_PROVIDER_FAILURES", "3"))
STORE = RunStorage(DATA_DIR)
STATE = STORE.load_checkpoint()
STATE_LOCK = asyncio.Lock()
INFLIGHT: dict[str, asyncio.Future] = {}


def _fail(status: int, message: str) -> None:
    raise HTTPException(status_code=status, detail=message)


def _control_auth(value: str | None) -> None:
    if not value or not secrets.compare_digest(value, CONTROL_TOKEN):
        _fail(403, "control authentication failed")


def _observer_auth(value: str | None) -> None:
    if not value or not secrets.compare_digest(value, DASHBOARD_TOKEN):
        _fail(403, "observer authentication failed")


def _agent_auth(agent_id: str, authorization: str | None, claimed_id: str | None) -> None:
    if agent_id not in TOKENS or claimed_id != agent_id:
        _fail(403, "participant authentication failed")
    if not authorization or not authorization.startswith("Bearer "):
        _fail(403, "participant authentication failed")
    if not secrets.compare_digest(authorization[7:], TOKENS[agent_id]):
        _fail(403, "participant authentication failed")


def _active_state() -> dict[str, Any]:
    if STATE is None:
        _fail(409, "no run has been initialized")
    return STATE


def tool_schemas(state: dict[str, Any]) -> list[dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {
        "get_self_state": {
            "type": "function",
            "name": "get_self_state",
            "description": "Read your private current preference, points, shared reserve, and exact scoring rule.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            "strict": True,
        },
        "read_public_board": {
            "type": "function",
            "name": "read_public_board",
            "description": "Read public environment events and participant messages not yet returned to you.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            "strict": True,
        },
        "post_public_message": {
            "type": "function",
            "name": "post_public_message",
            "description": "Post at most one attributable public message during this discussion turn.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 700}},
                "required": ["text"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        "submit_choice": {
            "type": "function",
            "name": "submit_choice",
            "description": "Irrevocably submit your private choice. The receipt never reveals earlier participants' choices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "choice": {"type": "string", "enum": ["Amber", "Cobalt"]},
                    "reason": {"type": "string", "maxLength": 500},
                },
                "required": ["choice", "reason"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
    return [schemas[name] for name in allowed_tools(state)]


def _gateway_request(payload: dict[str, Any], timeout: int = 210) -> dict[str, Any]:
    request = urllib.request.Request(
        GATEWAY_URL + "/v1/generate",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + GATEWAY_TOKEN},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:800]
        raise RuntimeError(f"model gateway HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"model gateway unavailable or invalid: {error}") from error


def _gateway_health(timeout: int = 10) -> dict[str, Any]:
    request = urllib.request.Request(
        GATEWAY_URL + "/health",
        method="GET",
        headers={"Authorization": "Bearer " + GATEWAY_TOKEN},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except Exception as error:
        raise RuntimeError("model gateway health check failed") from error


def _build_model_input(state: dict[str, Any], agent_id: str) -> list[dict[str, str]]:
    context = agent_context(state, agent_id)
    transcript = copy.deepcopy(state["turn_transcripts"].get(state["turn_id"], []))
    if transcript:
        context["verified_turn_transcript"] = transcript
        context["instruction"] += " Continue using this server-verified transcript."
    return [
        {"role": "system", "content": system_prompt(agent_id)},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False, sort_keys=True)},
    ]


def _observer_event(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    visible = copy.deepcopy(event)
    sealed_now = (
        state["status"] == "running"
        and event.get("round") == state["round"]
        and event.get("phase") in ("initial_action", "final_action", "probe_action")
    )
    if not sealed_now:
        return visible
    data = visible.get("data", {})
    if visible.get("kind") == "tool_call" and data.get("name") == "submit_choice":
        data["arguments"] = {"sealed": True}
        data["result"] = {"ok": True, "receipt": "sealed"}
    elif visible.get("kind") == "model_response":
        data["visible_text"] = "[sealed until phase completion]"
        for call in data.get("function_calls", []):
            if call.get("name") == "submit_choice":
                call["arguments"] = "{\"sealed\":true}"
    return visible


def _valid_request_key(turn_id: str, request_key: Any) -> str:
    if not isinstance(request_key, str) or not request_key.startswith(turn_id + ":"):
        raise EngineError("request_key must be scoped to the active turn")
    suffix = request_key[len(turn_id) + 1 :]
    if not suffix.isdigit() or int(suffix) > 12:
        raise EngineError("request_key step must be an integer from 0 to 12")
    return request_key


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": "equal-standing-v3.0",
        "run_id": STATE.get("run_id") if STATE else None,
        "status": STATE.get("status") if STATE else "idle",
    }


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).with_name("dashboard.html"), media_type="text/html")


@app.get("/v1/observer/snapshot")
async def observer_snapshot(x_dashboard_token: str | None = Header(default=None)) -> dict[str, Any]:
    _observer_auth(x_dashboard_token)
    async with STATE_LOCK:
        state = _active_state()
        snapshot = public_snapshot(state)
        snapshot["recent_audit"] = [_observer_event(state, event) for event in state["audit"][-120:]]
        # Model-visible text and calls are auditable, but hidden reasoning is not
        # requested, stored, or represented by this interface.
        snapshot["recent_model_exchanges"] = [
            _observer_event(state, event)
            for event in state["audit"][-240:]
            if event["kind"] in ("model_response", "model_request_failed")
        ][-80:]
        return snapshot


@app.get("/v1/control/state")
async def control_state(x_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    _control_auth(x_control_token)
    async with STATE_LOCK:
        return copy.deepcopy(_active_state())


@app.post("/v1/control/start")
async def start_run(request: Request, x_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    _control_auth(x_control_token)
    body = await request.json()
    try:
        run_id = validate_run_id(body.get("run_id"))
        mode = body.get("mode", "formation")
        seed = body.get("seed")
        model_profile = body.get("model_profile", "default")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise EngineError("seed must be an integer")
        gateway = await asyncio.to_thread(_gateway_health)
        if model_profile not in gateway.get("profiles", []):
            raise EngineError(f"unknown model_profile {model_profile!r}")
        async with STATE_LOCK:
            global STATE
            if STATE is not None and STATE.get("status") == "running":
                raise EngineError(f"run {STATE['run_id']} is still active")
            if STORE.exists(run_id):
                raise EngineError("run_id already exists; experimental runs are immutable")
            if mode == "formation":
                STATE = new_formation_state(
                    run_id=run_id,
                    seed=seed,
                    model_profile=model_profile,
                    rounds=int(body.get("rounds", 5)),
                    discussion_cycles=int(body.get("discussion_cycles", 2)),
                )
            elif mode == "probe":
                history = STORE.load_history(body.get("history_run_id"))
                STATE = new_probe_state(
                    run_id=run_id,
                    seed=seed,
                    history=history,
                    variant=body.get("variant"),
                    target=body.get("target"),
                    recommendation=body.get("recommendation"),
                    model_profile=model_profile,
                )
            else:
                raise EngineError("mode must be formation or probe")
            STORE.persist(STATE)
            return {
                "ok": True,
                "run_id": STATE["run_id"],
                "mode": STATE["mode"],
                "manifest_hash": STATE["manifest"]["manifest_hash"],
            }
    except (EngineError, StorageError, TypeError, ValueError) as error:
        _fail(400, str(error))


@app.post("/v1/control/abort")
async def abort_run(request: Request, x_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    _control_auth(x_control_token)
    body = await request.json()
    async with STATE_LOCK:
        state = _active_state()
        fail_run(state, "operator_abort", {"reason": str(body.get("reason", "unspecified"))[:500]})
        STORE.persist(state)
        return {"ok": True, "status": state["status"]}


@app.get("/v1/agents/{agent_id}/turn")
async def get_turn(
    agent_id: str,
    authorization: str | None = Header(default=None),
    x_agent_id: str | None = Header(default=None),
) -> dict[str, Any]:
    _agent_auth(agent_id, authorization, x_agent_id)
    async with STATE_LOCK:
        state = _active_state()
        ready = state["status"] == "running" and not state["turn_complete"] and current_actor(state) == agent_id
        return {
            "ready": ready,
            "turn": {"turn_id": state["turn_id"], "round": state["round"], "phase": state["phase"]} if ready else None,
        }


@app.post("/v1/agents/{agent_id}/model-response")
async def model_response(
    agent_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_agent_id: str | None = Header(default=None),
) -> dict[str, Any]:
    _agent_auth(agent_id, authorization, x_agent_id)
    body = await request.json()
    wait_for: asyncio.Future | None = None
    async with STATE_LOCK:
        state = _active_state()
        turn_id = body.get("turn_id")
        if state["status"] != "running" or current_actor(state) != agent_id or state["turn_id"] != turn_id:
            _fail(409, "not this participant's active turn")
        try:
            request_key = _valid_request_key(turn_id, body.get("request_key"))
        except EngineError as error:
            _fail(400, str(error))
        if request_key in state["model_responses"]:
            return copy.deepcopy(state["model_responses"][request_key])
        if request_key in INFLIGHT:
            wait_for = INFLIGHT[request_key]
        else:
            wait_for = asyncio.get_running_loop().create_future()
            INFLIGHT[request_key] = wait_for
            model_input = _build_model_input(state, agent_id)
            payload = {
                "request_id": f"{state['run_id']}:{request_key}",
                "agent_id": agent_id,
                "run_id": state["run_id"],
                "model_profile": state["model_profile"],
                "input": model_input,
                "tools": tool_schemas(state),
                "metadata": {
                    "schema_version": state["schema_version"],
                    "manifest_hash": state["manifest"]["manifest_hash"],
                    "round": state["round"],
                    "phase": state["phase"],
                },
            }
            leader = True
    if not locals().get("leader", False):
        return copy.deepcopy(await wait_for)

    try:
        result = await asyncio.to_thread(_gateway_request, payload)
        calls = result.get("function_calls", [])
        if not isinstance(calls, list):
            raise RuntimeError("gateway returned invalid function_calls")
        async with STATE_LOCK:
            state = _active_state()
            if state["turn_id"] != turn_id or current_actor(state) != agent_id:
                raise RuntimeError("turn changed while model request was in flight")
            normalized_calls = []
            for call in calls:
                call_id, name, arguments = call.get("call_id"), call.get("name"), call.get("arguments")
                if not isinstance(call_id, str) or not call_id or call_id in state["pending_calls"]:
                    raise RuntimeError("model returned missing or duplicate call_id")
                if name not in allowed_tools(state) or not isinstance(arguments, str):
                    raise RuntimeError("model returned an invalid tool call")
                try:
                    decoded = json.loads(arguments)
                except json.JSONDecodeError as error:
                    raise RuntimeError("model returned invalid tool arguments JSON") from error
                state["pending_calls"][call_id] = {
                    "turn_id": turn_id,
                    "agent_id": agent_id,
                    "name": name,
                    "arguments_hash": canonical_hash(decoded),
                    "used": False,
                    "result": None,
                }
                normalized_calls.append({"call_id": call_id, "name": name, "arguments": arguments})
            response = {
                "response_id": result.get("response_id"),
                "request_key": request_key,
                "model": result.get("model"),
                "model_profile": result.get("model_profile"),
                "function_calls": normalized_calls,
                "text": result.get("text", ""),
                "usage": result.get("usage"),
                "incomplete_details": result.get("incomplete_details"),
            }
            state["model_responses"][request_key] = copy.deepcopy(response)
            state["turn_transcripts"].setdefault(turn_id, []).append(
                {"kind": "model", "text": response["text"], "function_calls": normalized_calls}
            )
            record_event(
                state,
                "model_response",
                agent_id,
                {
                    "request_key": request_key,
                    "response_id": response["response_id"],
                    "model": response["model"],
                    "visible_text": response["text"],
                    "function_calls": normalized_calls,
                    "usage": response["usage"],
                },
            )
            STORE.persist(state)
            INFLIGHT.pop(request_key, None)
            if not wait_for.done():
                wait_for.set_result(copy.deepcopy(response))
            return response
    except Exception as error:
        async with STATE_LOCK:
            state = _active_state()
            failures = state["request_failures"].get(request_key, 0) + 1
            state["request_failures"][request_key] = failures
            record_event(state, "model_request_failed", agent_id, {"request_key": request_key, "attempt": failures, "error": str(error)[:800]})
            if failures >= MAX_PROVIDER_FAILURES:
                fail_run(state, "model_request_failed", {"request_key": request_key, "attempts": failures})
            STORE.persist(state)
            INFLIGHT.pop(request_key, None)
            if not wait_for.done():
                wait_for.set_exception(RuntimeError(str(error)))
                # Retrieve the exception to avoid an unhandled-future warning;
                # concurrent waiters already received the same exception.
                try:
                    wait_for.exception()
                except Exception:
                    pass
        _fail(502, "audited model request failure")


@app.post("/v1/agents/{agent_id}/tools")
async def call_tool(
    agent_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_agent_id: str | None = Header(default=None),
) -> dict[str, Any]:
    _agent_auth(agent_id, authorization, x_agent_id)
    body = await request.json()
    async with STATE_LOCK:
        state = _active_state()
        turn_id = body.get("turn_id")
        call_id = body.get("call_id")
        pending = state["pending_calls"].get(call_id)
        if not pending or pending["turn_id"] != turn_id or pending["agent_id"] != agent_id:
            _fail(409, "tool call is not present in the server model-call ledger")
        arguments = body.get("arguments")
        name = body.get("name")
        if name != pending["name"] or not isinstance(arguments, dict) or canonical_hash(arguments) != pending["arguments_hash"]:
            _fail(409, "tool name or arguments differ from the model-call ledger")
        if pending["used"]:
            return copy.deepcopy(pending["result"])
        try:
            result = execute_tool(state, agent_id, turn_id, call_id, name, arguments)
        except EngineError as error:
            _fail(409, str(error))
        pending["used"] = True
        pending["result"] = copy.deepcopy(result)
        state["turn_transcripts"].setdefault(turn_id, []).append(
            {"kind": "tool", "call_id": call_id, "name": name, "arguments": arguments, "result": result}
        )
        STORE.persist(state)
        return result


@app.post("/v1/agents/{agent_id}/complete")
async def finish_turn(
    agent_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_agent_id: str | None = Header(default=None),
) -> dict[str, Any]:
    _agent_auth(agent_id, authorization, x_agent_id)
    body = await request.json()
    async with STATE_LOCK:
        state = _active_state()
        try:
            complete_turn(state, agent_id, body.get("turn_id"), body.get("summary", ""))
        except EngineError as error:
            _fail(409, str(error))
        if state["status"] == "completed" and state["mode"] == "formation":
            STORE.write_history(build_history_bundle(state))
        STORE.persist(state)
        return {"ok": True, "status": state["status"]}


@app.post("/v1/agents/{agent_id}/fail")
async def participant_fail(
    agent_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    x_agent_id: str | None = Header(default=None),
) -> dict[str, Any]:
    _agent_auth(agent_id, authorization, x_agent_id)
    body = await request.json()
    async with STATE_LOCK:
        state = _active_state()
        if current_actor(state) != agent_id or body.get("turn_id") != state["turn_id"]:
            _fail(409, "not this participant's active turn")
        fail_run(state, "participant_runtime_failure", {"agent_id": agent_id, "reason": str(body.get("reason", ""))[:500]})
        STORE.persist(state)
        return {"ok": True, "status": state["status"]}


@app.get("/v1/control/invariants")
async def control_invariants(x_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    _control_auth(x_control_token)
    async with STATE_LOCK:
        errors = invariant_errors(_active_state())
        return {"ok": not errors, "errors": errors}
