#!/usr/bin/env python3
"""Fail-closed watchdog for Authority World LLM experiments.

The watchdog never edits experimental evidence.  When a circuit breaker trips,
it writes a receipt, stops only the explicitly named supervisor/processes, and
then (for world mode) brings down only the Compose project rooted at --root.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_KINDS = {"exchange", "provider_error", "codex_responses_exchange", "codex_provider_error"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def parse_iso(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def append_log(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": now_iso(), **payload}, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def safe_root(value: str) -> Path:
    root = Path(value).resolve()
    forbidden = {Path("/"), Path("/data"), Path("/srv"), Path("/root"), Path("/home")}
    if root in forbidden or "authority" not in root.name.lower():
        raise SystemExit(f"refusing unsafe experiment root: {root}")
    if not root.is_dir():
        raise SystemExit(f"experiment root does not exist: {root}")
    return root


def exact_processes(pattern: str, required_root: Path | None = None) -> list[int]:
    result: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw_bytes = (entry / "cmdline").read_bytes()
            tokens = [part.decode("utf-8", "replace") for part in raw_bytes.split(b"\0") if part]
            raw = " ".join(tokens)
            cwd = Path(os.readlink(entry / "cwd"))
        except OSError:
            continue
        # Script patterns are matched only in the executable/script position.
        # This prevents a watchdog's own --process-pattern argument or the
        # tmux server's launch command from being mistaken for a worker.
        if pattern.endswith((".py", ".sh")):
            candidates = tokens[:2]
            matched = any(Path(token).name == Path(pattern).name for token in candidates)
        else:
            matched = pattern in raw
        if not matched:
            continue
        if required_root is not None:
            path_belongs_to_root = any(
                candidate.is_absolute() and (candidate == required_root or required_root in candidate.parents)
                for candidate in (Path(token) for token in tokens)
            )
            if cwd != required_root and not path_belongs_to_root:
                continue
        pid = int(entry.name)
        if pid != os.getpid():
            result.append(pid)
    return sorted(result)


def terminate_pids(pids: list[int], grace_seconds: float = 10.0) -> list[int]:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.time() + grace_seconds
    remaining = set(pids)
    while remaining and time.time() < deadline:
        remaining = {pid for pid in remaining if Path(f"/proc/{pid}").exists()}
        if remaining:
            time.sleep(0.5)
    for pid in sorted(remaining):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return sorted(remaining)


def tmux_has_session(name: str) -> bool:
    return subprocess.run(["tmux", "has-session", "-t", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def stop_tmux(name: str) -> None:
    if not tmux_has_session(name):
        return
    subprocess.run(["tmux", "send-keys", "-t", f"{name}:0.0", "C-c"], check=False)
    deadline = time.time() + 10
    while tmux_has_session(name) and time.time() < deadline:
        time.sleep(0.5)
    if tmux_has_session(name):
        subprocess.run(["tmux", "kill-session", "-t", name], check=False)


def is_recovery_technical_abort(row: dict[str, Any]) -> bool:
    """Return true only for structured terminals created by audited recovery.

    These records close an interrupted request for charge/terminal accounting;
    they are not provider attempts and must not contribute to provider health
    rate or consecutive-error circuit breakers.
    """
    return (
        row.get("kind") in {"provider_error", "codex_provider_error"}
        and isinstance(row.get("recovery"), dict)
        and str(row.get("request_id", "")).startswith("automatic-recovery-abort:")
        and "technical_abort_at_watchdog_trip" in str(row.get("error", ""))
    )


def recovery_health_boundary(root: Path, run_id: str | None) -> float | None:
    """Return the latest committed recovery boundary for this exact run.

    Provider failures before a committed, provider-probed recovery remain in
    cumulative evidence, but they must not seed a new consecutive-error streak
    before the recovered gateway has produced its first terminal.
    """
    if not run_id:
        return None
    latest: float | None = None
    # Recovery may be a first-pass ``automatic-*`` amendment or an audited
    # rollback of a previously committed bad branch (``rollback-automatic-*``).
    # Filter by amendment contents rather than relying on either directory
    # prefix so the provider health window always starts at the latest commit.
    for path in (root / "recovery").glob("*/RECOVERY_AMENDMENT.json"):
        amendment = read_json(path)
        if amendment is None or amendment.get("status") != "committed":
            continue
        verification = amendment.get("verification")
        if not isinstance(verification, dict) or verification.get("run_id") != run_id:
            continue
        value = amendment.get("resume_epoch")
        boundary = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else parse_iso(amendment.get("committed_at"))
        if boundary is not None and (latest is None or boundary > latest):
            latest = boundary
    return latest


def gateway_summary(path: Path, window_seconds: float, health_cutoff: float | None = None) -> dict[str, Any]:
    rows = read_jsonl(path)
    terminal_records = [
        row
        for row in rows
        if row.get("kind") in {"exchange", "provider_error", "codex_responses_exchange", "codex_provider_error"}
    ]
    recovery_technical_aborts = [row for row in terminal_records if is_recovery_technical_abort(row)]
    provider = [row for row in terminal_records if not is_recovery_technical_abort(row)]
    health_provider = [
        row for row in provider
        if health_cutoff is None or (parse_iso(row.get("at")) or 0) >= health_cutoff
    ]
    recent_cutoff = max(time.time() - window_seconds, health_cutoff or 0)
    recent = [row for row in health_provider if (parse_iso(row.get("at")) or 0) >= recent_cutoff]

    def failed(row: dict[str, Any]) -> bool:
        if row.get("kind") in {"provider_error", "codex_provider_error"}:
            return True
        status = row.get("status")
        return isinstance(status, int) and status >= 400

    consecutive = 0
    for row in reversed(health_provider):
        if failed(row):
            consecutive += 1
        else:
            break
    return {
        # Accounting includes audited technical-abort terminals so completed
        # charged requests never reappear as false outstanding calls.
        "total": len(terminal_records),
        # Health/rate breakers use only actual provider attempts.
        "provider_health_total": len(provider),
        "successes": sum(not failed(row) for row in provider),
        "errors": sum(failed(row) for row in provider),
        "recent_total": len(recent),
        "recent_errors": sum(failed(row) for row in recent),
        "consecutive_errors": consecutive,
        "recovery_technical_aborts": len(recovery_technical_aborts),
        "health_boundary_at": health_cutoff,
        "last_at": parse_iso(health_provider[-1].get("at")) if health_provider else None,
        "last_error": str(health_provider[-1].get("error", ""))[:500] if health_provider and failed(health_provider[-1]) else None,
    }


def terminal_charge_reconciliation(
    event_rows: list[dict[str, Any]],
    gateway_rows: list[dict[str, Any]],
    health_cutoff: float | None = None,
) -> dict[str, Any]:
    """Pair actual provider calls with same-agent terminal gateway records.

    A global ``charges - terminals`` count is incorrect when agents execute
    concurrently, after an audited recovery adds a synthetic terminal, or when
    a model-request charge kills an agent before any provider request is sent.
    Reconcile per agent after the latest committed recovery boundary instead.
    """

    def charge_epoch(row: dict[str, Any]) -> float | None:
        value = row.get("at_wall")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return parse_iso(row.get("at"))

    def gateway_epoch(row: dict[str, Any]) -> float | None:
        value = row.get("at")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return parse_iso(value)

    refund_boundaries = [
        charge_epoch(row)
        for row in event_rows
        if row.get("kind") == "technical_model_request_energy_refunded"
    ]
    boundaries = [value for value in refund_boundaries if value is not None]
    if health_cutoff is not None:
        boundaries.append(health_cutoff)
    boundary = max(boundaries, default=float("-inf"))

    all_charges = [row for row in event_rows if row.get("kind") == "model_request_energy_consumed"]
    eligible_charges: list[dict[str, Any]] = []
    terminal_free_charges: list[dict[str, Any]] = []
    malformed_charges: list[dict[str, Any]] = []
    for charge in all_charges:
        stamp = charge_epoch(charge)
        if stamp is None:
            malformed_charges.append(charge)
            continue
        if stamp <= boundary:
            continue
        data = charge.get("data") if isinstance(charge.get("data"), dict) else {}
        remaining = data.get("remaining")
        if isinstance(remaining, (int, float)) and not isinstance(remaining, bool) and remaining <= 0:
            # The world immediately kills the agent and does not invoke the
            # provider.  Missing a gateway record is therefore expected.
            terminal_free_charges.append(charge)
            continue
        if not isinstance(charge.get("actor"), str):
            malformed_charges.append(charge)
            continue
        eligible_charges.append(charge)

    request_first_activity: dict[str, float] = {}
    for row in gateway_rows:
        request_id = row.get("request_id")
        stamp = gateway_epoch(row)
        if not isinstance(request_id, str) or not request_id or stamp is None:
            continue
        request_first_activity[request_id] = min(request_first_activity.get(request_id, stamp), stamp)

    available_by_agent: dict[str, list[dict[str, Any]]] = {}
    for charge in eligible_charges:
        available_by_agent.setdefault(str(charge["actor"]), []).append(charge)
    for charges in available_by_agent.values():
        charges.sort(key=lambda row: charge_epoch(row) or float("inf"))

    current_terminals: list[dict[str, Any]] = []
    malformed_terminals: list[dict[str, Any]] = []
    for terminal in gateway_rows:
        if terminal.get("kind") not in TERMINAL_KINDS:
            continue
        stamp = gateway_epoch(terminal)
        if stamp is None:
            malformed_terminals.append(terminal)
            continue
        if stamp > boundary:
            current_terminals.append(terminal)
    current_terminals.sort(
        key=lambda row: request_first_activity.get(
            str(row.get("request_id")), gateway_epoch(row) or float("inf")
        )
    )

    used_charge_ids: set[int] = set()
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    orphan_terminals: list[dict[str, Any]] = []
    for terminal in current_terminals:
        request_id = terminal.get("request_id")
        if isinstance(request_id, str) and request_id.startswith("automatic-recovery-abort:"):
            # This closes a pre-boundary call and must never consume a later
            # real charge when the watchdog is restarted.
            orphan_terminals.append(terminal)
            continue
        agent_id = terminal.get("agent_id")
        if not isinstance(agent_id, str):
            malformed_terminals.append(terminal)
            continue
        terminal_at = gateway_epoch(terminal)
        first_activity = request_first_activity.get(str(request_id), terminal_at or float("inf"))
        candidates = [
            charge
            for charge in available_by_agent.get(agent_id, [])
            if id(charge) not in used_charge_ids
            and (charge_epoch(charge) or float("inf")) <= first_activity + 0.001
        ]
        if not candidates:
            orphan_terminals.append(terminal)
            continue
        charge = max(candidates, key=lambda row: charge_epoch(row) or float("-inf"))
        used_charge_ids.add(id(charge))
        pairs.append((charge, terminal))

    unmatched = [charge for charge in eligible_charges if id(charge) not in used_charge_ids]
    return {
        "all_charges": all_charges,
        "eligible_charges": eligible_charges,
        "pairs": pairs,
        "unmatched": unmatched,
        "terminal_free_charges": terminal_free_charges,
        "orphan_terminals": orphan_terminals,
        "malformed_charges": malformed_charges,
        "malformed_terminals": malformed_terminals,
        "health_boundary_epoch": None if boundary == float("-inf") else boundary,
    }


def task_runtime_summary(root: Path, run_id: str | None, cutoff: float) -> dict[str, Any]:
    """Summarize infrastructure-level task failures from real agent receipts."""
    missing: list[dict[str, Any]] = []
    transport_timeouts: list[dict[str, Any]] = []
    if not run_id:
        return {"missing_containers": 0, "transport_timeouts": 0, "samples": []}
    pattern = root / "agent-state-v2"
    for path in pattern.glob(f"*/runner-v2/runs/{run_id}/audit.raw.jsonl"):
        agent_id = path.parts[-5].upper()
        for row in read_jsonl(path):
            stamp = row.get("at")
            if not isinstance(stamp, (int, float)) or isinstance(stamp, bool) or float(stamp) < cutoff:
                continue
            if row.get("kind") != "tool_result":
                continue
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            task_output = result.get("task_output") if isinstance(result.get("task_output"), dict) else {}
            stderr = str(task_output.get("stderr", ""))
            sample = {
                "at": float(stamp),
                "agent_id": agent_id,
                "call_id": row.get("call_id"),
                "name": row.get("name"),
            }
            if "No such container:" in stderr:
                sample["detail"] = stderr.strip()[:300]
                missing.append(sample)
            if row.get("ok") is False:
                error = result.get("error")
                detail = error.get("detail") if isinstance(error, dict) else error
                if str(detail).lower() == "timed out":
                    sample["detail"] = "agent tool transport timed out"
                    transport_timeouts.append(sample)
    samples = sorted(missing + transport_timeouts, key=lambda item: float(item["at"]))[-12:]
    return {
        "missing_containers": len(missing),
        "transport_timeouts": len(transport_timeouts),
        "samples": samples,
    }


def agent_runtime_summary(root: Path, expected: int) -> dict[str, Any]:
    """Require every Compose agent worker to stay running without restarts."""
    listed = subprocess.run(
        [
            "docker", "ps", "-a",
            "--filter", f"label=com.docker.compose.project.working_dir={root}",
            "--format", "{{.ID}}",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0:
        return {
            "expected": expected,
            "observed": 0,
            "healthy": False,
            "samples": [{"error": listed.stderr.strip()[:300]}],
        }
    samples: list[dict[str, Any]] = []
    ignored_nonrunning: list[dict[str, Any]] = []
    observed = 0
    for container_id in (line.strip() for line in listed.stdout.splitlines() if line.strip()):
        inspected = subprocess.run(
            ["docker", "inspect", container_id],
            text=True,
            capture_output=True,
            check=False,
        )
        if inspected.returncode != 0:
            samples.append({"container_id": container_id, "error": inspected.stderr.strip()[:300]})
            continue
        try:
            container = json.loads(inspected.stdout)[0]
        except (IndexError, TypeError, json.JSONDecodeError):
            samples.append({"container_id": container_id, "error": "invalid docker inspect response"})
            continue
        labels = container.get("Config", {}).get("Labels", {})
        service = labels.get("com.docker.compose.service") if isinstance(labels, dict) else None
        if not isinstance(service, str) or not service.startswith("agent_"):
            continue
        state = container.get("State", {})
        status = state.get("Status")
        restarts = int(container.get("RestartCount", 0))
        if status != "running":
            # Compose briefly keeps both the old running container and a new
            # replacement in `created` state while converging `up --build`.
            # Only running workers are part of the live agent runtime.  A
            # missing worker still fails closed through observed < expected;
            # stale or transitional non-running siblings must not turn six
            # healthy workers into a false observed=12 trip.
            ignored_nonrunning.append({
                "container_id": container_id,
                "service": service,
                "status": status,
                "exit_code": state.get("ExitCode"),
                "restart_count": restarts,
            })
            continue
        observed += 1
        if restarts > 0:
            samples.append({
                "container_id": container_id,
                "service": service,
                "status": status,
                "exit_code": state.get("ExitCode"),
                "restart_count": restarts,
            })
    return {
        "expected": expected,
        "observed": observed,
        "healthy": observed == expected and not samples,
        "samples": samples,
        "ignored_nonrunning": len(ignored_nonrunning),
        "ignored_nonrunning_samples": ignored_nonrunning[:12],
    }


def agent_runtime_failure_confirmation(
    summary: dict[str, Any], previous: int, required: int
) -> tuple[int, bool]:
    """Debounce Docker/Compose convergence without masking a missing worker."""
    count = 0 if summary.get("healthy") is True else previous + 1
    return count, count >= max(1, required)


def result_summary(paths: list[Path], field: str, bad_values: set[str], window: int, offsets: list[int] | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, path in enumerate(paths):
        path_rows = read_jsonl(path)
        offset = offsets[index] if offsets is not None and index < len(offsets) else 0
        rows.extend(path_rows[offset:])
    rows.sort(key=lambda row: str(row.get("started_at", "")))
    recent = rows[-window:] if window > 0 else rows

    def failed(row: dict[str, Any]) -> bool:
        return str(row.get(field)) in bad_values

    consecutive = 0
    for row in reversed(rows):
        if failed(row):
            consecutive += 1
        else:
            break
    bad_rows = [row for row in recent if failed(row)]
    signatures: dict[str, int] = {}
    for row in bad_rows:
        signature = str(row.get("error", ""))[:500]
        signatures[signature] = signatures.get(signature, 0) + 1
    return {
        "total": len(rows),
        "window_total": len(recent),
        "window_errors": len(bad_rows),
        "consecutive_errors": consecutive,
        "error_signatures": signatures,
    }


def write_trip(root: Path, reason: str, evidence: dict[str, Any]) -> Path:
    folder = root / "watchdog" / "trips"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    path = folder / f"trip-{stamp}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"schema": "authority-llm-watchdog-trip-v1", "tripped_at": now_iso(), "reason": reason, "evidence": evidence}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def active_env_file(root: Path, fallback: str) -> Path:
    marker = read_json(root / "agent-economics-active-run.json") or {}
    spec = marker.get("spec") if isinstance(marker.get("spec"), dict) else {}
    candidate = spec.get("env_file") if isinstance(spec.get("env_file"), str) else fallback
    return root / candidate


def stop_run_task_containers(run_id: str | None) -> dict[str, Any]:
    """Stop only task containers owned by the tripped world.

    Task containers are daemon-managed siblings, not Compose services.  A
    Compose down therefore does not stop them and is not a complete fail-close.
    """
    if not run_id:
        return {"container_ids": [], "returncode": 0}
    listed = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"label=authority.run_id={run_id}"],
        text=True,
        capture_output=True,
        check=False,
    )
    ids = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    if listed.returncode != 0 or not ids:
        return {"container_ids": ids, "returncode": listed.returncode, "stderr": listed.stderr[-500:]}
    stopped = subprocess.run(
        ["docker", "stop", "-t", "10", *ids],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "container_ids": ids,
        "returncode": stopped.returncode,
        "stdout": stopped.stdout[-500:],
        "stderr": stopped.stderr[-500:],
    }


def trip_world(args: argparse.Namespace, root: Path, reason: str, evidence: dict[str, Any]) -> None:
    receipt = write_trip(root, reason, evidence)
    append_log(args.log, {"kind": "trip", "reason": reason, "receipt": str(receipt), "evidence": evidence})
    if not args.arm:
        append_log(args.log, {"kind": "dry_run_trip_not_enforced"})
        return
    if args.session:
        stop_tmux(args.session)
    worker_pids: list[int] = []
    for pattern in args.process_pattern:
        worker_pids.extend(exact_processes(pattern, root if args.require_root_in_cmdline else None))
    supervisor_pids: list[int] = []
    for pattern in args.supervisor_pattern:
        supervisor_pids.extend(exact_processes(pattern, root if args.require_root_in_cmdline else None))
    forced = terminate_pids(sorted(set(worker_pids + supervisor_pids))) if worker_pids or supervisor_pids else []
    env_file = active_env_file(root, args.env_file)
    compose = root / args.compose_file
    if env_file.is_file() and compose.is_file():
        subprocess.run(["docker", "compose", "--env-file", str(env_file), "-f", str(compose), "down"], cwd=root, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    task_containers = stop_run_task_containers(str(evidence.get("run_id")) if evidence.get("run_id") else None)
    append_log(args.log, {
        "kind": "enforced",
        "session": args.session,
        "worker_pids": sorted(set(worker_pids)),
        "supervisor_pids": sorted(set(supervisor_pids)),
        "forced_kill_pids": forced,
        "compose": str(compose),
        "env_file": env_file.name,
        "task_containers": task_containers,
    })


def world_mode(args: argparse.Namespace) -> int:
    root = safe_root(args.root)
    args.log = Path(args.log or root / "watchdog" / "watchdog.jsonl")
    run_id: str | None = None
    run_seen_at = time.time()
    last_heartbeat = 0.0
    agent_runtime_unhealthy_samples = 0
    while True:
        marker = read_json(root / "agent-economics-active-run.json")
        state_path = root / "data-v2" / "authority-world-v2.state.json"
        events_path = root / "data-v2" / "authority-world-v2.events.jsonl"
        gateway_path = root / "gateway-data-v2" / "authority-world-v1.gateway.jsonl"
        state = read_json(state_path)
        current_id = str(state.get("run_id")) if state and state.get("run_id") else None
        if current_id != run_id:
            run_id = current_id
            run_seen_at = time.time()
            agent_runtime_unhealthy_samples = 0
            append_log(args.log, {"kind": "run_change", "run_id": run_id, "active_marker": marker is not None})
        if marker is None or state is None or state.get("status") not in {"scheduled", "running"}:
            time.sleep(args.interval)
            continue

        events = read_jsonl(events_path)
        health_boundary = recovery_health_boundary(root, run_id)
        summary = gateway_summary(
            gateway_path,
            args.rate_window_seconds,
            health_boundary,
        )
        reconciliation = terminal_charge_reconciliation(
            events,
            read_jsonl(gateway_path),
            health_boundary,
        )
        charges = reconciliation["all_charges"]
        outstanding_charges = reconciliation["unmatched"]
        outstanding = len(outstanding_charges)
        oldest_outstanding_age = 0.0
        if outstanding:
            timestamps = [
                float(row["at_wall"])
                if isinstance(row.get("at_wall"), (int, float)) and not isinstance(row.get("at_wall"), bool)
                else parse_iso(row.get("at"))
                for row in outstanding_charges
            ]
            valid = [value for value in timestamps if value is not None]
            if valid:
                oldest_outstanding_age = max(0.0, time.time() - min(valid))
        last_event_age = time.time() - events_path.stat().st_mtime if events_path.exists() else float("inf")
        recent_total = int(summary["recent_total"])
        recent_errors = int(summary["recent_errors"])
        task_runtime = task_runtime_summary(
            root,
            run_id,
            max(run_seen_at, time.time() - args.task_error_window_seconds),
        )
        agent_runtime = agent_runtime_summary(root, args.expected_agent_containers)
        agent_runtime_unhealthy_samples, agent_runtime_failure_confirmed = (
            agent_runtime_failure_confirmation(
                agent_runtime,
                agent_runtime_unhealthy_samples,
                args.agent_runtime_failure_samples,
            )
        )
        agent_runtime["consecutive_unhealthy_samples"] = agent_runtime_unhealthy_samples
        agent_runtime["required_unhealthy_samples"] = args.agent_runtime_failure_samples
        evidence = {
            "run_id": run_id,
            "world_status": state.get("status"),
            "day": state.get("day"),
            "event_seq": state.get("event_seq"),
            "charged_calls": len(charges),
            "gateway": summary,
            "outstanding_calls": outstanding,
            "oldest_outstanding_seconds": round(oldest_outstanding_age, 3),
            "reconciliation": {
                "eligible_charges": len(reconciliation["eligible_charges"]),
                "paired_calls": len(reconciliation["pairs"]),
                "terminal_free_lethal_charges": len(reconciliation["terminal_free_charges"]),
                "orphan_terminals": len(reconciliation["orphan_terminals"]),
                "malformed_charges": len(reconciliation["malformed_charges"]),
                "malformed_terminals": len(reconciliation["malformed_terminals"]),
                "health_boundary_epoch": reconciliation["health_boundary_epoch"],
                "outstanding_samples": [
                    {"seq": row.get("seq"), "actor": row.get("actor"), "at_wall": row.get("at_wall")}
                    for row in outstanding_charges[:12]
                ],
            },
            "last_event_age_seconds": round(last_event_age, 3),
            "task_runtime": task_runtime,
            "agent_runtime": agent_runtime,
        }
        grace_over = time.time() - run_seen_at >= args.startup_grace_seconds
        reason: str | None = None
        if grace_over and int(summary["consecutive_errors"]) >= args.max_consecutive_errors:
            reason = "consecutive_provider_errors"
        elif grace_over and recent_total >= args.min_rate_window_calls and recent_errors / recent_total >= args.max_error_rate:
            reason = "provider_error_rate"
        elif grace_over and outstanding and oldest_outstanding_age >= args.max_outstanding_seconds:
            reason = "provider_call_deadlock_or_timeout"
        elif grace_over and last_event_age >= args.max_stall_seconds:
            reason = "world_event_stall"
        elif grace_over and int(task_runtime["missing_containers"]) >= args.max_missing_containers:
            reason = "task_container_missing"
        elif grace_over and int(task_runtime["transport_timeouts"]) >= args.max_task_transport_timeouts:
            reason = "task_tool_transport_timeout"
        elif grace_over and agent_runtime_failure_confirmed:
            reason = "agent_runtime_unhealthy"
        elif recent_total > args.max_calls_per_window:
            reason = "api_call_rate_runaway"
        if reason:
            trip_world(args, root, reason, evidence)
            return 2
        if time.time() - last_heartbeat >= args.heartbeat_seconds:
            append_log(args.log, {"kind": "healthy", **evidence})
            last_heartbeat = time.time()
        time.sleep(args.interval)


def trip_process(args: argparse.Namespace, root: Path, reason: str, evidence: dict[str, Any]) -> None:
    receipt = write_trip(root, reason, evidence)
    append_log(args.log, {"kind": "trip", "reason": reason, "receipt": str(receipt), "evidence": evidence})
    if not args.arm:
        append_log(args.log, {"kind": "dry_run_trip_not_enforced"})
        return
    worker_pids = exact_processes(args.process_pattern, root if args.require_root_in_cmdline else None)
    supervisor_pids: list[int] = []
    for pattern in args.supervisor_pattern:
        supervisor_pids.extend(exact_processes(pattern, root if args.require_root_in_cmdline else None))
    forced = terminate_pids(sorted(set(worker_pids + supervisor_pids)))
    append_log(args.log, {"kind": "enforced", "worker_pids": worker_pids, "supervisor_pids": sorted(set(supervisor_pids)), "forced_kill_pids": forced})


def process_mode(args: argparse.Namespace) -> int:
    root = safe_root(args.root)
    args.log = Path(args.log or root / "watchdog" / "process-watchdog.jsonl")
    progress = [Path(value) for value in args.progress_file]
    gateway = Path(args.gateway_audit) if args.gateway_audit else None
    result_paths = [Path(value) for value in args.result_jsonl]
    result_offsets = [len(read_jsonl(path)) for path in result_paths] if args.ignore_existing_results else None
    started = time.time()
    last_heartbeat = 0.0
    last_progress_signature: tuple[tuple[int, int], ...] | None = None
    last_progress_at = time.time()
    while True:
        pids = exact_processes(args.process_pattern, root if args.require_root_in_cmdline else None)
        signature = tuple((path.stat().st_size, path.stat().st_mtime_ns) if path.exists() else (0, 0) for path in progress)
        if signature != last_progress_signature:
            last_progress_signature = signature
            last_progress_at = time.time()
        summary = gateway_summary(gateway, args.rate_window_seconds) if gateway else {"total": 0, "recent_total": 0, "recent_errors": 0, "consecutive_errors": 0}
        results = result_summary(result_paths, args.result_error_field, set(args.result_error_value), args.result_window, result_offsets) if result_paths else {"total": 0, "window_total": 0, "window_errors": 0, "consecutive_errors": 0, "error_signatures": {}}
        evidence = {
            "worker_pids": pids,
            "progress": {str(path): {"size": sig[0], "mtime_ns": sig[1]} for path, sig in zip(progress, signature)},
            "progress_stall_seconds": round(time.time() - last_progress_at, 3),
            "gateway": summary,
            "results": results,
        }
        grace_over = time.time() - started >= args.startup_grace_seconds
        reason: str | None = None
        recent_total = int(summary.get("recent_total", 0))
        recent_errors = int(summary.get("recent_errors", 0))
        if grace_over and int(summary.get("consecutive_errors", 0)) >= args.max_consecutive_errors:
            reason = "consecutive_provider_errors"
        elif grace_over and recent_total >= args.min_rate_window_calls and recent_errors / recent_total >= args.max_error_rate:
            reason = "provider_error_rate"
        elif grace_over and pids and time.time() - last_progress_at >= args.max_stall_seconds:
            reason = "solver_progress_stall"
        elif grace_over and int(results.get("consecutive_errors", 0)) >= args.max_consecutive_result_errors:
            reason = "consecutive_result_level_technical_errors"
        elif grace_over and int(results.get("window_total", 0)) >= args.min_result_window and int(results.get("window_errors", 0)) / int(results["window_total"]) >= args.max_result_error_rate:
            reason = "result_level_technical_error_rate"
        elif recent_total > args.max_calls_per_window:
            reason = "api_call_rate_runaway"
        if reason:
            trip_process(args, root, reason, evidence)
            return 2
        if not pids and grace_over:
            append_log(args.log, {"kind": "workers_complete", **evidence})
            return 0
        if time.time() - last_heartbeat >= args.heartbeat_seconds:
            append_log(args.log, {"kind": "healthy", **evidence})
            last_heartbeat = time.time()
        time.sleep(args.interval)


def freeze_mode(args: argparse.Namespace) -> int:
    """Create and enforce an explicit audited freeze for a named repair."""
    root = safe_root(args.root)
    args.log = Path(args.log or root / "watchdog" / "watchdog.jsonl")
    state = read_json(root / "data-v2" / "authority-world-v2.state.json")
    marker = read_json(root / "agent-economics-active-run.json")
    if state is None or marker is None or state.get("status") not in {"scheduled", "running"}:
        raise SystemExit("refusing repair freeze without one active world")
    evidence = {
        "run_id": state.get("run_id"),
        "world_status": state.get("status"),
        "day": state.get("day"),
        "event_seq": state.get("event_seq"),
        "repair_note": args.repair_note,
    }
    trip_world(args, root, args.reason, evidence)
    return 2


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", required=True)
    parser.add_argument("--log")
    parser.add_argument("--interval", type=float, default=15)
    parser.add_argument("--heartbeat-seconds", type=float, default=60)
    parser.add_argument("--startup-grace-seconds", type=float, default=180)
    parser.add_argument("--max-consecutive-errors", type=int, default=6)
    parser.add_argument("--max-error-rate", type=float, default=0.5)
    parser.add_argument("--min-rate-window-calls", type=int, default=6)
    parser.add_argument("--rate-window-seconds", type=float, default=900)
    parser.add_argument("--max-calls-per-window", type=int, default=180)
    parser.add_argument("--max-stall-seconds", type=float, default=900)
    parser.add_argument("--arm", action="store_true", help="enforce trips; without this flag the watchdog only records them")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="mode", required=True)
    world = sub.add_parser("world")
    common(world)
    world.add_argument("--session")
    world.add_argument("--process-pattern", action="append", default=[])
    world.add_argument("--supervisor-pattern", action="append", default=[])
    world.add_argument("--require-root-in-cmdline", action="store_true")
    world.add_argument("--compose-file", default="docker-compose.v2.fallback.yml")
    world.add_argument("--env-file", default=".env.gpt55")
    world.add_argument("--max-outstanding-seconds", type=float, default=300)
    world.add_argument("--task-error-window-seconds", type=float, default=900)
    world.add_argument("--max-missing-containers", type=int, default=1)
    world.add_argument("--max-task-transport-timeouts", type=int, default=3)
    world.add_argument("--expected-agent-containers", type=int, default=6)
    world.add_argument("--agent-runtime-failure-samples", type=int, default=3)
    process = sub.add_parser("process")
    common(process)
    process.add_argument("--process-pattern", required=True)
    process.add_argument("--supervisor-pattern", action="append", default=[])
    process.add_argument("--progress-file", action="append", required=True)
    process.add_argument("--gateway-audit")
    process.add_argument("--result-jsonl", action="append", default=[])
    process.add_argument("--result-error-field", default="stop_reason")
    process.add_argument("--result-error-value", action="append", default=["technical_error"])
    process.add_argument("--result-window", type=int, default=12)
    process.add_argument("--min-result-window", type=int, default=6)
    process.add_argument("--max-consecutive-result-errors", type=int, default=4)
    process.add_argument("--max-result-error-rate", type=float, default=0.5)
    process.add_argument("--ignore-existing-results", action="store_true")
    process.add_argument("--require-root-in-cmdline", action="store_true")
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--root", required=True)
    freeze.add_argument("--log")
    freeze.add_argument("--session")
    freeze.add_argument("--process-pattern", action="append", default=[])
    freeze.add_argument("--supervisor-pattern", action="append", default=[])
    freeze.add_argument("--require-root-in-cmdline", action="store_true")
    freeze.add_argument("--compose-file", default="docker-compose.v2.fallback.yml")
    freeze.add_argument("--env-file", default=".env.gpt55")
    freeze.add_argument("--reason", default="manual_runtime_repair")
    freeze.add_argument("--repair-note", required=True)
    freeze.add_argument("--arm", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    if args.mode == "world":
        return world_mode(args)
    if args.mode == "process":
        return process_mode(args)
    return freeze_mode(args)


if __name__ == "__main__":
    sys.exit(main())
