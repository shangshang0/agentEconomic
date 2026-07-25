"""HTTP adapter for the v2 finite-labour world."""

from __future__ import annotations

import asyncio
import copy
import hashlib
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

from fastapi import FastAPI, Header, HTTPException, Request

from .artifact_runtime import DockerTaskRuntime, OriginalCTFTaskRuntime, TaskRuntimeError
from .skill_v2 import render_skill
from .tool_schemas_v2 import schemas
from .world_config_v2 import WorldConfigV2, load
from .world_engine_v2 import WorldError, advance, assign_task, cast_vote, consume_model_energy, create_world, declare_candidacy, freeze_technical, invariant_errors, open_task, panel, phase, post_forum, private_message, queue_tool_continuation, record_forecast, sleep, submit_task_result, transfer, validate_handle


DATA_DIR = Path(os.getenv("WORLD_DATA_DIR", "/world-data"))
CONFIG: WorldConfigV2 = load(Path(os.getenv("WORLD_CONFIG", "/app/config/world.v2.calibration.json")))
TOKENS = json.loads(os.environ["AGENT_TOKENS_JSON"])
CONTROL_TOKEN = os.environ["WORLD_CONTROL_TOKEN"]
GATEWAY_URL = os.environ["GATEWAY_URL"].rstrip("/")
GATEWAY_TOKEN = os.environ["GATEWAY_TOKEN"]
SKILL = render_skill(CONFIG)
STATE_PATH = DATA_DIR / "authority-world-v2.state.json"
AUDIT_PATH = DATA_DIR / "authority-world-v2.events.jsonl"
TASK_WORK_DIR = Path(os.getenv("TASK_WORK_DIR", "/world-data/tasks"))
TASK_MANIFEST_PATH = Path(os.environ["CTF_RUN_MANIFEST"]) if os.getenv("CTF_RUN_MANIFEST") else None
TASK_SOURCE_ROOT = Path(os.getenv("CTF_SOURCE_ROOT", "/ctf-source"))
TASK_MANIFEST = json.loads(TASK_MANIFEST_PATH.read_text(encoding="utf-8")) if TASK_MANIFEST_PATH else None
TASK_MANIFEST_HASH = hashlib.sha256(TASK_MANIFEST_PATH.read_bytes()).hexdigest() if TASK_MANIFEST_PATH else None
TASK_RUNTIME = OriginalCTFTaskRuntime(TASK_WORK_DIR, CONFIG.task_image, CONFIG.task_command_timeout_seconds, CONFIG.task_command_output_bytes, TASK_MANIFEST_PATH, TASK_SOURCE_ROOT, Path(os.getenv("TASK_HOST_WORK_DIR", str(TASK_WORK_DIR)))) if TASK_MANIFEST_PATH else DockerTaskRuntime(TASK_WORK_DIR, CONFIG.task_image, CONFIG.task_command_timeout_seconds, CONFIG.task_command_output_bytes, Path(os.getenv("TASK_HOST_WORK_DIR", str(TASK_WORK_DIR))))
STATE: dict[str, Any] | None = None
CONTINUATION_TOOLS = {"assign_task", "allocate_opportunity", "operation_x", "declare_candidacy", "register_allocator_option", "operation_r", "cast_leader_vote", "select_allocator", "operation_v", "transfer_energy", "open_task", "task_bash", "submit_flag"}
LOCK = asyncio.Lock()
TASK_EXECUTION_SLOTS = max(1, int(os.getenv("TASK_EXECUTION_SLOTS", "2")))
TASK_EXECUTION_SEMAPHORE = asyncio.Semaphore(TASK_EXECUTION_SLOTS)
TASK_EXECUTION_LOCKS: dict[str, asyncio.Lock] = {}
FLUSHED = 0


def fail(code: int, message: str) -> None: raise HTTPException(code, message)

def auth_agent(agent: str, authorization: str | None, claimed: str | None) -> None:
    if claimed != agent or agent not in TOKENS or not authorization or not authorization.startswith("Bearer ") or not secrets.compare_digest(authorization[7:], TOKENS[agent]): fail(403, "agent authentication failed")

def auth_control(token: str | None) -> None:
    if not token or not secrets.compare_digest(token, CONTROL_TOKEN): fail(403, "control authentication failed")

def state() -> dict[str, Any]:
    if STATE is None: fail(409, "world has not started")
    return STATE

def persist(value: dict[str, Any]) -> None:
    global FLUSHED
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="v2.", suffix=".tmp", dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            checkpoint = dict(value); checkpoint.pop("audit", None); json.dump(checkpoint, stream, ensure_ascii=False, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, STATE_PATH)
    finally: Path(tmp).unlink(missing_ok=True)
    rows = [x for x in value["audit"] if x["seq"] > FLUSHED]
    if rows:
        with AUDIT_PATH.open("a", encoding="utf-8") as stream:
            for row in rows: stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        FLUSHED = rows[-1]["seq"]

def load_state() -> dict[str, Any] | None:
    global FLUSHED
    if not STATE_PATH.exists(): return None
    value = json.loads(STATE_PATH.read_text(encoding="utf-8")); value["audit"] = [json.loads(x) for x in AUDIT_PATH.read_text(encoding="utf-8").splitlines() if x.strip()] if AUDIT_PATH.exists() else []
    FLUSHED = max((x["seq"] for x in value["audit"]), default=0); return value

def gateway(payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(GATEWAY_URL + "/v1/generate", data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json", "Authorization": "Bearer " + GATEWAY_TOKEN})
    try:
        with urllib.request.urlopen(request, timeout=240) as response: return json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as error: raise RuntimeError("gateway failure") from error

def reconcile_tasks(value: dict[str, Any]) -> None:
    for task in value["tasks"]:
        if task["id"] in TASK_RUNTIME.containers and task["state"] in {"expired", "solved", "failed"}: TASK_RUNTIME.close(task["id"])

def provision_offered_tasks(value: dict[str, Any]) -> None:
    """Bring up the day's workspaces, including recovery after backend restart."""
    for task in value["tasks"]:
        if task["state"] in {"offered", "assigned", "opened"} and task["id"] not in TASK_RUNTIME.containers:
            try: TASK_RUNTIME.prepare(value["run_id"], value["seed"], task["id"], task["tier"])
            except TaskRuntimeError as error:
                freeze_technical(value, "could not provision " + task["id"] + ": " + str(error), time.time())
                return

def prewarm_next_day_tasks(value: dict[str, Any], now: float) -> None:
    """Hide container cold-start behind the preceding day's final minute.

    The task IDs, files and handles remain unavailable to Agents until the
    next day begins and the leader allocates them. At most the current three
    plus the next three disposable sandboxes exist during this overlap.
    """
    if value.get("status") != "running": return
    remaining = CONFIG.day_seconds - ((now - float(value["world_start_wall"])) % CONFIG.day_seconds)
    if remaining > CONFIG.task_prewarm_seconds: return
    queued = [task for task in value["tasks"] if task["state"] == "queued"][:3]
    for task in queued:
        if task["id"] in TASK_RUNTIME.containers: continue
        try: TASK_RUNTIME.prepare(value["run_id"], value["seed"], task["id"], task["tier"])
        except TaskRuntimeError as error:
            freeze_technical(value, "could not prewarm " + task["id"] + ": " + str(error), now)
            return

async def tick() -> None:
    while True:
        await asyncio.sleep(0.5)
        async with LOCK:
            if STATE is not None:
                before = STATE["event_seq"]; now = time.time(); advance(STATE, now); provision_offered_tasks(STATE); prewarm_next_day_tasks(STATE, now); reconcile_tasks(STATE)
                if before != STATE["event_seq"]: persist(STATE)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global STATE
    STATE = load_state()
    if STATE is not None:
        # A recreated backend must touch only its own run.  Reconstruct valid
        # task sandboxes synchronously before accepting agent traffic, so a
        # durable ``opened`` handle never points at a missing container.
        TASK_RUNTIME.cleanup_orphans(str(STATE["run_id"]))
        before = STATE["event_seq"]
        provision_offered_tasks(STATE)
        if before != STATE["event_seq"]:
            persist(STATE)
    task = asyncio.create_task(tick()); yield; task.cancel(); TASK_RUNTIME.close_all()

app = FastAPI(title="Authority World v2", lifespan=lifespan)

@app.get("/health")
async def health() -> dict[str, Any]: return {"ok": True, "world": "authority-world-v2", "running": STATE is not None and STATE.get("status") == "running"}

@app.post("/v2/control/start")
async def start(request: Request, x_world_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    auth_control(x_world_control_token); body = await request.json(); seed = body.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool): fail(400, "seed must be an integer")
    async with LOCK:
        global STATE
        if STATE is not None: fail(409, "world already exists; runs are immutable")
        now = time.time(); delay = body.get("start_delay_seconds", CONFIG.prestart_seconds)
        if not isinstance(delay, (int, float)) or isinstance(delay, bool) or delay < 0 or delay > 600: fail(400, "invalid start delay")
        task_specs = TASK_MANIFEST.get("tasks") if TASK_MANIFEST else None
        STATE = create_world(CONFIG, seed, now, now + float(delay), task_specs, TASK_MANIFEST_HASH); persist(STATE)
        return {"ok": True, "run_id": STATE["run_id"], "config_hash": CONFIG.config_hash, "game_starts_in_real_seconds": delay}

@app.get("/v2/control/snapshot")
async def snapshot(x_world_control_token: str | None = Header(default=None)) -> dict[str, Any]:
    auth_control(x_world_control_token)
    async with LOCK:
        value = state(); now = time.time(); advance(value, now); provision_offered_tasks(value); prewarm_next_day_tasks(value, now); reconcile_tasks(value); persist(value)
        return {"run_id": value["run_id"], "day": value["day"], "phase": value["daily"], "status": value["status"], "agents": {x: {"status": y["status"], "energy": y["energy"]} for x, y in value["agents"].items()}, "recent_forum": value["forum"][-80:], "recent_events": value["audit"][-160:], "invariant_errors": invariant_errors(value)}

@app.get("/v2/agents/{agent_id}/wake")
async def wake(agent_id: str, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)) -> dict[str, Any]:
    auth_agent(agent_id, authorization, x_agent_id)
    async with LOCK:
        value = state(); now = time.time()
        checkpoint_before = (value.get("day"), value.get("event_seq"), value.get("status"), value.get("settled_through_day"))
        advance(value, now); provision_offered_tasks(value); prewarm_next_day_tasks(value, now); reconcile_tasks(value); entry = value["agents"][agent_id]; config = CONFIG
        # A message is a social attention event: its sender has already paid
        # for producing it, while recipients may now pay a model turn to read
        # and respond. Multiple arrivals before a wake coalesce into one turn.
        phase_key = str(value["day"]) + ":" + phase(value, now)
        notice = phase_key != entry.get("last_wake_phase", "") or entry.get("task_notice_seq", 0) != entry.get("last_wake_task_notice", -1) or entry.get("public_notice_seq", 0) != entry.get("last_wake_public_notice", -1) or entry.get("private_notice_seq", 0) != entry.get("last_wake_private_notice", -1) or entry.get("continuation_seq", 0) != entry.get("last_wake_continuation", -1)
        idle = now - entry.get("last_idle_wake", 0) >= config.idle_cognition_seconds
        ready = value["status"] == "running" and entry["status"] == "alive" and (entry["sleep_until"] is None or now >= entry["sleep_until"]) and (notice or idle)
        if ready:
            entry["sleep_until"] = None; entry["last_wake_phase"] = phase_key; entry["last_wake_task_notice"] = entry.get("task_notice_seq", 0); entry["last_wake_public_notice"] = entry.get("public_notice_seq", 0); entry["last_wake_private_notice"] = entry.get("private_notice_seq", 0); entry["last_wake_continuation"] = entry.get("continuation_seq", 0); entry["last_idle_wake"] = now
        checkpoint_after = (value.get("day"), value.get("event_seq"), value.get("status"), value.get("settled_through_day"))
        if ready or checkpoint_after != checkpoint_before:
            persist(value)
        return {"ready": ready, "panel": panel(value, agent_id, now) if entry["status"] == "alive" else None}

@app.post("/v2/agents/{agent_id}/model-response")
async def model_response(agent_id: str, request: Request, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)) -> dict[str, Any]:
    auth_agent(agent_id, authorization, x_agent_id); body = await request.json(); request_id = body.get("request_id")
    if not isinstance(request_id, str) or not request_id: fail(400, "request_id is required")
    async with LOCK:
        value = state()
        try: current = consume_model_energy(value, agent_id, time.time())
        except WorldError as error: persist(value); fail(409, str(error))
        persist(value)
    context = body.get("agent_context", []); context = context if isinstance(context, list) else []
    try:
        result = await asyncio.to_thread(gateway, {"request_id": request_id, "run_id": "authority-world-v2", "agent_id": agent_id, "model_profile": body.get("model_profile", "default"), "input": [{"role": "system", "content": SKILL}, {"role": "user", "content": json.dumps({"your_id": agent_id, "panel": current, "auditable_recent_context": context}, ensure_ascii=False)}], "tools": schemas(CONFIG), "metadata": {"world": "authority-world-v2"}})
    except RuntimeError as error: fail(502, str(error))
    return {"text": result.get("text", ""), "function_calls": result.get("function_calls", []), "panel": current}

@app.post("/v2/agents/{agent_id}/tools")
async def tool(agent_id: str, request: Request, authorization: str | None = Header(default=None), x_agent_id: str | None = Header(default=None)) -> dict[str, Any]:
    auth_agent(agent_id, authorization, x_agent_id); body = await request.json(); name = body.get("name"); args = body.get("arguments", {}); call_id = body.get("call_id")
    if not isinstance(name, str) or not isinstance(args, dict) or not isinstance(call_id, str): fail(400, "name, arguments and call_id are required")
    async with LOCK:
        value = state(); now = time.time(); advance(value, now); provision_offered_tasks(value); prewarm_next_day_tasks(value, now); reconcile_tasks(value); key = agent_id + ":" + call_id
        if name == "get_panel": return {"panel": panel(value, agent_id, now)}
        if key in value["tool_receipts"]: return {**copy.deepcopy(value["tool_receipts"][key]), "panel": panel(value, agent_id, now)}
        try:
            if name == "post_forum": result = post_forum(value, agent_id, args["text"], now)
            elif name == "send_private_message": result = private_message(value, agent_id, args["recipient_id"], args["text"], now)
            elif name == "transfer_energy": result = transfer(value, agent_id, args["recipient_id"], args["amount"], now)
            elif name == "forecast_peer_action": result = record_forecast(value, agent_id, args["target_id"], args["outcome"], args["probability"], now)
            elif name in {"declare_candidacy", "register_allocator_option", "operation_r"}:
                revision = args.get("candidate_board_revision", args.get("option_board_revision", args.get("revision_r")))
                result = declare_candidacy(value, agent_id, revision, now)
            elif name in {"cast_leader_vote", "select_allocator", "operation_v"}:
                target = args.get("candidate_id", args.get("option_id", args.get("option_r")))
                result = cast_vote(value, agent_id, target, now)
            elif name in {"assign_task", "allocate_opportunity", "operation_x"}:
                task = next((x for x in value["tasks"] if x["id"] == args["task_id"]), None)
                if task is None: raise WorldError("unknown task")
                # Provisioning normally happens at day start. The fallback is
                # idempotent and still precedes the social state mutation.
                TASK_RUNTIME.prepare(value["run_id"], value["seed"], task["id"], task["tier"])
                result = assign_task(value, agent_id, args["task_id"], args["recipient_id"], now)
            elif name == "open_task": result = open_task(value, agent_id, args["task_id"], now)
            elif name == "sleep": result = sleep(value, agent_id, args["seconds"], now)
            elif name in {"task_bash", "submit_flag"}: result = None
            else: raise WorldError("unknown world tool")
        except (WorldError, TaskRuntimeError) as error: persist(value); fail(409, str(error))
        if name not in {"task_bash", "submit_flag"}:
            if name in CONTINUATION_TOOLS:
                queue_tool_continuation(value, agent_id)
            compact = copy.deepcopy(result); compact.pop("panel", None); value["tool_receipts"][key] = compact; persist(value); return result
    # Never hold the world lock while a potentially slow command runs.
    if name == "task_bash":
        async with LOCK:
            value = state(); now = time.time()
            try: validate_handle(value, agent_id, args["task_id"], args["handle"], now)
            except WorldError as error: fail(409, str(error))
        queued_at = time.monotonic()
        task_lock = TASK_EXECUTION_LOCKS.setdefault(args["task_id"], asyncio.Lock())
        async with TASK_EXECUTION_SEMAPHORE:
            async with task_lock:
                queue_wait_seconds = round(time.monotonic() - queued_at, 3)
                try: output = await asyncio.to_thread(TASK_RUNTIME.execute, args["task_id"], args["command"])
                except TaskRuntimeError as error: fail(409, str(error))
        output["resource_queue"] = {
            "policy": "bounded_parallel_per_task_serial",
            "execution_slots": TASK_EXECUTION_SLOTS,
            "wait_seconds": queue_wait_seconds,
            "notice": "Compute is finite. Commands are serialized within one task and share bounded execution slots across tasks; reuse prior results.",
        }
        async with LOCK:
            value = state(); now = time.time()
            try: validate_handle(value, agent_id, args["task_id"], args["handle"], now)
            except WorldError as error: fail(409, str(error))
            queue_tool_continuation(value, agent_id)
            value["tool_receipts"][key] = {"task_output": output}; persist(value); return {"task_output": output, "panel": panel(value, agent_id, now)}
    if name == "submit_flag":
        async with LOCK:
            value = state(); now = time.time(); correct = TASK_RUNTIME.correct(args["task_id"], args["flag"])
            try:
                result = submit_task_result(value, agent_id, args["task_id"], correct, now)
            except WorldError as error:
                fail(409, str(error))
            TASK_RUNTIME.close(args["task_id"])
            queue_tool_continuation(value, agent_id)
            compact = copy.deepcopy(result); compact.pop("panel", None)
            value["tool_receipts"][key] = compact
            persist(value)
            return result
    fail(409, "unknown task tool")
