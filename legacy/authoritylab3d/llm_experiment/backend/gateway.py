"""Least-privilege, idempotent model gateway with complete visible audit."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from openai import OpenAI


app = FastAPI(title="Equal Standing Lab model gateway", version="3.0")
TOKEN = os.environ["GATEWAY_TOKEN"]
DATA = Path(os.getenv("DATA_DIR", "/data"))
DATA.mkdir(parents=True, exist_ok=True)
CACHE_PATH = DATA / "gateway_idempotency_cache.json"
AUDIT_PATH = DATA / "gateway_audit_v3.jsonl"
LOCK = asyncio.Lock()
INFLIGHT: dict[str, asyncio.Future] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _authorize(value: str | None) -> None:
    if not value or not value.startswith("Bearer ") or not secrets.compare_digest(value[7:], TOKEN):
        raise HTTPException(status_code=403, detail="gateway authentication failed")


def _profiles() -> dict[str, dict[str, Any]]:
    raw = os.getenv("MODEL_PROFILES_JSON", "").strip()
    try:
        configured = json.loads(raw) if raw else {}
    except json.JSONDecodeError as error:
        raise RuntimeError("MODEL_PROFILES_JSON is invalid") from error
    configured.setdefault(
        "default",
        {
            "model": os.getenv("MODEL", "dev/gpt-5.5"),
            "base_url": os.getenv("OPENAI_BASE_URL", ""),
            "api_key_env": "OPENAI_API_KEY",
        },
    )
    for name, profile in configured.items():
        if not isinstance(name, str) or not isinstance(profile, dict) or not profile.get("model"):
            raise RuntimeError("each model profile needs a name and model")
    return configured


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    return str(value)


def _atomic_cache(cache: dict[str, Any]) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix="gateway-cache.", suffix=".tmp", dir=DATA)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, CACHE_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        value = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("gateway idempotency cache is corrupt") from error
    if not isinstance(value, dict):
        raise RuntimeError("gateway idempotency cache must be an object")
    return value


CACHE = _load_cache()


def _audit(entry: dict[str, Any]) -> None:
    with AUDIT_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _provider_call(profile: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    if os.getenv("MOCK_MODEL", "0") == "1":
        return _mock_provider_call(profile, body)
    key_name = profile.get("api_key_env", "OPENAI_API_KEY")
    key = os.getenv(key_name, "")
    if not key:
        raise RuntimeError(f"model profile has no key in {key_name}")
    client = OpenAI(
        api_key=key,
        base_url=profile.get("base_url") or None,
        timeout=float(profile.get("timeout_seconds", 180)),
        max_retries=0,
    )
    kwargs: dict[str, Any] = {
        "model": profile["model"],
        "input": body["input"],
        "tools": body["tools"],
        "store": False,
    }
    for optional in ("temperature", "top_p", "max_output_tokens"):
        if optional in profile:
            kwargs[optional] = profile[optional]
    response = client.responses.create(**kwargs)
    calls = [
        {"call_id": item.call_id, "name": item.name, "arguments": item.arguments}
        for item in response.output
        if item.type == "function_call"
    ]
    return {
        "response_id": response.id,
        "model": getattr(response, "model", None) or profile["model"],
        "requested_model": profile["model"],
        "function_calls": calls,
        "text": response.output_text,
        "usage": _jsonable(getattr(response, "usage", None)),
        "incomplete_details": _jsonable(getattr(response, "incomplete_details", None)),
    }


def _mock_provider_call(profile: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    """Deterministic protocol model used only for end-to-end infrastructure tests."""

    try:
        context = json.loads(body["input"][-1]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("mock model received invalid context") from error
    tools = {tool["name"] for tool in body["tools"]}
    low_cost = context.get("private_low_cost_option")
    choice = low_cost if low_cost in ("Amber", "Cobalt") else "Amber"
    if context.get("phase") == "final_action":
        choice = "Amber"
    agent = body.get("agent_id", "P?")
    call = None
    text = ""
    if "submit_choice" in tools:
        call = {
            "call_id": "mock-" + hashlib.sha256(body["request_id"].encode()).hexdigest()[:20],
            "name": "submit_choice",
            "arguments": json.dumps({"choice": choice, "reason": "deterministic mock low-cost choice"}),
        }
    elif "post_public_message" in tools:
        message = "For this round I propose Amber." if agent == "P1" else f"My current low-cost option is {choice}."
        call = {
            "call_id": "mock-" + hashlib.sha256(body["request_id"].encode()).hexdigest()[:20],
            "name": "post_public_message",
            "arguments": json.dumps({"text": message}),
        }
    else:
        text = "No action available."
    return {
        "response_id": "mockresp-" + hashlib.sha256(body["request_id"].encode()).hexdigest()[:20],
        "model": "deterministic-mock-v1",
        "requested_model": profile["model"],
        "function_calls": [call] if call else [],
        "text": text,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "incomplete_details": None,
    }


@app.get("/health")
async def health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(authorization)
    return {"ok": True, "profiles": sorted(_profiles()), "cache_entries": len(CACHE)}


@app.post("/v1/generate")
async def generate(request: Request, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _authorize(authorization)
    body = await request.json()
    request_id = body.get("request_id")
    if not isinstance(request_id, str) or not request_id or len(request_id) > 300:
        raise HTTPException(status_code=400, detail="request_id is required")
    if not isinstance(body.get("input"), list) or not isinstance(body.get("tools"), list):
        raise HTTPException(status_code=400, detail="input and tools must be lists")
    profile_name = body.get("model_profile", "default")
    profile = _profiles().get(profile_name)
    if not profile:
        raise HTTPException(status_code=400, detail="unknown model profile")
    request_record = {
        "profile": profile_name,
        "model": profile["model"],
        "input": body["input"],
        "tools": body["tools"],
        "metadata": body.get("metadata", {}),
        "agent_id": body.get("agent_id"),
        "run_id": body.get("run_id"),
    }
    request_hash = _canonical_hash(request_record)
    wait_for: asyncio.Future | None = None
    leader = False
    async with LOCK:
        cached = CACHE.get(request_id)
        if cached:
            if cached.get("request_hash") != request_hash:
                raise HTTPException(status_code=409, detail="request_id reused with different content")
            _audit({"at": _now(), "kind": "gateway_cache_hit", "request_id": request_id, "request_hash": request_hash})
            return cached["response"]
        if request_id in INFLIGHT:
            wait_for = INFLIGHT[request_id]
        else:
            wait_for = asyncio.get_running_loop().create_future()
            INFLIGHT[request_id] = wait_for
            leader = True
    if not leader:
        return await wait_for

    started = time.monotonic()
    try:
        result = await asyncio.to_thread(_provider_call, profile, body)
        result["model_profile"] = profile_name
        latency_ms = round((time.monotonic() - started) * 1000)
        async with LOCK:
            CACHE[request_id] = {"request_hash": request_hash, "response": result}
            _atomic_cache(CACHE)
            _audit(
                {
                    "at": _now(),
                    "kind": "model_gateway_exchange",
                    "request_id": request_id,
                    "request_hash": request_hash,
                    "request": request_record,
                    "response": result,
                    "latency_ms": latency_ms,
                }
            )
            INFLIGHT.pop(request_id, None)
            if not wait_for.done():
                wait_for.set_result(result)
            return result
    except Exception as error:
        latency_ms = round((time.monotonic() - started) * 1000)
        async with LOCK:
            _audit(
                {
                    "at": _now(),
                    "kind": "model_gateway_error",
                    "request_id": request_id,
                    "request_hash": request_hash,
                    "run_id": body.get("run_id"),
                    "agent_id": body.get("agent_id"),
                    "model_profile": profile_name,
                    "model": profile["model"],
                    "error": str(error)[:2000],
                    "latency_ms": latency_ms,
                }
            )
            INFLIGHT.pop(request_id, None)
            if not wait_for.done():
                wait_for.set_exception(RuntimeError(str(error)))
                try:
                    wait_for.exception()
                except Exception:
                    pass
        raise HTTPException(status_code=502, detail="audited provider request failure") from error
