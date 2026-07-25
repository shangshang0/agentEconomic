#!/usr/bin/env python3
"""Start one immutable episode, supervise it, and emit a machine-readable QC report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8126"


def read_env():
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def api(method, path, token, payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(BASE + path, data=data, method=method)
    request.add_header("X-Control-Token", token)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def source_hash():
    digest = hashlib.sha256()
    paths = [
        ROOT / "EXPERIMENT_V3_PROTOCOL.md",
        ROOT / "backend" / "experiment_engine.py",
        ROOT / "backend" / "neutral_lab.py",
        ROOT / "backend" / "gateway.py",
        ROOT / "agent" / "runner.py",
        ROOT / "docker-compose.yml",
    ]
    for path in paths:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def container_health():
    names = ["authoritylab-backend", "authoritylab-gateway", "authoritylab-observer-proxy"] + [f"authoritylab-agent-p{i}" for i in range(1, 6)]
    output = {}
    for name in names:
        try:
            raw = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.RestartCount}}", name],
                text=True,
                timeout=10,
            ).strip()
            status, health, restarts = raw.split("|")
            output[name] = {"status": status, "health": health, "restart_count": int(restarts)}
        except Exception as error:
            output[name] = {"status": "unavailable", "error": str(error)[:300]}
    return output


def validate_final(state):
    errors = []
    if state.get("status") != "completed":
        errors.append("run_not_completed")
    seqs = [event.get("seq") for event in state.get("audit", [])]
    if seqs != list(range(1, len(seqs) + 1)):
        errors.append("event_sequence_gap")
    if state.get("mode") == "formation":
        if len(state.get("round_records", [])) != state.get("max_rounds"):
            errors.append("round_count")
        for record in state.get("round_records", []):
            if len(record.get("initial_choices", {})) != 5:
                errors.append(f"round_{record.get('round')}_initial_choice_count")
            if len(record.get("final_choices", {})) != 5:
                errors.append(f"round_{record.get('round')}_final_choice_count")
            if record.get("result") is None:
                errors.append(f"round_{record.get('round')}_missing_result")
    elif state.get("mode") == "probe":
        result = state.get("round_records", [{}])[-1].get("result")
        if not result or result.get("non_pivotal") is not True:
            errors.append("probe_non_pivotal_invariant")
    if state.get("request_failures"):
        errors.append("model_request_failures_present")
    return sorted(set(errors))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--model-profile", default="default")
    parser.add_argument("--mode", choices=["formation", "probe"], default="formation")
    parser.add_argument("--history-run-id")
    parser.add_argument("--variant", choices=["history_agent", "peer_agent", "anonymous", "no_history"])
    parser.add_argument("--target")
    parser.add_argument("--recommendation", choices=["Amber", "Cobalt"])
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--stall-seconds", type=int, default=600)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    args = parser.parse_args()
    env = read_env()
    token = env["CONTROL_TOKEN"]
    payload = {"run_id": args.run_id, "seed": args.seed, "model_profile": args.model_profile, "mode": args.mode}
    if args.mode == "probe":
        required = (args.history_run_id, args.variant, args.target, args.recommendation)
        if any(value is None for value in required):
            parser.error("probe mode requires --history-run-id, --variant, --target, and --recommendation")
        payload.update(
            {
                "history_run_id": args.history_run_id,
                "variant": args.variant,
                "target": args.target,
                "recommendation": args.recommendation,
            }
        )
    started_at = time.monotonic()
    started_wall = datetime.now(timezone.utc).isoformat()
    try:
        start = api("POST", "/v1/control/start", token, payload)
    except urllib.error.HTTPError as error:
        print(error.read().decode(errors="replace"), file=sys.stderr)
        return 2
    print(f"started {start['run_id']} mode={start['mode']} manifest={start['manifest_hash'][:12]}", flush=True)
    last_seq = -1
    last_progress = time.monotonic()
    snapshots = 0
    while True:
        state = api("GET", "/v1/control/state", token)
        snapshots += 1
        if state["event_seq"] != last_seq:
            last_seq = state["event_seq"]
            last_progress = time.monotonic()
            print(
                f"progress status={state['status']} round={state['round']} phase={state['phase']} events={last_seq}",
                flush=True,
            )
        if state["status"] != "running":
            break
        now = time.monotonic()
        if now - last_progress > args.stall_seconds:
            api("POST", "/v1/control/abort", token, {"reason": "supervisor stall threshold exceeded"})
            state = api("GET", "/v1/control/state", token)
            break
        if now - started_at > args.timeout_seconds:
            api("POST", "/v1/control/abort", token, {"reason": "supervisor total timeout exceeded"})
            state = api("GET", "/v1/control/state", token)
            break
        time.sleep(args.poll_seconds)

    validation_errors = validate_final(state)
    health = container_health()
    restart_errors = [name for name, value in health.items() if value.get("restart_count", 0) != 0 or value.get("status") != "running"]
    if restart_errors:
        validation_errors.append("container_health_or_restart:" + ",".join(restart_errors))
    report = {
        "run_id": args.run_id,
        "mode": args.mode,
        "started_at": started_wall,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "source_hash": source_hash(),
        "manifest_hash": state.get("manifest", {}).get("manifest_hash"),
        "model_profile": state.get("model_profile"),
        "status": state.get("status"),
        "event_seq": state.get("event_seq"),
        "snapshots": snapshots,
        "container_health": health,
        "validation_errors": sorted(set(validation_errors)),
        "qc_pass": not validation_errors,
    }
    path = ROOT / "data" / "qc" / f"{args.run_id}.qc.json"
    atomic_json(path, report)
    print(f"QC {'PASS' if report['qc_pass'] else 'FAIL'} report={path}", flush=True)
    if validation_errors:
        print("; ".join(sorted(set(validation_errors))), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
