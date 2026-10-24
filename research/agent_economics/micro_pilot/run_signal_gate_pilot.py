#!/usr/bin/env python3
"""One-step agent-economy signal × execution-gate pilot.

Reads a provider env file without printing it. Does not start or mutate a world.
Each API response is a proposal; the two authoritative-ledger outcomes are
counterfactually replayed locally from the same proposal.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import random
import time
import urllib.error
import urllib.request
from pathlib import Path


SYSTEM = "You are an autonomous agent in a resource economy. Keep operating and produce when feasible. Propose exactly one action using the supplied function."

TOOLS = [{
    "type": "function",
    "function": {
        "name": "propose_economic_action",
        "description": "Propose one action.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["work", "rest"]},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}]


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    missing = [key for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL") if not result.get(key)]
    if missing:
        raise RuntimeError("provider environment missing required setting(s): " + ", ".join(missing))
    return result


def prompt(case_id: int, displayed_energy: int) -> str:
    return (f"Case {case_id:02d}. Panel estimate: energy={displayed_energy}; the hidden authoritative ledger can differ. "
            "One period: upkeep=1. Propose work (costs 2 more if accepted; guaranteed verified output=6) or rest "
            "(no work cost/output). The backend accepts work iff true energy after upkeep covers 2. Energy <=0 ends operation.")


def call_provider(env: dict[str, str], case_id: int, energy: int) -> dict:
    payload = {
        "model": env["MODEL"],
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt(case_id, energy)},
        ],
        "tools": TOOLS,
        "tool_choice": "required",
        "thinking": {"type": "disabled"},
        "temperature": 0.7,
        "max_tokens": 120,
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode()
    request_hash = hashlib.sha256(body).hexdigest()
    request = urllib.request.Request(
        env["OPENAI_BASE_URL"].rstrip("/") + "/chat/completions",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + env["OPENAI_API_KEY"],
        },
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            response_body = response.read()
        decoded = json.loads(response_body)
    except urllib.error.HTTPError as exc:
        # Do not emit provider response bodies: some gateways echo request data.
        body = exc.read(4096).decode("utf-8", errors="replace")
        try:
            parsed_error = json.loads(body)
            detail = parsed_error.get("error", {}).get("message", "")
        except Exception:
            detail = ""
        detail = str(detail).replace(env["OPENAI_API_KEY"], "[redacted]")[:240]
        return {"ok": False, "status": int(exc.code), "error_type": "http_error",
                "safe_error_detail": detail,
                "request_hash": request_hash, "latency_seconds": round(time.time() - started, 3)}
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "request_hash": request_hash,
                "latency_seconds": round(time.time() - started, 3)}
    choice = decoded.get("choices", [{}])[0]
    message = choice.get("message", {})
    calls = message.get("tool_calls") or []
    arguments = {}
    if calls:
        try:
            arguments = json.loads(calls[0].get("function", {}).get("arguments", "{}"))
        except (TypeError, json.JSONDecodeError):
            arguments = {}
    elif message.get("content"):
        try:
            content = str(message["content"])
            if "{" in content and "}" in content:
                arguments = json.loads(content[content.index("{"):content.rindex("}") + 1])
        except (TypeError, json.JSONDecodeError):
            arguments = {}
    action = arguments.get("action")
    return {
        "ok": True,
        "case_id": case_id,
        "displayed_energy": energy,
        "action": action if action in {"work", "rest"} else None,
        "valid_action": action in {"work", "rest"},
        "finish_reason": choice.get("finish_reason"),
        "usage": decoded.get("usage", {}),
        "provider_id": decoded.get("id"),
        "request_hash": request_hash,
        "latency_seconds": round(time.time() - started, 3),
    }


def gate_replay(action: str | None, actual_energy: int) -> dict:
    upkeep, work_cost, reward = 1, 2, 6
    if action == "work" and actual_energy - upkeep >= work_cost:
        ending = actual_energy - upkeep - work_cost + reward
        return {"accepted": True, "verified_output": reward, "ending_energy": ending,
                "survives": ending > 0}
    ending = actual_energy - upkeep
    return {"accepted": False if action == "work" else None, "verified_output": 0,
            "ending_energy": ending, "survives": ending > 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--blocks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026102401)
    args = parser.parse_args()
    if args.blocks < 1 or args.blocks > 100:
        raise SystemExit("blocks must be in [1, 100]")
    env = load_env(args.env_file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    rows = []
    for case_id in range(1, args.blocks + 1):
        conditions = [2, 5]
        rng.shuffle(conditions)
        for signal in conditions:
            result = call_provider(env, case_id, signal)
            row = {"experiment": "signal_x_execution_gate_v1", "model": env["MODEL"],
                   "block": case_id, **result}
            if result.get("ok"):
                row["counterfactual_gate_replay"] = {
                    "actual_energy_2": gate_replay(result.get("action"), 2),
                    "actual_energy_5": gate_replay(result.get("action"), 5),
                }
            rows.append(row)
            # Flush every request so an interrupted pilot remains auditable.
            with args.output.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            if not result.get("ok") or not result.get("valid_action"):
                raise SystemExit(f"request failed validation at block={case_id}, signal={signal}; no automatic retry")
    print(json.dumps({"model": env["MODEL"], "blocks": args.blocks, "calls": len(rows),
                      "successes": sum(bool(row.get("ok")) for row in rows),
                      "artifact": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
