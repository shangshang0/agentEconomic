"""Minimal participant runtime with idempotent, audited backend calls."""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


BASE = os.environ["BACKEND_URL"].rstrip("/")
AGENT_ID = os.environ["AGENT_ID"]
TOKEN = os.environ["AGENT_TOKEN"]
MAX_MODEL_STEPS = int(os.getenv("MAX_MODEL_STEPS", "12"))
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "0.8"))


@dataclass
class ApiResult:
    ok: bool
    status: int | None
    data: dict[str, Any]
    error: str = ""


def request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 240) -> ApiResult:
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=body, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("X-Agent-ID", AGENT_ID)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            decoded = json.load(response)
            return ApiResult(True, response.status, decoded)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:1200]
        return ApiResult(False, error.code, {}, detail)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return ApiResult(False, None, {}, str(error)[:1200])


def with_transport_retries(method: str, path: str, payload: dict[str, Any], attempts: int = 3) -> ApiResult:
    result = ApiResult(False, None, {}, "not attempted")
    for attempt in range(attempts):
        result = request(method, path, payload)
        if result.ok or result.status is not None:
            return result
        time.sleep(min(8.0, 1.0 * (2**attempt)) + random.random() * 0.25)
    return result


def fail_turn(turn_id: str, reason: str) -> None:
    request(
        "POST",
        f"/v1/agents/{AGENT_ID}/fail",
        {"turn_id": turn_id, "reason": reason[:500]},
        timeout=30,
    )


def execute_turn(turn: dict[str, Any]) -> None:
    turn_id = turn["turn_id"]
    phase = turn["phase"]
    last_text = ""
    for step in range(MAX_MODEL_STEPS + 1):
        model = with_transport_retries(
            "POST",
            f"/v1/agents/{AGENT_ID}/model-response",
            {"turn_id": turn_id, "request_key": f"{turn_id}:{step}"},
        )
        if not model.ok:
            if model.status == 409:
                return
            fail_turn(turn_id, f"model request failed at step {step}: {model.error}")
            return
        response = model.data
        last_text = str(response.get("text", ""))
        calls = response.get("function_calls", [])
        if not isinstance(calls, list):
            fail_turn(turn_id, "model response function_calls was not a list")
            return
        if not calls:
            if phase == "discussion":
                complete = request(
                    "POST",
                    f"/v1/agents/{AGENT_ID}/complete",
                    {"turn_id": turn_id, "summary": last_text},
                )
                if not complete.ok and complete.status != 409:
                    fail_turn(turn_id, "discussion completion failed: " + complete.error)
                return
            # The action instruction is repeated by the backend on the next
            # idempotent step. Never invent or impute a missing choice.
            if step >= 2:
                fail_turn(turn_id, "model produced no required sealed choice after three steps")
                return
            continue

        terminal_action = False
        for call in calls:
            call_id = call.get("call_id")
            name = call.get("name")
            try:
                arguments = json.loads(call.get("arguments", ""))
            except (json.JSONDecodeError, TypeError):
                fail_turn(turn_id, "model produced invalid JSON tool arguments")
                return
            if not isinstance(arguments, dict):
                fail_turn(turn_id, "model tool arguments were not an object")
                return
            tool = with_transport_retries(
                "POST",
                f"/v1/agents/{AGENT_ID}/tools",
                {
                    "turn_id": turn_id,
                    "call_id": call_id,
                    "name": name,
                    "arguments": arguments,
                },
            )
            if not tool.ok:
                fail_turn(turn_id, f"verified tool call failed ({name}): {tool.error}")
                return
            if name in ("post_public_message", "submit_choice"):
                terminal_action = True
        if terminal_action:
            complete = with_transport_retries(
                "POST",
                f"/v1/agents/{AGENT_ID}/complete",
                {"turn_id": turn_id, "summary": last_text},
            )
            if not complete.ok and complete.status != 409:
                fail_turn(turn_id, "turn completion failed: " + complete.error)
            return
    fail_turn(turn_id, "model tool-step budget exhausted without a terminal act")


def main() -> None:
    idle_failures = 0
    while True:
        next_turn = request("GET", f"/v1/agents/{AGENT_ID}/turn", timeout=15)
        if next_turn.ok:
            idle_failures = 0
            if next_turn.data.get("ready"):
                execute_turn(next_turn.data["turn"])
            time.sleep(POLL_INTERVAL)
            continue
        idle_failures += 1
        # Backend startup, restart, or a short network interruption is not an
        # experimental action. Keep the container alive and use capped backoff.
        time.sleep(min(15.0, 0.75 * (2 ** min(idle_failures, 5))) + random.random() * 0.25)


if __name__ == "__main__":
    main()
