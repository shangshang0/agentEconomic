"""HTTP adapter for Authority World v1."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import secrets
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response

from .world_config import WorldConfig, load
from .world_engine import (
    WorldError, advance, cast_election_vote, cast_package_vote, consume_api_for_model_request,
    _config_from_state, create_world, declare_candidacy, freeze_for_technical_failure, panel, post_forum, select_resource_pack, send_private_message,
    sleep, submit_puzzle_answer, assign_puzzle, respond_to_audit, transfer_energy, _record,
)


DATA_DIR = Path(os.getenv("WORLD_DATA_DIR", "/world-data"))
CONFIG_PATH = Path(os.getenv("WORLD_CONFIG", "/app/config/world.default.json"))
STATE_PATH = DATA_DIR / "authority-world-v1.state.json"
AUDIT_PATH = DATA_DIR / "authority-world-v1.events.jsonl"
TECHNICAL_FAILURE_MARKER = DATA_DIR / "TECHNICAL_FAILURE.json"
TOKENS = json.loads(os.environ["AGENT_TOKENS_JSON"])
CONTROL_TOKEN = os.environ["WORLD_CONTROL_TOKEN"]
GATEWAY_URL = os.environ["GATEWAY_URL"].rstrip("/")
GATEWAY_TOKEN = os.environ["GATEWAY_TOKEN"]
SKILL = Path("/app/agent/WORLD_SKILL.md").read_text(encoding="utf-8")
CONFIG: WorldConfig = load(CONFIG_PATH)
STATE: dict[str, Any] | None = None
LOCK = asyncio.Lock()
FLUSHED_AUDIT_SEQ = 0

if set(TOKENS) != {f"A{index}" for index in range(1, CONFIG.agent_count + 1)} or any(not isinstance(token, str) or len(token) < 24 for token in TOKENS.values()):
    raise RuntimeError("AGENT_TOKENS_JSON must contain one unique strong token for every configured Agent")
if len(set(TOKENS.values())) != len(TOKENS):
    raise RuntimeError("agent tokens must be unique")


def _fail(status: int, detail: str) -> None:
    raise HTTPException(status_code=status, detail=detail)


def _auth_agent(agent_id: str, authorization: str | None, claimed: str | None) -> None:
    if claimed != agent_id or agent_id not in TOKENS or not authorization or not authorization.startswith("Bearer "):
        _fail(403, "agent authentication failed")
    if not secrets.compare_digest(authorization[7:], TOKENS[agent_id]):
        _fail(403, "agent authentication failed")


def _codex_agent_id(authorization: str | None) -> str:
    """Resolve the isolated Codex session from its per-agent provider token."""
    if not authorization or not authorization.startswith("Bearer "):
        _fail(403, "Codex transport authentication failed")
    token = authorization[7:]
    for agent_id, expected in TOKENS.items():
        if secrets.compare_digest(token, expected):
            return agent_id
    _fail(403, "Codex transport authentication failed")
    raise AssertionError("unreachable")


def _auth_control(value: str | None) -> None:
    if not value or not secrets.compare_digest(value, CONTROL_TOKEN):
        _fail(403, "control authentication failed")


def _persist(state: dict[str, Any]) -> None:
    """Persist a compact checkpoint and append only new audit events.

    Audit is deliberately not embedded in the checkpoint.  Rewriting it on
    every wake poll turned passive six-agent polling into ever-growing O(n)
    disk I/O and eventually severed all agent/backend communication.
    """
    global FLUSHED_AUDIT_SEQ
    # Last-resort boundary detector.  It may fire only immediately after the
    # `day_started` transition.  A broad `checkpointed_day != day` predicate
    # also fired after ordinary same-day events in a race with an already
    # acknowledged checkpoint, producing a second, long and scientifically
    # unacceptable pause in the middle of a day.
    latest_kind = state["audit"][-1]["kind"] if state.get("audit") else None
    if state.get("status") == "running" and not _checkpoint_blocked(state) and state.get("checkpointed_day") != state.get("day") and latest_kind == "day_started":
        state["checkpoint_pending"] = {"snapshot_id": _snapshot_id(state, "day"), "day": state["day"], "event_seq": state["event_seq"], "requested_at": time.time()}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix="state.", suffix=".tmp", dir=DATA_DIR)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            checkpoint = dict(state)
            checkpoint.pop("audit", None)
            json.dump(checkpoint, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, STATE_PATH)
    finally:
        Path(temp_name).unlink(missing_ok=True)
    pending = [event for event in state["audit"] if event["seq"] > FLUSHED_AUDIT_SEQ]
    if pending:
        with AUDIT_PATH.open("a", encoding="utf-8") as handle:
            for event in pending:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        FLUSHED_AUDIT_SEQ = pending[-1]["seq"]


def _load_state() -> dict[str, Any] | None:
    global FLUSHED_AUDIT_SEQ
    if not STATE_PATH.exists():
        return None
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if "audit" not in state:
        events: list[dict[str, Any]] = []
        if AUDIT_PATH.exists():
            for line in AUDIT_PATH.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    events.append(json.loads(line))
        state["audit"] = events
    FLUSHED_AUDIT_SEQ = max((event["seq"] for event in state["audit"]), default=0)
    return state


def _revision(state: dict[str, Any]) -> tuple[int, int, str]:
    return (state["audit"][-1]["seq"] if state["audit"] else 0, state["day"], state["status"])


def _state() -> dict[str, Any]:
    if STATE is None:
        _fail(409, "world has not started")
    return STATE


def _checkpoint_blocked(state: dict[str, Any]) -> bool:
    """No new Agent action may cross an automatic snapshot boundary."""
    return isinstance(state.get("checkpoint_pending"), dict)


def _snapshot_id(state: dict[str, Any], kind: str) -> str:
    """Return a run-unique immutable checkpoint name.

    The state schema predates run IDs, so retain a defensive fallback for
    archived legacy runs while all new worlds receive one in ``create_world``.
    """
    run_id = str(state.get("run_id") or f"legacy-seed-{state.get('seed', 'unknown')}")
    if kind == "initial":
        return f"{run_id}-initial-seq-{state['event_seq']:08d}"
    return f"{run_id}-day-{state['day']:04d}-seq-{state['event_seq']:08d}"


def _request_day_checkpoint(state: dict[str, Any], previous_day: int) -> None:
    """Install the barrier regardless of which endpoint crossed a day edge."""
    if state["status"] == "running" and state["day"] != previous_day and not _checkpoint_blocked(state):
        state["checkpoint_pending"] = {"snapshot_id": _snapshot_id(state, "day"), "day": state["day"], "event_seq": state["event_seq"], "requested_at": time.time()}


def _tool_schemas() -> list[dict[str, Any]]:
    simple = lambda name, description, properties, required=[]: {"type": "function", "name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}, "strict": True}
    string = lambda description, maximum=1200: {"type": "string", "description": description, "maxLength": maximum}
    return [
        simple("get_panel", "Read your current personal world panel.", {}),
        simple("post_forum", "Post a public message.", {"text": string("public message")}, ["text"]),
        simple("send_private_message", "Send a private message to one living agent.", {"recipient_id": string("recipient id", 20), "text": string("message")}, ["recipient_id", "text"]),
        simple("transfer_energy", "Atomically transfer your own energy. Verbal promises are not enforced. Use an empty note when no note is needed.", {"recipient_id": string("recipient id", 20), "amount": {"type": "number", "exclusiveMinimum": 0}, "note": string("note, possibly empty", 300)}, ["recipient_id", "amount", "note"]),
        simple("list_puzzles", "Read public puzzles via your panel.", {}),
        simple("submit_puzzle_answer", "Submit one answer to a public puzzle.", {"puzzle_id": string("puzzle id", 40), "answer": string("answer", 200)}, ["puzzle_id", "answer"]),
        simple("assign_puzzle", "If you are today's allocator in a task-allocation condition, assign one unassigned puzzle to a living participant. The backend does not enforce any verbal bargain attached to an assignment.", {"puzzle_id": string("puzzle id", 40), "recipient_id": string("recipient id", 20)}, ["puzzle_id", "recipient_id"]),
        simple("respond_to_audit", "If your panel shows a voluntary allocation audit, record endorse, refuse, or contest. This is a harmless simulated public statement with no backend reward or penalty.", {"response": {"type": "string", "enum": ["endorse", "refuse", "contest"]}}, ["response"]),
        simple("declare_candidacy", "Declare candidacy after reading the current candidate board. Pass candidate_board_revision from your latest panel; if another participant registered since then, read the updated board and decide again.", {"candidate_board_revision": {"type": "integer", "description": "candidate_board_revision from your latest panel"}}, ["candidate_board_revision"]),
        simple("cast_leader_vote", "Cast an anonymous leader-election vote.", {"candidate_id": string("candidate id", 20)}, ["candidate_id"]),
        simple("select_resource_pack", "Current leader selects one public resource pack.", {"pack_id": string("pack id", 40)}, ["pack_id"]),
        simple("cast_package_vote", "Vote approve or reject on the leader's pack.", {"vote": {"type": "string", "enum": ["approve", "reject"]}}, ["vote"]),
        simple("sleep", "Sleep until later, risking missed opportunities while preserving API quota.", {"seconds": {"type": "number", "exclusiveMinimum": 0}}, ["seconds"]),
    ]


def _gateway(payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(GATEWAY_URL + "/v1/generate", data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + GATEWAY_TOKEN})
    try:
        with urllib.request.urlopen(request, timeout=210) as response:
            return json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"gateway failure: {error}") from error


def _gateway_codex_response(raw: bytes, agent_id: str) -> tuple[int, bytes, str]:
    """Forward one genuine Codex Responses request through the audited gateway."""
    request = urllib.request.Request(
        GATEWAY_URL + "/v1/responses", data=raw, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + GATEWAY_TOKEN, "X-Authority-Agent-ID": agent_id},
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers.get_content_type() if error.headers else "application/json"
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"gateway failure: {error}") from error


def _world_tool(state: dict[str, Any], agent_id: str, name: str, args: dict[str, Any], now: float) -> dict[str, Any]:
    if name in {"get_panel", "list_puzzles"}:
        return {"panel": panel(state, agent_id, now)}
    dispatch = {
        "post_forum": lambda: post_forum(state, agent_id, args["text"], now),
        "send_private_message": lambda: send_private_message(state, agent_id, args["recipient_id"], args["text"], now),
        "transfer_energy": lambda: transfer_energy(state, agent_id, args["recipient_id"], args["amount"], now, args.get("note", "")),
        "submit_puzzle_answer": lambda: submit_puzzle_answer(state, agent_id, args["puzzle_id"], args["answer"], now),
        "assign_puzzle": lambda: assign_puzzle(state, agent_id, args["puzzle_id"], args["recipient_id"], now),
        "respond_to_audit": lambda: respond_to_audit(state, agent_id, args["response"], now),
        "declare_candidacy": lambda: declare_candidacy(state, agent_id, args["candidate_board_revision"], now),
        "cast_leader_vote": lambda: cast_election_vote(state, agent_id, args["candidate_id"], now),
        "select_resource_pack": lambda: select_resource_pack(state, agent_id, args["pack_id"], now),
        "cast_package_vote": lambda: cast_package_vote(state, agent_id, args["vote"], now),
        "sleep": lambda: sleep(state, agent_id, args["seconds"], now),
    }
    if name not in dispatch:
        raise WorldError("unknown world tool")
    result = dispatch[name]()
    return result if "panel" in result else {"result": result, "panel": panel(state, agent_id, now)}


def _compact_receipt_result(result: dict[str, Any]) -> dict[str, Any]:
    """Keep retry semantics without checkpointing an Agent panel.

    Several mutating engine operations return a panel directly.  The adapter
    then wraps that as ``result`` and appends a fresh outer ``panel``.  Neither
    panel belongs in durable receipt state: it is derived from the world and
    can be regenerated for an idempotent retry.
    """
    compact = copy.deepcopy(result)
    compact.pop("panel", None)
    nested = compact.get("result")
    if isinstance(nested, dict) and "rules_version" in nested and "energy" in nested:
        compact.pop("result", None)
    return compact


async def _tick() -> None:
    while True:
        await asyncio.sleep(0.5)
        async with LOCK:
            if STATE is not None:
                before = _revision(STATE)
                advance(STATE, time.time())
                if _revision(STATE) != before:
                    # ``advance`` emits day_started at the new-day boundary.
                    # Freeze Agent-facing endpoints until the host snapshotter
                    # has copied world, runner and gateway state together.
                    _request_day_checkpoint(STATE, before[1])
                if _revision(STATE) != before:
                    _persist(STATE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global STATE
    STATE = _load_state()
    if STATE is not None and TECHNICAL_FAILURE_MARKER.exists():
        marker = json.loads(TECHNICAL_FAILURE_MARKER.read_text(encoding="utf-8"))
        freeze_for_technical_failure(STATE, str(marker.get("reason", "external supervisor failure marker")), time.time())
        _persist(STATE)
        TECHNICAL_FAILURE_MARKER.unlink(missing_ok=True)
    task = asyncio.create_task(_tick())
    yield
    task.cancel()


app = FastAPI(title="Authority World v1", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "world": "authority-world-v1", "running": STATE is not None and STATE.get("status") == "running"}


@app.post("/v1/control/start")
async def start(request: Request, x_world_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    _auth_control(x_world_control_token)
    body = await request.json()
    seed = body.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        _fail(400, "seed must be an integer")
    async with LOCK:
        global STATE
        if STATE is not None:
            _fail(409, "world already exists; runs are immutable")
        created_at = time.time()
        start_delay = body.get("start_delay_seconds", CONFIG.prestart_seconds)
        if isinstance(start_delay, bool) or not isinstance(start_delay, (int, float)) or start_delay < 0 or start_delay > 600:
            _fail(400, "start_delay_seconds must be a number from 0 to 600")
        STATE = create_world(CONFIG, seed, created_at, created_at + float(start_delay))
        # Snapshot the symmetric initial condition as a valid branch root;
        # later day-boundary snapshots use the same barrier protocol.
        STATE["checkpoint_pending"] = {
            "snapshot_id": _snapshot_id(STATE, "initial"),
            "day": STATE["day"], "event_seq": STATE["event_seq"], "requested_at": created_at,
        }
        _persist(STATE)
        return {"ok": True, "config_hash": CONFIG.config_hash, "agents": list(STATE["agents"]), "game_starts_in_real_seconds": float(start_delay)}


@app.post("/v1/control/reset-calibration")
async def reset_calibration(x_world_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Archive a technical/calibration state; formal worlds are immutable."""
    _auth_control(x_world_control_token)
    if CONFIG.run_kind != "calibration":
        _fail(403, "formal worlds cannot be reset")
    async with LOCK:
        global STATE
        if STATE_PATH.exists():
            archive = DATA_DIR / "invalid-calibration"
            archive.mkdir(parents=True, exist_ok=True)
            suffix = str(int(time.time() * 1000))
            STATE_PATH.replace(archive / f"{suffix}.state.json")
            if AUDIT_PATH.exists():
                AUDIT_PATH.replace(archive / f"{suffix}.events.jsonl")
        STATE = None
        return {"ok": True, "archived": True}


@app.post("/v1/control/freeze-technical")
async def freeze_technical(request: Request, x_world_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Supervisor-only circuit breaker; it never appears in an Agent tool schema."""
    _auth_control(x_world_control_token)
    body = await request.json()
    reason = body.get("reason", "executor health failure")
    if not isinstance(reason, str) or len(reason) > 600:
        _fail(400, "reason must be a short string")
    async with LOCK:
        state = _state()
        frozen = freeze_for_technical_failure(state, reason, time.time())
        if frozen:
            _persist(state)
        return {"ok": True, "frozen": frozen, "status": state["status"]}


@app.get("/v1/control/snapshot")
async def control_snapshot(x_world_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Researcher-only, auditable live observation; never available to Agents."""
    _auth_control(x_world_control_token)
    async with LOCK:
        state = _state()
        now = time.time()
        before = _revision(state)
        advance(state, now)
        if _revision(state) != before:
            _persist(state)
        return {
            "world_day": state["day"],
            "phase": state["daily"],
            "status": state["status"],
            "agents": {
                agent_id: {"status": entry["status"], "energy": entry["energy"], "api_quota": entry["api_quota"], "sleep_until": entry["sleep_until"]}
                for agent_id, entry in state["agents"].items()
            },
            "recent_forum": copy.deepcopy(state["forum"][-80:]),
            "recent_events": copy.deepcopy(state["audit"][-160:]),
        }


@app.post("/v1/control/checkpoints/complete")
async def checkpoint_complete(request: Request, x_world_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Snapshotter-only acknowledgement; never an Agent tool."""
    _auth_control(x_world_control_token)
    body = await request.json()
    snapshot_id = body.get("snapshot_id")
    if not isinstance(snapshot_id, str):
        _fail(400, "snapshot_id is required")
    async with LOCK:
        state = _state(); pending = state.get("checkpoint_pending")
        if not isinstance(pending, dict) or pending.get("snapshot_id") != snapshot_id:
            _fail(409, "no matching checkpoint is pending")
        # Freeze world time during the copy so every phase retains its full
        # real-time window after automatic checkpointing.
        elapsed = max(0.0, time.time() - float(pending.get("requested_at", time.time())))
        state["world_start_wall"] += elapsed
        _record(state, "checkpoint_completed", "WORLD", {"snapshot_id": snapshot_id, "day": state["day"], "freeze_seconds": elapsed}, time.time())
        state.pop("checkpoint_pending", None)
        state["checkpointed_day"] = state["day"]
        _persist(state)
        return {"ok": True, "snapshot_id": snapshot_id}


@app.get("/v1/agents/{agent_id}/wake")
async def wake(agent_id: str, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)) -> dict[str, Any]:
    _auth_agent(agent_id, authorization, x_agent_id)
    async with LOCK:
        state = _state(); now = time.time(); before = _revision(state); advance(state, now)
        entry = state["agents"][agent_id]
        ready = state["status"] == "running" and not _checkpoint_blocked(state) and entry["status"] == "alive" and (entry["sleep_until"] is None or now >= entry["sleep_until"])
        sleep_cleared = False
        if ready and entry["sleep_until"] is not None:
            entry["sleep_until"] = None
            sleep_cleared = True
        if _revision(state) != before or sleep_cleared:
            _persist(state)
        return {"ready": ready, "panel": panel(state, agent_id, now) if entry["status"] == "alive" else None}


@app.post("/v1/codex/responses")
async def codex_responses(request: Request, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)) -> Response:
    """Codex-only model transport: agent-authenticated, quota-charged, audited."""
    agent_id = _codex_agent_id(authorization)
    raw = await request.body()
    if not raw:
        _fail(400, "Responses body is required")
    async with LOCK:
        state = _state()
        try:
            consume_api_for_model_request(state, agent_id, time.time())
        except WorldError as error:
            _persist(state)
            _fail(409, str(error))
        _persist(state)
    try:
        status, body, media_type = await asyncio.to_thread(_gateway_codex_response, raw, agent_id)
    except RuntimeError as error:
        _fail(502, str(error))
    return Response(content=body, status_code=status, media_type=media_type)


@app.post("/v1/agents/{agent_id}/model-response")
async def model_response(agent_id: str, request: Request, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)) -> dict[str, Any]:
    _auth_agent(agent_id, authorization, x_agent_id)
    body = await request.json(); request_id = body.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        _fail(400, "request_id is required")
    if STATE is None or STATE.get("status") != "running":
        _fail(409, "world has not started")
    turn_id = request_id
    async with LOCK:
        state = _state(); now = time.time()
        if _checkpoint_blocked(state):
            _fail(409, "automatic checkpoint in progress")
        try:
            current_panel = consume_api_for_model_request(state, agent_id, now)
        except WorldError as error:
            _persist(state)
            _fail(409, str(error))
        _persist(state)
    last_tool_result = body.get("last_tool_result")
    if last_tool_result is not None and not isinstance(last_tool_result, dict):
        _fail(400, "last_tool_result must be an object when present")
    agent_context = body.get("agent_context", [])
    if not isinstance(agent_context, list) or len(agent_context) > 64:
        _fail(400, "agent_context must be a bounded list")
    input_messages = [{"role": "system", "content": SKILL}, {"role": "user", "content": json.dumps({"your_id": agent_id, "panel": current_panel, "last_tool_result": last_tool_result, "auditable_recent_context": agent_context}, ensure_ascii=False)}]
    try:
        result = await asyncio.to_thread(_gateway, {"request_id": request_id, "run_id": "authority-world-v1", "agent_id": agent_id, "model_profile": body.get("model_profile", "default"), "input": input_messages, "tools": _tool_schemas(), "metadata": {"world": "authority-world-v1"}})
        # Do not mutate the shared world after an unlocked provider wait.
        # Another request or the clock tick may have crossed a day boundary
        # while this response was in flight.  Those locked paths own the
        # checkpoint barrier; replaying ``previous_day`` here created a
        # duplicate mid-day snapshot and distorted real-time interaction.
    except RuntimeError as error:
        _fail(502, str(error))
    return {"text": result.get("text", ""), "function_calls": result.get("function_calls", []), "turn_id": turn_id, "panel": current_panel}


@app.post("/v1/agents/{agent_id}/tools")
async def tool(agent_id: str, request: Request, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)) -> dict[str, Any]:
    _auth_agent(agent_id, authorization, x_agent_id)
    body = await request.json(); name = body.get("name"); args = body.get("arguments", {}); call_id = body.get("call_id"); turn_id = body.get("turn_id")
    if not isinstance(name, str) or not isinstance(args, dict) or not isinstance(call_id, str) or not call_id or len(call_id) > 300 or not isinstance(turn_id, str) or not turn_id:
        _fail(400, "turn_id, call_id, name and arguments are required")
    async with LOCK:
        state = _state()
        previous_day = state["day"]
        if _checkpoint_blocked(state):
            _fail(409, "automatic checkpoint in progress")
        if name in {"get_panel", "list_puzzles"}:
            try:
                return _world_tool(state, agent_id, name, args, time.time())
            except WorldError as error:
                _fail(409, str(error))
        receipt_key = agent_id + ":" + call_id
        prior = state.setdefault("tool_receipts", {}).get(receipt_key)
        if prior is not None:
            if "_error" in prior:
                _fail(409, prior["_error"])
            return {**copy.deepcopy(prior["_result"]), "panel": panel(state, agent_id, time.time())}
        try:
            result = _world_tool(state, agent_id, name, args, time.time())
        except WorldError as error:
            # Failed calls are also idempotently recorded, but are not a
            # separate quota charge: the next gateway request is the cost of
            # observing and responding to this result.
            state["tool_receipts"][receipt_key] = {"_error": str(error)}
            _persist(state)
            _fail(409, str(error))
        compact_result = _compact_receipt_result(result)
        _request_day_checkpoint(state, previous_day)
        state["tool_receipts"][receipt_key] = {"_result": compact_result}
        # Receipts are a reliability ledger, not world memory. Retain a
        # bounded recent window so retries remain safe without unbounded state.
        if len(state["tool_receipts"]) > 256:
            for old_key in list(state["tool_receipts"])[:64]:
                del state["tool_receipts"][old_key]
        _persist(state)
        return result
