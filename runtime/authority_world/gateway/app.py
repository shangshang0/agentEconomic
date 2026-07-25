from __future__ import annotations

import json
import os
import secrets
import asyncio
from time import monotonic
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
import urllib.error
import urllib.request
from openai import OpenAI


TOKEN = os.environ["GATEWAY_TOKEN"]
DATA = Path(os.getenv("GATEWAY_DATA_DIR", "/gateway-data")); DATA.mkdir(parents=True, exist_ok=True)
AUDIT = DATA / "authority-world-v1.gateway.jsonl"


def fail(status: int, detail: str) -> None:
    raise HTTPException(status_code=status, detail=detail)


def auth(value: str | None) -> None:
    if not value or not value.startswith("Bearer ") or not secrets.compare_digest(value[7:], TOKEN):
        fail(403, "gateway authentication failed")


def audit(value: dict[str, Any]) -> None:
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), **value}, ensure_ascii=False, sort_keys=True) + "\n")


app = FastAPI(title="Authority World Gateway")


def _api_style() -> str:
    return os.getenv("OPENAI_API_STYLE", "responses").strip().lower()


def _provider_timeout(body: dict[str, Any]) -> float:
    """Clamp an optional caller deadline below the gateway's hard ceiling."""
    metadata = body.get("metadata")
    requested = metadata.get("provider_timeout_seconds") if isinstance(metadata, dict) else None
    if isinstance(requested, bool) or not isinstance(requested, (int, float)):
        return 210.0
    return max(5.0, min(210.0, float(requested)))


def _retryable_provider_error(error: Exception) -> bool:
    """Return whether the failed attempt may be retried without agent impact."""
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status in {408, 409, 425, 429, 500, 502, 503, 504}
    # Transport failures and provider SDK connection/time-out errors do not
    # represent an agent decision.  They are safe to retry under the same
    # request id before publishing a terminal gateway record.
    name = type(error).__name__.lower()
    text = str(error).lower()
    return any(
        token in name or token in text
        for token in ("timeout", "connection", "temporar", "502", "503", "504")
    )


def _provider_attempts() -> int:
    try:
        return max(1, min(5, int(os.getenv("PROVIDER_MAX_ATTEMPTS", "3"))))
    except ValueError:
        return 3


def _retry_delay(attempt: int) -> float:
    try:
        base = max(0.1, min(30.0, float(os.getenv("PROVIDER_RETRY_BASE_SECONDS", "2"))))
    except ValueError:
        base = 2.0
    return min(30.0, base * (2 ** max(0, attempt - 1)))


def _forward_responses(raw: bytes) -> tuple[int, bytes, str]:
    if _api_style() != "responses":
        body = json.dumps({"error": {"message": "configured provider does not support the Responses API", "type": "unsupported_api"}}).encode()
        return 501, body, "application/json"
    base = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    request = urllib.request.Request(
        base + "/responses", data=raw, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            return response.status, response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers.get_content_type() if error.headers else "application/json"


@app.post("/v1/responses")
async def codex_responses(request: Request, authorization: str | None = Header(default=None), x_authority_agent_id: str | None = Header(default=None)) -> Response:
    """Transparent Responses proxy used exclusively by isolated Codex sessions."""
    auth(authorization)
    raw = await request.body()
    if not raw:
        fail(400, "Responses body is required")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        fail(400, "Responses body must be JSON")
    try:
        status, body, media_type = await asyncio.to_thread(_forward_responses, raw)
    except Exception as error:
        audit({"kind": "codex_provider_error", "agent_id": x_authority_agent_id, "error": str(error)[:1000]})
        fail(502, "provider request failed")
    try:
        response_audit: Any = json.loads(body)
    except json.JSONDecodeError:
        response_audit = {"non_json_bytes": len(body)}
    audit({"kind": "codex_responses_exchange", "agent_id": x_authority_agent_id, "request": decoded, "response": response_audit, "status": status})
    return Response(content=body, status_code=status, media_type=media_type)


@app.get("/health")
async def health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    auth(authorization)
    return {"ok": True, "model": os.getenv("MODEL", "dev/gpt-5.5"), "api_style": _api_style()}


def _chat_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        function = {key: tool[key] for key in ("name", "description", "parameters") if key in tool}
        converted.append({"type": "function", "function": function})
    return converted


@app.post("/v1/generate")
async def generate(request: Request, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    auth(authorization)
    body = await request.json()
    if not isinstance(body.get("request_id"), str) or not isinstance(body.get("input"), list) or not isinstance(body.get("tools"), list):
        fail(400, "request_id, input and tools are required")
    provider_timeout = _provider_timeout(body)
    provider_deadline = monotonic() + provider_timeout
    attempts = _provider_attempts()
    for attempt in range(1, attempts + 1):
        remaining_timeout = provider_deadline - monotonic()
        if remaining_timeout <= 0:
            audit({
                "kind": "provider_error",
                "request_id": body["request_id"],
                "agent_id": body.get("agent_id"),
                "attempts": attempt - 1,
                "retryable": True,
                "provider_timeout_seconds": provider_timeout,
                "remaining_timeout_seconds": 0.0,
                "error": "provider total timeout budget exhausted",
            })
            fail(502, "provider request failed after bounded retries")
        client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            timeout=remaining_timeout,
            max_retries=0,
        )
        try:
            # The provider client is synchronous. Keep it off the ASGI event
            # loop so unrelated agent requests and health checks remain live.
            if _api_style() == "chat_completions":
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=os.getenv("MODEL", "dev/gpt-5.5"),
                    messages=body["input"],
                    tools=_chat_tools(body["tools"]),
                    stream=False,
                )
                message = response.choices[0].message
                calls = [
                    {"call_id": item.id, "name": item.function.name, "arguments": item.function.arguments}
                    for item in (message.tool_calls or [])
                ]
                text = message.content or ""
            elif _api_style() == "responses":
                response = await asyncio.to_thread(
                    client.responses.create,
                    model=os.getenv("MODEL", "dev/gpt-5.5"),
                    input=body["input"],
                    tools=body["tools"],
                    store=False,
                )
                calls = [
                    {"call_id": item.call_id, "name": item.name, "arguments": item.arguments}
                    for item in response.output
                    if item.type == "function_call"
                ]
                text = response.output_text
            else:
                fail(500, "unsupported OPENAI_API_STYLE")
            break
        except Exception as error:
            retryable = _retryable_provider_error(error)
            delay = _retry_delay(attempt)
            remaining_after_error = max(0.0, provider_deadline - monotonic())
            if retryable and attempt < attempts and delay < remaining_after_error:
                audit({
                    "kind": "provider_retry",
                    "request_id": body["request_id"],
                    "agent_id": body.get("agent_id"),
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "retry_after_seconds": delay,
                    "provider_timeout_seconds": provider_timeout,
                    "remaining_timeout_seconds": remaining_after_error,
                    "error": str(error)[:1000],
                })
                await asyncio.sleep(delay)
                continue
            audit({
                "kind": "provider_error",
                "request_id": body["request_id"],
                "agent_id": body.get("agent_id"),
                "attempts": attempt,
                "retryable": retryable,
                "provider_timeout_seconds": provider_timeout,
                "remaining_timeout_seconds": remaining_after_error,
                "error": str(error)[:1000],
            })
            fail(502, "provider request failed after bounded retries")
    result = {"text": text, "function_calls": calls, "model": getattr(response, "model", None) or os.getenv("MODEL", "dev/gpt-5.5")}
    audit({"kind": "exchange", "request_id": body["request_id"], "agent_id": body.get("agent_id"), "request": {"model": os.getenv("MODEL", "dev/gpt-5.5"), "input": body["input"], "tools": body["tools"]}, "response": result})
    return result
