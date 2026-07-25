#!/usr/bin/env python3
"""Fail-closed automatic recovery for a tripped Authority World v2 lane."""

from __future__ import annotations

import argparse
import atexit
import fcntl
import hashlib
import json
import os
import shutil
import shlex
import stat
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from technical_recovery_policy import (
    provider_error_refund_substring,
    require_provider_error_refund_match,
)


TERMINAL_KINDS = {"exchange", "provider_error", "codex_responses_exchange", "codex_provider_error"}
DEFAULT_REASONS = {
    "provider_call_deadlock_or_timeout",
    "consecutive_provider_errors",
    "provider_error_rate",
    "world_event_stall",
    "task_container_missing",
    "task_tool_transport_timeout",
    "manual_runtime_repair",
    "host_disk_hard_limit",
}


def iso_now() -> str:
    return datetime.now().astimezone().isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def rows(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not path.exists():
        return result
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                result.append(value)
    return result


def atomic_json(path: Path, value: dict[str, Any], mode: int | None = None) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if mode is not None:
        os.chmod(temporary, mode)
    os.replace(temporary, path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def command(args: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def tmux_exists(name: str) -> bool:
    return command(["tmux", "has-session", "-t", name], check=False).returncode == 0


def runner_exit_diagnostic(receipt_path: Path, log_path: Path) -> str:
    """Return bounded, durable evidence when a tmux runner dies at startup."""
    receipt: dict[str, Any] | None = None
    if receipt_path.exists():
        try:
            receipt = load(receipt_path)
        except Exception as error:
            receipt = {"receipt_error": repr(error)}
    tail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:] if log_path.exists() else ""
    return json.dumps({"exit_receipt": receipt, "runner_log_tail": tail}, ensure_ascii=False, sort_keys=True)


def env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def provider_probe(env_path: Path) -> dict[str, Any]:
    values = env_values(env_path)
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


def provider_probe_series(env_path: Path, samples: int, interval: float) -> dict[str, Any]:
    receipts: list[dict[str, Any]] = []
    for index in range(samples):
        receipts.append(provider_probe(env_path))
        if index + 1 < samples:
            time.sleep(interval)
    return {
        "ok": True,
        "required_samples": samples,
        "successful_samples": len(receipts),
        "receipts": receipts,
    }


def latest_recoverable_trip(folder: Path, allowed: set[str]) -> tuple[Path, dict[str, Any]] | None:
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for path in folder.glob("trip-*.json"):
        try:
            value = load(path)
        except Exception:
            continue
        if value.get("reason") in allowed and value.get("schema") == "authority-llm-watchdog-trip-v1":
            candidates.append((path.stat().st_mtime_ns, path, value))
    if not candidates:
        return None
    _, path, value = max(candidates)
    return path, value


def enforced_epoch(
    watchdog_log: Path,
    trip: dict[str, Any],
    trip_path: Path,
    environment_supervisor_log: Path | None = None,
) -> tuple[float, dict[str, Any]]:
    tripped = datetime.fromisoformat(str(trip["tripped_at"])).timestamp()
    for row in rows(watchdog_log):
        if row.get("kind") != "enforced" or not isinstance(row.get("at"), str):
            continue
        stamp = datetime.fromisoformat(row["at"]).timestamp()
        if stamp >= tripped:
            return stamp, {
                "source": "watchdog_log",
                "path": str(watchdog_log),
                "record": row,
            }
    if environment_supervisor_log is not None:
        for row in rows(environment_supervisor_log):
            if row.get("kind") != "global_fail_closed" or not isinstance(row.get("at"), str):
                continue
            if row.get("receipt") != str(trip_path):
                continue
            if row.get("run_id") != trip.get("evidence", {}).get("run_id"):
                continue
            if row.get("reason") != trip.get("reason"):
                continue
            stamp = datetime.fromisoformat(row["at"]).timestamp()
            if stamp >= tripped:
                return stamp, {
                    "source": "environment_supervisor_log",
                    "path": str(environment_supervisor_log),
                    "record": row,
                }
    raise RuntimeError("watchdog log has no enforcement receipt after the trip")


def processed(root: Path, trip_sha: str) -> bool:
    for path in (root / "recovery").glob("automatic-*/RECOVERY_AMENDMENT.json"):
        try:
            amendment = load(path)
            if (
                amendment.get("source_trip", {}).get("sha256") == trip_sha
                and amendment.get("status") in {None, "committed"}
            ):
                return True
        except Exception:
            continue
    return False


def computed_day(state: dict[str, Any], now: float) -> int | None:
    world_start = state.get("world_start_wall")
    if not isinstance(world_start, (int, float)) or isinstance(world_start, bool):
        return None
    return int(max(0.0, now - float(world_start)) // 900) + 1


def logical_freeze_epoch(
    state: dict[str, Any], event_rows: list[dict[str, Any]], enforcement_epoch: float
) -> tuple[float, dict[str, Any] | None]:
    """Keep recovery on the last auditable world day after a stalled rollover.

    The watchdog can only enforce a freeze after its timeout has elapsed.  If
    that interval crosses a 900-second boundary, the persisted state can still
    be on day N while wall-clock arithmetic at enforcement already says N+1.
    Resuming from enforcement would then skip the missing day_started event.
    In that narrow case, use the exact last persisted event as the logical
    freeze point.  The physical enforcement timestamp remains separately
    recorded in the recovery amendment.
    """
    state_day = state.get("day")
    if computed_day(state, enforcement_epoch) == state_day:
        return enforcement_epoch, None

    run_id = state.get("run_id")
    event_seq = state.get("event_seq")
    candidates = [
        row
        for row in event_rows
        if row.get("run_id") == run_id
        and row.get("seq") == event_seq
        and row.get("day") == state_day
        and isinstance(row.get("at_wall"), (int, float))
        and not isinstance(row.get("at_wall"), bool)
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "cannot derive a unique logical freeze point for stalled day rollover: "
            f"run_id={run_id} day={state_day} event_seq={event_seq} matches={len(candidates)}"
        )
    event = candidates[0]
    event_epoch = float(event["at_wall"])
    if event_epoch > enforcement_epoch:
        raise RuntimeError("last persisted event occurs after watchdog enforcement")
    if computed_day(state, event_epoch) != state_day:
        raise RuntimeError(
            "last persisted event is inconsistent with persisted world day: "
            f"state={state_day} computed={computed_day(state, event_epoch)}"
        )
    return event_epoch, {
        "reason": "watchdog_enforcement_crossed_unpersisted_day_boundary",
        "event_seq": event_seq,
        "event_day": state_day,
        "event_at_wall": event_epoch,
        "enforcement_epoch": enforcement_epoch,
        "uncommitted_wall_seconds": enforcement_epoch - event_epoch,
    }


def atomic_restore(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.restore")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def terminal_charge_reconciliation(
    event_rows: list[dict[str, Any]], gateway_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Reconcile calls after the latest auditable recovery health boundary.

    Terminal rows do not carry the event sequence of their charge.  We map a
    terminal to the latest unused same-agent charge before that request's first
    gateway activity.  This handles cross-agent concurrency and same-agent
    overlap.  Previous technical-abort rows are excluded: their charge was
    already closed by an audited refund at the health boundary.

    A charge whose recorded remaining energy is non-positive is also excluded
    from outstanding calls.  The world kills that agent immediately and never
    sends a provider request, so the absence of a gateway terminal is expected.
    """
    charges = [row for row in event_rows if row.get("kind") == "model_request_energy_consumed"]
    terminals = [row for row in gateway_rows if row.get("kind") in TERMINAL_KINDS]

    def charge_epoch(row: dict[str, Any]) -> float:
        value = row.get("at_wall")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError(f"charged model request has no numeric at_wall: seq={row.get('seq')}")
        return float(value)

    def terminal_epoch(row: dict[str, Any]) -> float:
        value = row.get("at")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            return datetime.fromisoformat(value).timestamp()
        raise RuntimeError(f"provider terminal has no parseable timestamp: request_id={row.get('request_id')}")

    refund_boundaries = [
        float(row["at_wall"])
        for row in event_rows
        if row.get("kind") == "technical_model_request_energy_refunded"
        and isinstance(row.get("at_wall"), (int, float))
        and not isinstance(row.get("at_wall"), bool)
    ]
    health_boundary = max(refund_boundaries, default=float("-inf"))
    terminal_free_charges: list[dict[str, Any]] = []
    eligible_charges: list[dict[str, Any]] = []
    for charge in charges:
        if charge_epoch(charge) <= health_boundary:
            continue
        remaining = charge.get("data", {}).get("remaining") if isinstance(charge.get("data"), dict) else None
        if isinstance(remaining, (int, float)) and not isinstance(remaining, bool) and remaining <= 0:
            terminal_free_charges.append(charge)
            continue
        if not isinstance(charge.get("actor"), str):
            raise RuntimeError("charged model request lacks an actor")
        eligible_charges.append(charge)

    request_first_activity: dict[str, float] = {}
    for row in gateway_rows:
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            continue
        try:
            row_epoch = terminal_epoch(row)
        except RuntimeError:
            continue
        request_first_activity[request_id] = min(request_first_activity.get(request_id, row_epoch), row_epoch)

    available_by_agent: dict[str, list[dict[str, Any]]] = {}
    for charge in eligible_charges:
        available_by_agent.setdefault(str(charge["actor"]), []).append(charge)
    for agent_charges in available_by_agent.values():
        agent_charges.sort(key=charge_epoch)

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    orphan_terminals: list[dict[str, Any]] = []
    used_charge_ids: set[int] = set()
    current_terminals = [row for row in terminals if terminal_epoch(row) > health_boundary]
    current_terminals.sort(
        key=lambda row: request_first_activity.get(str(row.get("request_id")), terminal_epoch(row))
    )
    for terminal in current_terminals:
        request_id = terminal.get("request_id")
        if isinstance(request_id, str) and request_id.startswith("automatic-recovery-abort:"):
            orphan_terminals.append(terminal)
            continue
        agent_id = terminal.get("agent_id")
        if not isinstance(agent_id, str):
            raise RuntimeError("provider terminal lacks an agent_id")
        first_activity = request_first_activity.get(str(request_id), terminal_epoch(terminal))
        candidates = [
            charge for charge in available_by_agent.get(agent_id, [])
            if id(charge) not in used_charge_ids and charge_epoch(charge) <= first_activity + 0.001
        ]
        if not candidates:
            orphan_terminals.append(terminal)
            continue
        charge = max(candidates, key=charge_epoch)
        used_charge_ids.add(id(charge))
        pairs.append((charge, terminal))
    unmatched = [charge for charge in eligible_charges if id(charge) not in used_charge_ids]
    return {
        "charges": charges,
        "terminals": terminals,
        "pairs": pairs,
        "unmatched": unmatched,
        "orphan_terminals": orphan_terminals,
        "terminal_free_charges": terminal_free_charges,
        "health_boundary_epoch": None if health_boundary == float("-inf") else health_boundary,
    }


def attributable_provider_failures(
    reconciliation: dict[str, Any], error_substring: str | None
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if not error_substring:
        return []
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    request_ids: set[str] = set()
    for charge, terminal in reconciliation["pairs"]:
        if terminal.get("kind") not in {"provider_error", "codex_provider_error"}:
            continue
        if error_substring not in str(terminal.get("error", "")):
            continue
        request_id = terminal.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise RuntimeError("attributable provider error lacks request_id")
        if request_id in request_ids:
            raise RuntimeError(f"duplicate attributable provider terminal request_id: {request_id}")
        request_ids.add(request_id)
        selected.append((charge, terminal))
    return selected


def rollback_source_files(root: Path, recovery: Path) -> dict[str, Path]:
    recovery = recovery.resolve()
    recovery_root = (root / "recovery").resolve()
    if recovery.parent != recovery_root:
        raise RuntimeError(f"rollback recovery must be a direct child of {recovery_root}")
    required = {
        "state": recovery / "state.before.json",
        "events": recovery / "events.before.jsonl",
        "gateway": recovery / "gateway.before.jsonl",
        "marker": recovery / "active-run.json",
        "watchdog": recovery / "watchdog.jsonl",
        "trip": recovery / "trip.json",
        "agent_state": recovery / "agent-state-v2.before",
        "amendment": recovery / "RECOVERY_AMENDMENT.json",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise RuntimeError(f"rollback recovery is incomplete: {missing}")
    amendment = load(required["amendment"])
    if amendment.get("status") != "committed":
        raise RuntimeError("rollback source is not a committed recovery")
    return required


def systemd_active(unit: str) -> bool:
    return command(["systemctl", "is-active", "--quiet", unit], check=False).returncode == 0


def quiesce_runtime(root: Path, env_path: Path, run_id: str) -> dict[str, Any]:
    """Stop only this world's compose project and run-labelled task containers."""
    compose_file = root / "docker-compose.v2.fallback.yml"
    receipts: dict[str, Any] = {"compose_file": str(compose_file), "run_id": run_id}
    if compose_file.exists():
        stopped = command(
            [
                "docker", "compose", "--env-file", str(env_path),
                "-f", str(compose_file), "down", "--remove-orphans",
            ],
            cwd=root,
            check=False,
        )
        receipts["compose_down"] = {
            "returncode": stopped.returncode,
            "stdout": stopped.stdout[-4000:],
            "stderr": stopped.stderr[-4000:],
        }
        if stopped.returncode != 0:
            raise RuntimeError(f"failed to quiesce compose project: {stopped.stderr[-2000:]}")
    listed = command(
        ["docker", "ps", "-aq", "--filter", f"label=authority.run_id={run_id}"],
        check=False,
    )
    container_ids = [line.strip() for line in listed.stdout.splitlines() if line.strip()]
    receipts["run_labelled_containers"] = container_ids
    if container_ids:
        stopped_tasks = command(["docker", "stop", *container_ids], check=False)
        receipts["task_stop"] = {
            "returncode": stopped_tasks.returncode,
            "stdout": stopped_tasks.stdout[-4000:],
            "stderr": stopped_tasks.stderr[-4000:],
        }
        if stopped_tasks.returncode != 0:
            raise RuntimeError(f"failed to stop run-labelled task containers: {stopped_tasks.stderr[-2000:]}")
    return receipts


def wait_for_stable_file(path: Path, samples: int = 2, interval: float = 1.0) -> str:
    previous: str | None = None
    stable = 0
    for _ in range(12):
        current = sha256(path)
        if current == previous:
            stable += 1
            if stable >= samples:
                return current
        else:
            stable = 0
        previous = current
        time.sleep(interval)
    raise RuntimeError(f"file did not quiesce after runtime stop: {path}")


def rollback_interrupted_preparation(root: Path) -> dict[str, Any] | None:
    """Recover atomically when a previous controller died before commit.

    A prepared amendment has already shifted the clock and may have appended
    technical-abort terminals.  Retrying on top of it would double-shift time,
    so restore the exact pre-attempt files first while preserving the interrupted
    state as incident evidence.
    """
    candidates = sorted(
        (root / "recovery").glob("automatic-*/RECOVERY_AMENDMENT.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for amendment_path in candidates:
        amendment = load(amendment_path)
        if amendment.get("status") != "prepared":
            continue
        recovery = amendment_path.parent
        required = {
            "state": recovery / "state.before.json",
            "events": recovery / "events.before.jsonl",
            "gateway": recovery / "gateway.before.jsonl",
            "marker": recovery / "active-run.json",
        }
        if not all(path.is_file() for path in required.values()):
            raise RuntimeError(f"prepared recovery lacks rollback files: {recovery}")
        preserved = recovery / "interrupted-after-controller-exit"
        preserved.mkdir(exist_ok=True)
        current = {
            "state": root / "data-v2/authority-world-v2.state.json",
            "events": root / "data-v2/authority-world-v2.events.jsonl",
            "gateway": root / "gateway-data-v2/authority-world-v1.gateway.jsonl",
            "marker": root / "agent-economics-active-run.json",
        }
        for label, path in current.items():
            if path.exists():
                shutil.copy2(path, preserved / f"{label}.json" if label in {"state", "marker"} else preserved / f"{label}.jsonl")
        atomic_restore(required["state"], current["state"])
        atomic_restore(required["events"], current["events"])
        atomic_restore(required["gateway"], current["gateway"])
        atomic_restore(required["marker"], current["marker"])
        amendment["status"] = "rolled_back_after_controller_interruption"
        amendment["rolled_back_at"] = iso_now()
        amendment["interrupted_evidence"] = str(preserved)
        atomic_json(amendment_path, amendment)
        receipt = {
            "schema": "authority-world-v2-prepared-recovery-rollback-v1",
            "at": iso_now(),
            "recovery": str(recovery),
            "restored": {label: str(path) for label, path in required.items()},
            "preserved": str(preserved),
        }
        atomic_json(recovery / "RECOVERY_ROLLED_BACK.json", receipt)
        return receipt
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--runner-session")
    parser.add_argument("--watchdog-session")
    parser.add_argument("--runner-launcher")
    parser.add_argument("--watchdog-launcher")
    parser.add_argument("--systemd-runner-unit")
    parser.add_argument("--systemd-watchdog-unit")
    parser.add_argument("--rollback-recovery", type=Path)
    parser.add_argument("--refund-provider-error-substring")
    parser.add_argument("--env-file", default=".env.gpt55")
    parser.add_argument("--watchdog-log", default="watchdog/watchdog.jsonl")
    parser.add_argument("--environment-supervisor-log", type=Path)
    parser.add_argument("--classification", default="secondary_technical_recovery_not_registered_confirmation")
    parser.add_argument("--hold-file", default="MANUAL_RECOVERY_HOLD.json")
    parser.add_argument("--provider-probe-samples", type=int, default=3)
    parser.add_argument("--provider-probe-interval", type=float, default=5.0)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--allowed-reason", action="append")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    hold_path = root / args.hold_file
    if hold_path.exists():
        print(json.dumps({"ok": True, "action": "none", "reason": "manual_recovery_hold", "hold": str(hold_path)}))
        return
    if args.provider_probe_samples < 1 or args.provider_probe_samples > 10:
        parser.error("--provider-probe-samples must be between 1 and 10")
    if args.provider_probe_interval < 0 or args.provider_probe_interval > 300:
        parser.error("--provider-probe-interval must be between 0 and 300 seconds")
    state_path = root / "data-v2/authority-world-v2.state.json"
    events_path = root / "data-v2/authority-world-v2.events.jsonl"
    gateway_path = root / "gateway-data-v2/authority-world-v1.gateway.jsonl"
    marker_path = root / "agent-economics-active-run.json"
    rollback_files: dict[str, Path] | None = None
    rollback_recovery: Path | None = None
    if args.rollback_recovery is not None:
        rollback_recovery = args.rollback_recovery
        if not rollback_recovery.is_absolute():
            rollback_recovery = root / "recovery" / rollback_recovery
        rollback_files = rollback_source_files(root, rollback_recovery)
        trip_path = rollback_files["trip"]
        trip = load(trip_path)
        watchdog_log = rollback_files["watchdog"]
        state_source = rollback_files["state"]
        events_source = rollback_files["events"]
        gateway_source = rollback_files["gateway"]
        marker_source = rollback_files["marker"]
        state = load(state_source)
        current_state = load(state_path)
        if current_state.get("run_id") != state.get("run_id"):
            raise RuntimeError("committed recovery rollback would change run identity")
    else:
        watchdog_log = Path(args.watchdog_log)
        if not watchdog_log.is_absolute():
            watchdog_log = root / watchdog_log
        allowed = set(args.allowed_reason or DEFAULT_REASONS)
        found = latest_recoverable_trip(root / "watchdog/trips", allowed)
        if found is None:
            print(json.dumps({"ok": True, "action": "none", "reason": "no_recoverable_trip"}))
            return
        trip_path, trip = found
        if processed(root, sha256(trip_path)):
            print(json.dumps({"ok": True, "action": "none", "reason": "trip_already_processed", "trip": str(trip_path)}))
            return
        state_source = state_path
        events_source = events_path
        gateway_source = gateway_path
        marker_source = marker_path
        state = load(state_source)
    trip_sha = sha256(trip_path)
    evidence = trip.get("evidence") if isinstance(trip.get("evidence"), dict) else {}
    if evidence.get("run_id") != state.get("run_id"):
        raise RuntimeError("recoverable trip belongs to a different run")
    marker = load(marker_source)
    spec = marker.get("spec") if isinstance(marker.get("spec"), dict) else {}
    env_file = spec.get("env_file") if args.env_file == "auto" else args.env_file
    if not isinstance(env_file, str) or not env_file:
        raise RuntimeError("active run marker has no provider env_file")
    env_path = root / env_file
    tmux_mode = all((args.runner_session, args.watchdog_session, args.runner_launcher, args.watchdog_launcher))
    systemd_mode = all((args.systemd_runner_unit, args.systemd_watchdog_unit))
    if not args.prepare_only and not (tmux_mode or systemd_mode):
        parser.error("complete tmux or systemd launch arguments are required unless --prepare-only is used")
    if tmux_mode and systemd_mode:
        parser.error("tmux and systemd launch modes are mutually exclusive")
    if tmux_mode and (tmux_exists(str(args.runner_session)) or tmux_exists(str(args.watchdog_session))):
        print(json.dumps({"ok": True, "action": "none", "reason": "lane_is_active", "trip": str(trip_path)}))
        return
    if systemd_mode and (
        systemd_active(str(args.systemd_runner_unit)) or systemd_active(str(args.systemd_watchdog_unit))
    ):
        print(json.dumps({"ok": True, "action": "none", "reason": "lane_is_active", "trip": str(trip_path)}))
        return
    interrupted_rollback = None if rollback_files else rollback_interrupted_preparation(root)
    if interrupted_rollback is not None:
        state = load(state_path)
        evidence = trip.get("evidence") if isinstance(trip.get("evidence"), dict) else {}
        if evidence.get("run_id") != state.get("run_id"):
            raise RuntimeError("trip identity changed after prepared-recovery rollback")
    environment_supervisor_log = args.environment_supervisor_log
    if environment_supervisor_log is not None and not environment_supervisor_log.is_absolute():
        environment_supervisor_log = root / environment_supervisor_log
    enforcement_epoch, enforcement_receipt = enforced_epoch(
        watchdog_log,
        trip,
        trip_path,
        environment_supervisor_log,
    )
    source_events = rows(events_source)
    source_gateway = rows(gateway_source)
    reconciliation = terminal_charge_reconciliation(source_events, source_gateway)
    effective_refund_substring = provider_error_refund_substring(
        trip.get("reason"), args.refund_provider_error_substring
    )
    attributable = attributable_provider_failures(
        reconciliation, effective_refund_substring
    )
    require_provider_error_refund_match(effective_refund_substring, len(attributable))
    freeze_epoch, freeze_adjustment = logical_freeze_epoch(state, source_events, enforcement_epoch)
    probe = provider_probe_series(env_path, args.provider_probe_samples, args.provider_probe_interval)
    refund_plan = [
        {
            "agent_id": charge.get("actor"),
            "charge_seq": charge.get("seq"),
            "amount": charge.get("data", {}).get("amount"),
            "request_id": terminal.get("request_id"),
        }
        for charge, terminal in attributable
    ]
    report = {
        "ok": True,
        "action": "would_recover" if args.dry_run else "recover",
        "trip": str(trip_path),
        "trip_reason": trip.get("reason"),
        "run_id": state.get("run_id"),
        "day": state.get("day"),
        "event_seq": state.get("event_seq"),
        "enforced_at_epoch": enforcement_epoch,
        "enforcement_receipt": enforcement_receipt,
        "logical_freeze_epoch": freeze_epoch,
        "logical_freeze_adjustment": freeze_adjustment,
        "provider_probe": probe,
        "interrupted_preparation_rollback": interrupted_rollback,
        "rollback_recovery": str(rollback_recovery) if rollback_recovery else None,
        "attributable_terminal_refund_plan": refund_plan,
        "attributable_terminal_refund_count": len(refund_plan),
        "provider_error_refund_filter_applied": effective_refund_substring is not None,
        "outstanding_refund_plan": [
            {"agent_id": row.get("actor"), "charge_seq": row.get("seq"), "amount": row.get("data", {}).get("amount")}
            for row in reconciliation["unmatched"]
        ],
    }
    if args.dry_run:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    lock = root / ".automatic-technical-recovery.lock"
    lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        print(json.dumps({"ok": True, "action": "none", "reason": "recovery_already_locked", "trip": str(trip_path)}))
        return
    os.ftruncate(lock_fd, 0)
    os.write(lock_fd, (json.dumps({"pid": os.getpid(), "trip": str(trip_path), "started_at": iso_now()}) + "\n").encode())
    os.fsync(lock_fd)
    runtime_quiescence = quiesce_runtime(root, env_path, str(state.get("run_id")))
    wait_for_stable_file(state_path)
    state_sha_before = sha256(state_source)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    recovery = root / "recovery" / (("rollback-automatic-" if rollback_files else "automatic-") + stamp)
    recovery.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__).resolve(), recovery / "auto-recovery-controller.py")
    for label, source in (("state.before.json", state_source), ("events.before.jsonl", events_source), ("gateway.before.jsonl", gateway_source), ("active-run.json", marker_source), ("watchdog.jsonl", watchdog_log), ("trip.json", trip_path)):
        shutil.copy2(source, recovery / label)
    if environment_supervisor_log is not None:
        shutil.copy2(environment_supervisor_log, recovery / "environment-supervisor.jsonl")
    source_agent_state = rollback_files["agent_state"] if rollback_files else root / "agent-state-v2"
    shutil.copytree(source_agent_state, recovery / "agent-state-v2.before")
    if sha256(state_source) != state_sha_before:
        raise RuntimeError("source state changed during automatic recovery backup")
    invalid_branch: Path | None = None
    if rollback_files:
        invalid_branch = recovery / "invalid-committed-recovery-branch"
        invalid_branch.mkdir()
        for label, current in (
            ("state.json", state_path), ("events.jsonl", events_path),
            ("gateway.jsonl", gateway_path), ("active-run.json", marker_path),
        ):
            shutil.copy2(current, invalid_branch / label)
        shutil.copytree(root / "agent-state-v2", invalid_branch / "agent-state-v2")
        atomic_restore(recovery / "state.before.json", state_path)
        atomic_restore(recovery / "events.before.jsonl", events_path)
        atomic_restore(recovery / "gateway.before.jsonl", gateway_path)
        atomic_restore(recovery / "active-run.json", marker_path)
        current_agent_state = root / "agent-state-v2"
        os.replace(current_agent_state, recovery / "agent-state-v2.invalid-live-branch")
        shutil.copytree(recovery / "agent-state-v2.before", current_agent_state)
        state = load(state_path)

    committed = False
    rollback_running = False

    def rollback_uncommitted_attempt() -> None:
        nonlocal rollback_running
        if committed or rollback_running:
            return
        rollback_running = True
        try:
            quiesce_runtime(root, env_path, str(state.get("run_id")))
            wait_for_stable_file(state_path)
        except Exception:
            # Continue the file rollback even if Docker itself is degraded;
            # the failure receipt and preserved branch remain fail-closed.
            pass
        failure_dir = recovery / "failed-post-recovery"
        failure_dir.mkdir(exist_ok=True)
        for session_name in (args.runner_session, args.watchdog_session):
            if session_name and tmux_exists(session_name):
                command(["tmux", "kill-session", "-t", session_name], check=False)
        for unit_name in (args.systemd_watchdog_unit, args.systemd_runner_unit):
            if unit_name:
                command(["systemctl", "stop", str(unit_name)], check=False)
        for label, current in (
            ("state.after-failure.json", state_path),
            ("events.after-failure.jsonl", events_path),
            ("gateway.after-failure.jsonl", gateway_path),
            ("active-run.after-failure.json", marker_path),
        ):
            if current.exists():
                shutil.copy2(current, failure_dir / label)
        current_agent_state = root / "agent-state-v2"
        failed_agent_state = failure_dir / "agent-state-v2.after-failure"
        if current_agent_state.exists() and not failed_agent_state.exists():
            os.replace(current_agent_state, failed_agent_state)
        shutil.copytree(recovery / "agent-state-v2.before", current_agent_state)
        atomic_restore(recovery / "state.before.json", state_path)
        atomic_restore(recovery / "events.before.jsonl", events_path)
        atomic_restore(recovery / "gateway.before.jsonl", gateway_path)
        atomic_restore(recovery / "active-run.json", marker_path)
        atomic_json(
            recovery / "RECOVERY_FAILED.json",
            {
                "schema": "authority-world-v2-automatic-technical-recovery-failure-v1",
                "at": iso_now(),
                "reason": "controller_exited_before_commit",
                "evidence_preserved_at": str(failure_dir),
                "restored_from": str(recovery),
            },
        )
        amendment_path = recovery / "RECOVERY_AMENDMENT.json"
        if amendment_path.exists():
            failed_amendment = load(amendment_path)
            failed_amendment["status"] = "rolled_back_after_failed_startup"
            failed_amendment["rolled_back_at"] = iso_now()
            failed_amendment["failed_startup_evidence"] = str(failure_dir)
            atomic_json(amendment_path, failed_amendment)

    atexit.register(rollback_uncommitted_attempt)

    current_events = rows(events_path)
    current_gateway = rows(gateway_path)
    reconciliation = terminal_charge_reconciliation(current_events, current_gateway)
    charges = reconciliation["charges"]
    terminals = reconciliation["terminals"]
    outstanding_charges = reconciliation["unmatched"]
    outstanding = len(outstanding_charges)
    abort_records: list[dict[str, Any]] = []
    refund_records: list[dict[str, Any]] = []

    def refund_charge(charge: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        agent_id = charge.get("actor")
        amount = charge.get("data", {}).get("amount") if isinstance(charge.get("data"), dict) else None
        agent = state.get("agents", {}).get(agent_id) if isinstance(state.get("agents"), dict) else None
        if not isinstance(agent_id, str) or not isinstance(agent, dict):
            raise RuntimeError("cannot refund charge without a valid agent")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
            raise RuntimeError("cannot refund charge without a positive amount")
        if not isinstance(agent.get("energy"), (int, float)) or isinstance(agent.get("energy"), bool):
            raise RuntimeError("cannot refund charge without numeric agent energy")
        if agent.get("status") != "alive":
            raise RuntimeError(f"automatic refund would need to revive {agent_id}; refusing ambiguous recovery")
        before_energy = float(agent["energy"])
        agent["energy"] = before_energy + float(amount)
        state["event_seq"] = int(state.get("event_seq", 0)) + 1
        refund = {
            "actor": agent_id,
            "at": datetime.now(timezone.utc).isoformat(),
            "at_wall": time.time(),
            "data": {
                "amount": float(amount), "energy_before": before_energy,
                "energy_after": agent["energy"], "original_charge_seq": charge.get("seq"), **data,
            },
            "day": state.get("day"), "kind": "technical_model_request_energy_refunded",
            "phase": charge.get("phase"), "run_id": state.get("run_id"), "seq": state["event_seq"],
        }
        append_jsonl(events_path, refund)
        refund_records.append(refund)
        return refund

    for charge, terminal in attributable:
        refund_charge(charge, {
            "reason": "attributable_provider_auth_or_quota_trip",
            "provider_error_request_id": terminal.get("request_id"),
            "provider_error_kind": terminal.get("kind"),
            "provider_error_sha256": hashlib.sha256(
                json.dumps(terminal, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest(),
        })

    for index, charge in enumerate(outstanding_charges):
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": "provider_error",
            "request_id": f"automatic-recovery-abort:{state.get('run_id')}:{state.get('event_seq')}:{index}",
            "agent_id": charge.get("actor"),
            "error": "technical_abort_at_watchdog_trip; charged request had no provider terminal record",
            "recovery": {"trip_receipt": str(trip_path), "trip_sha256": trip_sha},
        }
        append_jsonl(gateway_path, record)
        abort_records.append(record)
        refund_charge(charge, {
            "reason": "technical_abort_at_watchdog_trip",
            "technical_abort_request_id": record["request_id"],
        })
    if terminal_charge_reconciliation(rows(events_path), rows(gateway_path))["unmatched"]:
        raise RuntimeError("technical-abort reconciliation did not close the frozen outstanding count")

    resume_epoch = time.time()
    downtime = resume_epoch - freeze_epoch
    shifted: list[dict[str, Any]] = []

    def shift(path: str, container: dict[str, Any], key: str) -> None:
        value = container.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            container[key] = float(value) + downtime
            shifted.append({"path": path, "before": value, "after": container[key], "delta_seconds": downtime})

    shift("world_start_wall", state, "world_start_wall")
    for agent_id, agent in state.get("agents", {}).items():
        if isinstance(agent, dict) and agent.get("status") == "alive":
            shift(f"agents.{agent_id}.sleep_until", agent, "sleep_until")
            shift(f"agents.{agent_id}.last_idle_wake", agent, "last_idle_wake")
    original_mode = stat.S_IMODE(state_path.stat().st_mode)
    atomic_json(state_path, state, mode=original_mode)
    computed_before_launch = computed_day(state, time.time())
    if computed_before_launch != state.get("day"):
        raise RuntimeError(
            f"time compensation did not preserve current day: state={state.get('day')} computed={computed_before_launch}"
        )
    event_sha = sha256(events_path)
    event_mtime_before = events_path.stat().st_mtime_ns
    os.utime(events_path, ns=(events_path.stat().st_atime_ns, int(resume_epoch * 1_000_000_000)))

    hold = root / "watchdog/trips" / f"trip-{stamp}-automatic-recovery-hold.json"
    atomic_json(hold, {"schema": "authority-automatic-recovery-hold-v1", "tripped_at": iso_now(), "reason": "automatic_recovery_in_progress", "evidence": {"run_id": state.get("run_id"), "day": state.get("day"), "event_seq": state.get("event_seq")}})
    amendment = {
        "schema": "authority-world-v2-automatic-technical-recovery-v1",
        "status": "prepared",
        "created_at": iso_now(),
        "classification": args.classification,
        "source_trip": {"path": str(trip_path), "sha256": trip_sha, "reason": trip.get("reason"), "tripped_at": trip.get("tripped_at")},
        "enforced_at_epoch": enforcement_epoch,
        "enforcement_receipt": enforcement_receipt,
        "logical_freeze_epoch": freeze_epoch,
        "logical_freeze_adjustment": freeze_adjustment,
        "resume_epoch": resume_epoch,
        "downtime_seconds": downtime,
        "provider_probe": probe,
        "runtime_quiescence": runtime_quiescence,
        "rollback": None if not rollback_files else {
            "source_recovery": str(rollback_recovery),
            "source_amendment_sha256": sha256(rollback_files["amendment"]),
            "invalid_branch_evidence": str(invalid_branch),
        },
        "state": {"before_sha256": state_sha_before, "after_sha256": sha256(state_path), "day": state.get("day"), "event_seq": state.get("event_seq"), "shifted_fields": shifted},
        "events": {"after_sha256": event_sha, "mtime_before_ns": event_mtime_before, "mtime_after_ns": events_path.stat().st_mtime_ns, "technical_energy_refund_records": refund_records},
        "gateway": {"charges": len(charges), "terminals_before": len(terminals), "outstanding_before": outstanding, "outstanding_after": len(terminal_charge_reconciliation(rows(events_path), rows(gateway_path))["unmatched"]), "technical_abort_records": abort_records, "attributable_provider_error_request_ids": [row["data"].get("provider_error_request_id") for row in refund_records if row["data"].get("provider_error_request_id")], "after_sha256": sha256(gateway_path)},
        "agent_state_backup": str(recovery / "agent-state-v2.before"),
        "hold_trip": str(hold),
    }
    atomic_json(recovery / "RECOVERY_AMENDMENT.json", amendment)
    if tmux_mode:
        runner_log = recovery / "runner-start.log"
        runner_exit = recovery / "runner-exit.json"
        runner_command = (
            "set +e; "
            f"{shlex.quote(str(args.runner_launcher))} >> {shlex.quote(str(runner_log))} 2>&1; "
            "code=$?; "
            f"printf '{{\"exit_code\":%s,\"at\":\"%s\"}}\\n' \"$code\" \"$(date -Is)\" > {shlex.quote(str(runner_exit))}; "
            "exit \"$code\""
        )
        command([
            "tmux", "new-session", "-d", "-s", str(args.runner_session),
            "-c", str(root), "bash -lc " + shlex.quote(runner_command),
        ])
        time.sleep(5)
        if not tmux_exists(str(args.runner_session)):
            raise RuntimeError(
                "runner exited during recovery startup: "
                + runner_exit_diagnostic(runner_exit, runner_log)
            )
        command(["tmux", "new-session", "-d", "-s", str(args.watchdog_session), "-c", str(root), str(args.watchdog_launcher)])
        time.sleep(15)
    elif systemd_mode:
        command(["systemctl", "start", str(args.systemd_runner_unit)])
        time.sleep(5)
        if not systemd_active(str(args.systemd_runner_unit)):
            raise RuntimeError("systemd runner exited during recovery startup")
        command(["systemctl", "start", str(args.systemd_watchdog_unit)])
        time.sleep(15)
    after = load(state_path)
    if tmux_mode and (
        not tmux_exists(str(args.runner_session)) or not tmux_exists(str(args.watchdog_session))
    ):
        raise RuntimeError("automatic recovery startup verification failed")
    if systemd_mode and (
        not systemd_active(str(args.systemd_runner_unit))
        or not systemd_active(str(args.systemd_watchdog_unit))
    ):
        raise RuntimeError("automatic systemd recovery startup verification failed")
    if after.get("run_id") != state.get("run_id"):
        raise RuntimeError("automatic recovery changed run identity")
    before_day = state.get("day")
    after_day = after.get("day")
    if not isinstance(before_day, int) or after_day not in {before_day, before_day + 1}:
        raise RuntimeError(f"automatic recovery skipped a world day: before={before_day} after={after_day}")
    if not isinstance(after.get("event_seq"), int) or after["event_seq"] < state.get("event_seq", 0):
        raise RuntimeError("automatic recovery regressed event_seq")
    if computed_day(after, time.time()) != after_day:
        raise RuntimeError("automatic recovery state day does not match compensated world clock")
    final_events = rows(events_path)
    if after_day == before_day + 1 and not any(
        row.get("kind") == "day_started"
        and row.get("day") == after_day
        and isinstance(row.get("seq"), int)
        and row["seq"] > state.get("event_seq", 0)
        for row in final_events
    ):
        raise RuntimeError("world day advanced without an auditable day_started event")
    final_charges = sum(row.get("kind") == "model_request_energy_consumed" for row in final_events)
    final_terminals = sum(row.get("kind") in TERMINAL_KINDS for row in rows(gateway_path))
    live_outstanding = len(terminal_charge_reconciliation(final_events, rows(gateway_path))["unmatched"])
    amendment["status"] = "committed"
    amendment["committed_at"] = iso_now()
    amendment["verification"] = {
        "run_id": after.get("run_id"),
        "day": after_day,
        "computed_day": computed_day(after, time.time()),
        "event_seq": after.get("event_seq"),
        "mode": "prepare_only" if args.prepare_only else ("systemd_restart" if systemd_mode else "tmux_restart"),
        "runner_session_alive": tmux_exists(str(args.runner_session)) if tmux_mode else None,
        "watchdog_session_alive": tmux_exists(str(args.watchdog_session)) if tmux_mode else None,
        "runner_unit_active": systemd_active(str(args.systemd_runner_unit)) if systemd_mode else None,
        "watchdog_unit_active": systemd_active(str(args.systemd_watchdog_unit)) if systemd_mode else None,
        "charges": final_charges,
        "terminals": final_terminals,
        "outstanding_at_verification": live_outstanding,
        "frozen_outstanding_after_reconciliation": 0,
    }
    atomic_json(recovery / "RECOVERY_AMENDMENT.json", amendment)
    if rollback_files:
        atomic_json(
            rollback_recovery / "RECOVERY_SUPERSEDED_BY_ROLLBACK.json",
            {
                "schema": "authority-world-v2-committed-recovery-superseded-v1",
                "at": iso_now(), "superseded_recovery": str(rollback_recovery),
                "corrective_recovery": str(recovery),
                "reason": "terminal provider quota errors were charged before watchdog enforcement",
                "attributable_request_ids": amendment["gateway"]["attributable_provider_error_request_ids"],
            },
        )
    committed = True
    atexit.unregister(rollback_uncommitted_attempt)
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    os.close(lock_fd)
    report.update({"action": "recovered", "recovery": str(recovery), "downtime_seconds": downtime, "outstanding_before": outstanding, "outstanding_after": amendment["gateway"]["outstanding_after"]})
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
