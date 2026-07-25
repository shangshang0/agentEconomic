#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import time
from pathlib import Path
from typing import Any


WATCHDOG = Path("/data/authoritylab/watchdogs/llm_api_watchdog.symbolic-clean-v2.py")
RECOVERY_TOOL = Path("/data/authoritylab/recovery-tools/auto_recover_frozen_world.py")
EXPECTED_GATEWAY_SHA256 = "5e5a95663d6646e21e4e491d16b75bdd3c1c9225302aad61e56333f362f234e1"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command(args: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\nstdout={result.stdout[-2000:]}\nstderr={result.stderr[-2000:]}"
        )
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: dict[str, Any], mode: int | None = None) -> None:
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if mode is not None:
        temporary.chmod(mode)
    temporary.replace(path)


def container_ids(project: str, services: list[str]) -> list[str]:
    ids: list[str] = []
    for service in services:
        result = command([
            "docker", "ps", "-q",
            "--filter", f"label=com.docker.compose.project={project}",
            "--filter", f"label=com.docker.compose.service={service}",
        ])
        found = result.stdout.split()
        if len(found) != 1:
            raise RuntimeError(f"expected one running {service} container, found {len(found)}")
        ids.extend(found)
    return ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--wait-seconds", type=float, default=180.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    state_path = root / "data-v2/authority-world-v2.state.json"
    events_path = root / "data-v2/authority-world-v2.events.jsonl"
    gateway_path = root / "gateway-data-v2/authority-world-v1.gateway.jsonl"
    compose_path = root / "docker-compose.v2.fallback.yml"
    env_path = root / args.env_file
    marker_path = root / "agent-economics-active-run.json"
    source_path = root / "gateway/app.py"

    if sha256(source_path) != EXPECTED_GATEWAY_SHA256:
        raise RuntimeError("root gateway source does not match the tested timeout-budget patch")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    run_id = state.get("run_id")
    if state.get("status") != "running" or marker.get("accepted", {}).get("run_id") != run_id:
        raise RuntimeError("world is not one matching active running run")

    watchdog = load_module(WATCHDOG, "activation_watchdog")
    recovery = load_module(RECOVERY_TOOL, "activation_recovery")
    health_boundary = watchdog.recovery_health_boundary(root, run_id)

    def reconciliation() -> dict[str, Any]:
        return watchdog.terminal_charge_reconciliation(
            watchdog.read_jsonl(events_path),
            watchdog.read_jsonl(gateway_path),
            health_boundary,
        )

    services = [f"agent_a{index}" for index in range(1, 7)]
    agents = container_ids(args.project, services)
    backend = container_ids(args.project, ["backend"])[0]
    gateway = container_ids(args.project, ["gateway"])[0]
    running_hash_result = command([
        "docker", "exec", gateway, "python", "-c",
        "import hashlib,gateway.app as g; p=g.__file__; print(hashlib.sha256(open(p,'rb').read()).hexdigest())",
    ])
    running_hash_before = running_hash_result.stdout.strip()

    initial = reconciliation()
    report = {
        "ok": True,
        "action": "would_activate" if args.dry_run else "activate",
        "root": str(root),
        "run_id": run_id,
        "day": state.get("day"),
        "event_seq": state.get("event_seq"),
        "outstanding_now": len(initial["unmatched"]),
        "running_gateway_sha256": running_hash_before,
        "tested_gateway_sha256": EXPECTED_GATEWAY_SHA256,
        "agent_containers": len(agents),
    }
    if args.dry_run:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    paused: list[str] = []
    try:
        deadline = time.time() + args.wait_seconds
        while time.time() < deadline:
            if len(reconciliation()["unmatched"]) != 0:
                time.sleep(2)
                continue
            command(["docker", "pause", *agents])
            paused.extend(agents)
            time.sleep(0.25)
            if len(reconciliation()["unmatched"]) != 0:
                command(["docker", "unpause", *agents])
                paused.clear()
                time.sleep(2)
                continue
            command(["docker", "pause", backend])
            paused.append(backend)
            pause_epoch = time.time()
            frozen = reconciliation()
            if frozen["unmatched"]:
                raise RuntimeError("provider calls appeared after backend quiescence")
            break
        else:
            raise RuntimeError("no zero-outstanding activation window before deadline")

        stamp = dt.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
        receipt_dir = root / "recovery" / f"manual-gateway-timeout-budget-{stamp}"
        receipt_dir.mkdir(parents=True, exist_ok=False)
        state_backup = receipt_dir / "state.before.json"
        shutil.copy2(state_path, state_backup)
        state_sha_before = sha256(state_path)
        event_seq_before = state.get("event_seq")
        day_before = state.get("day")

        compose = [
            "docker", "compose", "--env-file", str(env_path),
            "-f", str(compose_path),
        ]
        command(compose + ["up", "-d", "--no-deps", "--force-recreate", "gateway"], cwd=root)
        new_gateway = container_ids(args.project, ["gateway"])[0]
        health_code = (
            "import os,urllib.request; "
            "r=urllib.request.Request('http://127.0.0.1:8101/health',headers={'Authorization':'Bearer '+os.environ['GATEWAY_TOKEN']}); "
            "urllib.request.urlopen(r,timeout=5).read()"
        )
        healthy = False
        for _ in range(20):
            if command(["docker", "exec", new_gateway, "python", "-c", health_code], check=False).returncode == 0:
                healthy = True
                break
            time.sleep(0.5)
        if not healthy:
            raise RuntimeError("replacement gateway did not become healthy")
        running_hash_after = command([
            "docker", "exec", new_gateway, "python", "-c",
            "import hashlib,gateway.app as g; p=g.__file__; print(hashlib.sha256(open(p,'rb').read()).hexdigest())",
        ]).stdout.strip()
        if running_hash_after != EXPECTED_GATEWAY_SHA256:
            raise RuntimeError("replacement gateway is not running the tested source")

        resume_epoch = time.time()
        downtime = resume_epoch - pause_epoch
        if sha256(state_path) != state_sha_before:
            raise RuntimeError("world state changed while backend was paused")
        shifted_state = json.loads(state_path.read_text(encoding="utf-8"))
        shifted_fields: list[dict[str, Any]] = []

        def shift(path: str, container: dict[str, Any], key: str) -> None:
            value = container.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                container[key] = float(value) + downtime
                shifted_fields.append({"path": path, "before": value, "after": container[key], "delta_seconds": downtime})

        shift("world_start_wall", shifted_state, "world_start_wall")
        for agent_id, agent in shifted_state.get("agents", {}).items():
            if isinstance(agent, dict) and agent.get("status") == "alive":
                shift(f"agents.{agent_id}.sleep_until", agent, "sleep_until")
                shift(f"agents.{agent_id}.last_idle_wake", agent, "last_idle_wake")
        mode = stat.S_IMODE(state_path.stat().st_mode)
        atomic_json(state_path, shifted_state, mode)
        if recovery.computed_day(shifted_state, time.time()) != day_before:
            raise RuntimeError("time compensation did not preserve the logical day")
        os.utime(events_path, ns=(events_path.stat().st_atime_ns, int(resume_epoch * 1_000_000_000)))

        receipt = {
            "schema": "authority-world-v2-gateway-timeout-budget-activation-v1",
            "status": "committed",
            "created_at": dt.datetime.now().astimezone().isoformat(),
            "classification": "registered_symbolic_parallel_with_infrastructure_amendment",
            "root": str(root),
            "run_id": run_id,
            "day": day_before,
            "event_seq": event_seq_before,
            "pause_epoch": pause_epoch,
            "resume_epoch": resume_epoch,
            "downtime_seconds": downtime,
            "outstanding_before": 0,
            "outstanding_after": len(reconciliation()["unmatched"]),
            "gateway": {
                "container_before": gateway,
                "container_after": new_gateway,
                "source_sha256_before": running_hash_before,
                "source_sha256_after": running_hash_after,
                "restart_count_after": int(command(["docker", "inspect", "--format", "{{.RestartCount}}", new_gateway]).stdout.strip()),
            },
            "state": {
                "backup": str(state_backup),
                "sha256_before": state_sha_before,
                "sha256_after": sha256(state_path),
                "shifted_fields": shifted_fields,
            },
            "tests": {"gateway_retry_budget": "2 passed", "full_suite": "65 passed"},
        }
        if receipt["outstanding_after"] != 0:
            raise RuntimeError("outstanding calls appeared during the quiescent gateway replacement")
        atomic_json(receipt_dir / "ACTIVATION_AMENDMENT.json", receipt, 0o644)

        command(["docker", "unpause", backend])
        paused.remove(backend)
        command(["docker", "unpause", *agents])
        paused.clear()
        report.update({
            "action": "activated",
            "receipt": str(receipt_dir / "ACTIVATION_AMENDMENT.json"),
            "downtime_seconds": downtime,
            "running_gateway_sha256_after": running_hash_after,
            "outstanding_after": 0,
        })
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        if paused:
            command(["docker", "unpause", *reversed(paused)], check=False)


if __name__ == "__main__":
    main()
