#!/usr/bin/env python3
"""Run and archive the registered Agent Economics worlds one at a time.

The discovery phase never injects messages, allocations, transfers or actions.
It only starts immutable worlds, waits for a terminal state, and archives their
complete traces. Mechanism-validation conditions require an explicit flag so
they cannot be confused with undisturbed discovery runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "experiments/agent_economics_protocol.json"
COMPOSE = ROOT / "docker-compose.v2.fallback.yml"
STATE = ROOT / "data-v2/authority-world-v2.state.json"
EVENTS = ROOT / "data-v2/authority-world-v2.events.jsonl"
ACTIVE = ROOT / "agent-economics-active-run.json"
EVIDENCE_STATUS = ROOT / "data-v2/EVIDENCE_STATUS.json"


def log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"[{stamp}] {message}", flush=True)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def compose(env_file: Path, config: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WORLD_CONFIG_FILE"] = Path(config).name
    command = ["docker", "compose", "--env-file", str(env_file), "-f", str(COMPOSE), *args]
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=check)


def wait_health(env_file: Path, config: str, timeout: float = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = compose(env_file, config, "exec", "-T", "backend", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health',timeout=3).read()", check=False)
        if result.returncode == 0:
            return
        time.sleep(2)
    raise RuntimeError("backend health timeout")


def healthy(env_file: Path, config: str) -> bool:
    result = compose(
        env_file,
        config,
        "exec",
        "-T",
        "backend",
        "python",
        "-c",
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health',timeout=3).read()",
        check=False,
    )
    return result.returncode == 0


def start_world(seed: int, env_file: Path, config: str, delay: float = 45) -> dict[str, Any]:
    """Start through backend loopback so host port publishing is irrelevant."""
    code = (
        "import json,os,urllib.request;"
        "body=json.dumps({'seed':int(os.environ['START_SEED']),'start_delay_seconds':float(os.environ['START_DELAY'])}).encode();"
        "req=urllib.request.Request('http://127.0.0.1:8100/v2/control/start',data=body,method='POST',"
        "headers={'Content-Type':'application/json','X-World-Control-Token':os.environ['WORLD_CONTROL_TOKEN']});"
        "print(urllib.request.urlopen(req,timeout=20).read().decode())"
    )
    result = compose(
        env_file,
        config,
        "exec",
        "-T",
        "-e",
        f"START_SEED={seed}",
        "-e",
        f"START_DELAY={delay}",
        "backend",
        "python",
        "-c",
        code,
    )
    accepted = json.loads(result.stdout)
    if not isinstance(accepted, dict):
        raise RuntimeError("backend returned a non-object start response")
    return accepted


def provider_probe(env_file: Path) -> dict[str, Any]:
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL"):
        if not values.get(key):
            raise RuntimeError(f"provider probe is missing {key}")
    style = values.get("OPENAI_API_STYLE", "responses").lower()
    if style == "chat_completions":
        endpoint = "/chat/completions"
        payload = {"model": values["MODEL"], "messages": [{"role": "user", "content": "Reply OK."}], "max_tokens": 8, "stream": False}
    elif style == "responses":
        endpoint = "/responses"
        payload = {"model": values["MODEL"], "input": "Reply OK.", "max_output_tokens": 8, "store": False}
    else:
        raise RuntimeError(f"unsupported provider API style: {style}")
    request = urllib.request.Request(
        values["OPENAI_BASE_URL"].rstrip("/") + endpoint,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + values["OPENAI_API_KEY"]},
    )
    started = time.time()
    with urllib.request.urlopen(request, timeout=45) as response:
        response.read()
        if response.status != 200:
            raise RuntimeError(f"provider probe returned HTTP {response.status}")
    return {"ok": True, "style": style, "model": values["MODEL"], "elapsed_seconds": round(time.time() - started, 3)}


def archive(target: Path, metadata: dict[str, Any]) -> None:
    target.mkdir(parents=True, exist_ok=False)
    (target / "run_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for name in ("data-v2", "agent-state-v2", "gateway-data-v2"):
        source = ROOT / name
        if source.exists():
            shutil.move(str(source), target / name)
        source.mkdir(parents=True, exist_ok=True)
    for number in range(1, 7):
        (ROOT / "agent-state-v2" / f"a{number}").mkdir(parents=True, exist_ok=True)
    run_id = metadata.get("run_id")
    if isinstance(run_id, str) and run_id:
        archive_recovery_evidence(target, run_id)


def archive_recovery_evidence(target: Path, run_id: str) -> None:
    """Co-locate committed recovery provenance with the archived world."""
    matches: list[tuple[Path, dict[str, Any]]] = []
    for amendment_path in sorted((ROOT / "recovery").glob("automatic-*/RECOVERY_AMENDMENT.json")):
        try:
            amendment = load_json(amendment_path)
        except Exception:
            continue
        verification = amendment.get("verification")
        if (
            amendment.get("status") == "committed"
            and isinstance(verification, dict)
            and verification.get("run_id") == run_id
        ):
            matches.append((amendment_path, amendment))
    if not matches:
        return

    summaries: list[dict[str, Any]] = []
    recovery_target = target / "technical-recovery"
    recovery_target.mkdir(exist_ok=True)
    for amendment_path, amendment in matches:
        source = amendment_path.parent
        destination = recovery_target / source.name
        destination.mkdir(exist_ok=False)
        copied: dict[str, str] = {}
        for name in ("RECOVERY_AMENDMENT.json", "auto-recovery-controller.py", "trip.json"):
            candidate = source / name
            if candidate.is_file():
                shutil.copy2(candidate, destination / name)
                copied[name] = hashlib.sha256(candidate.read_bytes()).hexdigest()
        summaries.append({
            "directory": str(Path("technical-recovery") / source.name),
            "classification": amendment.get("classification"),
            "status": amendment.get("status"),
            "source_trip": amendment.get("source_trip"),
            "downtime_seconds": amendment.get("downtime_seconds"),
            "logical_freeze_adjustment": amendment.get("logical_freeze_adjustment"),
            "verification": amendment.get("verification"),
            "sha256": copied,
        })

    evidence_path = target / "data-v2/EVIDENCE_STATUS.json"
    if not evidence_path.is_file():
        raise RuntimeError("committed recovery exists but archived evidence status is missing")
    original_path = evidence_path.with_name("EVIDENCE_STATUS.pre-technical-recovery-amendment.json")
    shutil.copy2(evidence_path, original_path)
    evidence = load_json(evidence_path)
    evidence["evidence_classification"] = "clean_candidate_with_technical_recovery_amendment"
    evidence["eligibility"] = "pending terminal clean-evidence audit and technical-recovery amendment review"
    evidence["recovery_amendments"] = summaries
    temporary = evidence_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(evidence_path)


def write_active(spec: dict[str, Any], accepted: dict[str, Any]) -> None:
    payload = {"spec": spec, "accepted": accepted, "created_at": time.time()}
    temporary = ACTIVE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(ACTIVE)


def write_clean_candidate(spec: dict[str, Any], accepted: dict[str, Any]) -> None:
    run_id = accepted.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("cannot initialize evidence status without a run ID")
    payload = {
        "schema": "authority-agent-economics-evidence-status-v1",
        "run_id": run_id,
        "evidence_classification": "clean_candidate",
        "clean_rerun_required": False,
        "started_at_epoch": time.time(),
        "source_spec": spec,
        "runtime_repair": {
            "backend_app_v2_sha256": hashlib.sha256((ROOT / "backend/app_v2.py").read_bytes()).hexdigest(),
            "artifact_runtime_sha256": hashlib.sha256((ROOT / "backend/artifact_runtime.py").read_bytes()).hexdigest(),
            "agent_runner_v2_sha256": hashlib.sha256((ROOT / "agent/runner_v2.py").read_bytes()).hexdigest(),
            "required_policy": "scoped_run_cleanup_and_bounded_parallel_per_task_serial",
        },
        "eligibility": "pending terminal clean-evidence audit",
    }
    EVIDENCE_STATUS.parent.mkdir(parents=True, exist_ok=True)
    temporary = EVIDENCE_STATUS.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(EVIDENCE_STATUS)


def validate_clean_candidate(accepted: dict[str, Any]) -> None:
    status = load_json(EVIDENCE_STATUS)
    if status.get("run_id") != accepted.get("run_id") or status.get("evidence_classification") != "clean_candidate":
        raise RuntimeError("resumed clean series lacks its matching clean_candidate evidence status")


def read_active(spec: dict[str, Any]) -> dict[str, Any] | None:
    if not ACTIVE.exists():
        return None
    payload = load_json(ACTIVE)
    if payload.get("spec") != spec:
        raise RuntimeError(f"active run marker belongs to a different registered run: {ACTIVE}")
    accepted = payload.get("accepted")
    if not isinstance(accepted, dict) or not isinstance(accepted.get("run_id"), str):
        raise RuntimeError(f"invalid active run marker: {ACTIVE}")
    return accepted


def validate_resumed_state(spec: dict[str, Any], accepted: dict[str, Any]) -> dict[str, Any]:
    state = load_json(STATE)
    if state.get("run_id") != accepted.get("run_id"):
        raise RuntimeError("active marker and durable world state have different run ids")
    if state.get("seed") != spec.get("seed"):
        raise RuntimeError("active marker and durable world state have different seeds")
    if accepted.get("config_hash") and state.get("config_hash") != accepted.get("config_hash"):
        raise RuntimeError("active marker and durable world state have different config hashes")
    return state


def registered_runs(protocol: dict[str, Any], phase: str, replicates: int | None) -> list[dict[str, Any]]:
    if phase == "discovery-pilot":
        block = protocol["discovery"]
        return [{"phase": phase, "model": model["id"], "env_file": model["env_file"], "config": block["config"], "seed": seed} for model in block["models"] for seed in block["pilot_seeds"]]
    if phase == "discovery-confirmatory":
        block = protocol["discovery"]
        count = replicates if replicates is not None else block["confirmatory_replicates_per_model"]
        if not isinstance(count, int) or count < 2:
            raise RuntimeError("confirmatory replicate count must be frozen from pilot power analysis")
        return [{"phase": phase, "model": model["id"], "env_file": model["env_file"], "config": block["config"], "seed": int(block["confirmatory_seed_base"]) + model_index * 10_000 + index} for model_index, model in enumerate(block["models"]) for index in range(1, count + 1)]
    if phase == "mechanism-validation":
        block = protocol.get("mechanism_validation", {})
        if block.get("status") != "frozen_after_discovery":
            raise RuntimeError("mechanism validation requires a separately frozen post-discovery protocol")
        count = replicates if replicates is not None else block.get("replicates_per_model")
        conditions = block.get("conditions")
        models = block.get("models")
        if not isinstance(count, int) or count < 2:
            raise RuntimeError("mechanism replicate count must be an integer of at least two")
        if not isinstance(conditions, list) or not conditions:
            raise RuntimeError("frozen mechanism protocol has no conditions")
        if not isinstance(models, list) or not models:
            raise RuntimeError("frozen mechanism protocol has no models")
        result = []
        seed_base = int(block["seed_base"])
        for condition_index, condition in enumerate(conditions):
            if not isinstance(condition, dict) or not all(isinstance(condition.get(key), str) for key in ("id", "config", "estimand")):
                raise RuntimeError("each mechanism condition requires id, config and estimand strings")
            for model_index, model in enumerate(models):
                for index in range(1, count + 1):
                    result.append({
                        "phase": phase,
                        "condition": condition["id"],
                        "estimand": condition["estimand"],
                        "model": model["id"],
                        "env_file": model["env_file"],
                        "config": condition["config"],
                        "seed": seed_base + condition_index * 100_000 + model_index * 10_000 + index,
                    })
        return result
    raise RuntimeError(f"unsupported phase: {phase}")


def select_registered_seeds(runs: list[dict[str, Any]], only_seeds: list[int] | None) -> list[dict[str, Any]]:
    """Select an explicitly preregistered subset for infrastructure reruns.

    This leaves the frozen protocol intact and refuses seeds that are not in
    it.  It is intended for replacing individually invalidated worlds without
    repeating already-valid replicates.
    """
    if not only_seeds:
        return runs
    requested = set(only_seeds)
    available = {int(run["seed"]) for run in runs}
    unknown = sorted(requested - available)
    if unknown:
        raise RuntimeError(f"requested seed is not preregistered for this phase: {unknown}")
    return [run for run in runs if int(run["seed"]) in requested]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--phase", choices=("discovery-pilot", "discovery-confirmatory", "mechanism-validation"), required=True)
    parser.add_argument("--replicates", type=int)
    parser.add_argument("--results", type=Path, default=ROOT / "agent-economics-results")
    parser.add_argument("--poll-seconds", type=float, default=10)
    parser.add_argument("--only-seed", action="append", type=int, dest="only_seeds")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    protocol = load_json(args.protocol)
    protocol_hash = hashlib.sha256(args.protocol.read_bytes()).hexdigest()
    runs = select_registered_seeds(
        registered_runs(protocol, args.phase, args.replicates),
        args.only_seeds,
    )
    if args.dry_run:
        print(json.dumps({"schema": protocol["schema"], "runs": runs, "resources": protocol["resources"]}, indent=2))
        return
    args.results.mkdir(parents=True, exist_ok=True)
    registry = args.results / "run_registry.jsonl"
    for spec in runs:
        condition = f'-{spec["condition"]}' if spec.get("condition") else ""
        target = args.results / f'{spec["phase"]}{condition}-{spec["model"]}-{spec["seed"]}'
        if target.exists():
            if ACTIVE.exists() and not STATE.exists() and not EVENTS.exists():
                marker = load_json(ACTIVE)
                if marker.get("spec") == spec:
                    ACTIVE.unlink()
            continue
        env_file = ROOT / spec["env_file"]
        if not env_file.exists():
            raise RuntimeError(f"missing provider environment file: {env_file}")
        accepted = read_active(spec)
        resuming = accepted is not None
        if resuming:
            if not STATE.exists() or not EVENTS.exists():
                raise RuntimeError("active run marker exists but durable world data is incomplete")
            validate_resumed_state(spec, accepted)
            validate_clean_candidate(accepted)
        elif STATE.exists() or EVENTS.exists():
            raise RuntimeError("unarchived v2 data exists without an active run marker; refusing to mix worlds")
        if not resuming:
            probe = provider_probe(env_file)
            log(f"provider preflight passed model={probe['model']} style={probe['style']} elapsed={probe['elapsed_seconds']}s")
        compose(env_file, spec["config"], "up", "-d", "--build")
        try:
            wait_health(env_file, spec["config"])
            if not resuming:
                accepted = start_world(spec["seed"], env_file, spec["config"])
                write_active(spec, accepted)
                write_clean_candidate(spec, accepted)
                log(f"started {spec['phase']} model={spec['model']} seed={spec['seed']} run_id={accepted['run_id']}")
            else:
                log(f"resumed {spec['phase']} model={spec['model']} seed={spec['seed']} run_id={accepted['run_id']}")
            assert accepted is not None
            health_failures = 0
            last_progress: tuple[Any, Any] | None = None
            while True:
                if not STATE.exists():
                    time.sleep(args.poll_seconds); continue
                state = load_json(STATE)
                progress = (state.get("status"), state.get("day"))
                if progress != last_progress:
                    alive = sum(entry.get("status") == "alive" for entry in state.get("agents", {}).values())
                    log(f"progress run_id={state.get('run_id')} status={progress[0]} day={progress[1]} alive={alive}")
                    last_progress = progress
                if state.get("status") in {"scheduled", "running"}:
                    if healthy(env_file, spec["config"]):
                        health_failures = 0
                    else:
                        health_failures += 1
                        if health_failures >= 3:
                            # Restore the same immutable world from its durable
                            # state; this creates no in-world action or resource.
                            compose(env_file, spec["config"], "up", "-d", "--build")
                            wait_health(env_file, spec["config"])
                            validate_resumed_state(spec, accepted)
                            log(f"restored unhealthy stack for run_id={accepted['run_id']} from durable state")
                            health_failures = 0
                    time.sleep(args.poll_seconds); continue
                metadata = {
                    **spec,
                    **accepted,
                    "terminal_status": state.get("status"),
                    "config_hash": state.get("config_hash"),
                    "task_manifest_hash": state.get("task_manifest_hash"),
                    "protocol_hash": protocol_hash,
                    "archived_at": time.time(),
                }
                # Stop writers before moving the append-only evidence tree.
                compose(env_file, spec["config"], "down", check=False)
                archive(target, metadata)
                with registry.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(metadata, sort_keys=True) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                ACTIVE.unlink(missing_ok=True)
                log(f"archived run_id={state.get('run_id')} status={state.get('status')} target={target}")
                if state.get("status") == "technical_failed":
                    raise RuntimeError(f"technical failure archived at {target}; series stopped")
                if state.get("status") != "complete":
                    raise RuntimeError(f"unexpected terminal status {state.get('status')!r} archived at {target}")
                break
        finally:
            compose(env_file, spec["config"], "down", check=False)


if __name__ == "__main__":
    main()
