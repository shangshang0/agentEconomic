#!/usr/bin/env python3
"""Conservative host-level supervision for Authority World experiments.

Per-world API watchdogs remain authoritative for provider errors, outstanding
calls, and world stalls. This supervisor adds host admission control, recovers
infrastructure that vanished without a newer watchdog trip, and can invoke an
audited time-compensated recovery controller for explicitly configured lanes.
It never naked-resumes a tripped run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


DEFAULT_AUTOMATIC_RECOVERY_REASONS = {
    "provider_call_deadlock_or_timeout",
    "consecutive_provider_errors",
    "provider_error_rate",
    "world_event_stall",
    "task_container_missing",
    "task_tool_transport_timeout",
    "host_disk_hard_limit",
}


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected object: {path}")
    return value


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat()


def parse_timestamp(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def is_recovery_technical_abort(row: dict[str, Any]) -> bool:
    return (
        row.get("kind") in {"provider_error", "codex_provider_error"}
        and isinstance(row.get("recovery"), dict)
        and str(row.get("request_id", "")).startswith("automatic-recovery-abort:")
        and "technical_abort_at_watchdog_trip" in str(row.get("error", ""))
    )


def tail_gateway(path: Path, cutoff: float) -> tuple[int, int]:
    total = errors = 0
    if not path.exists():
        return total, errors
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            stamp = parse_timestamp(row.get("at"))
            if stamp is None or stamp < cutoff:
                continue
            if row.get("kind") not in {"exchange", "provider_error", "codex_responses_exchange", "codex_provider_error"}:
                continue
            if is_recovery_technical_abort(row):
                continue
            total += 1
            errors += row.get("kind") in {"provider_error", "codex_provider_error"}
    return total, errors


def newest_mtime(paths: list[Path]) -> float:
    values = [path.stat().st_mtime for path in paths if path.exists()]
    return max(values, default=0.0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def recovery_trip_processed(root: Path, trip_path: Path) -> bool:
    trip_sha = sha256(trip_path)
    for amendment_path in (root / "recovery").glob("automatic-*/RECOVERY_AMENDMENT.json"):
        try:
            amendment = load_object(amendment_path)
        except (OSError, ValueError, RuntimeError):
            continue
        source = amendment.get("source_trip")
        if (
            isinstance(source, dict)
            and source.get("sha256") == trip_sha
            and amendment.get("status") in {None, "committed"}
        ):
            return True
    return False


def latest_recoverable_trip(
    root: Path,
    allowed_reasons: set[str],
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for path in (root / "watchdog/trips").glob("trip-*.json"):
        try:
            value = load_object(path)
        except (OSError, ValueError, RuntimeError):
            continue
        if value.get("schema") != "authority-llm-watchdog-trip-v1":
            continue
        if value.get("reason") not in allowed_reasons:
            continue
        evidence = value.get("evidence")
        if run_id is not None and (
            not isinstance(evidence, dict) or evidence.get("run_id") != run_id
        ):
            continue
        if recovery_trip_processed(root, path):
            continue
        candidates.append((path.stat().st_mtime_ns, path, value))
    if not candidates:
        return None
    _, path, value = max(candidates)
    return path, value


def latest_unprocessed_trip(
    root: Path,
    run_id: str | None = None,
) -> tuple[Path, dict[str, Any]] | None:
    """Return the newest pending trip, regardless of recovery policy.

    Recovery eligibility and fail-closed state are deliberately separate.
    A non-recoverable circuit-breaker trip must still prevent a naked runner,
    watchdog, or Compose restart.
    """
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for path in (root / "watchdog/trips").glob("trip-*.json"):
        try:
            value = load_object(path)
        except (OSError, ValueError, RuntimeError):
            continue
        if value.get("schema") != "authority-llm-watchdog-trip-v1":
            continue
        evidence = value.get("evidence")
        if run_id is not None and (
            not isinstance(evidence, dict) or evidence.get("run_id") != run_id
        ):
            continue
        if recovery_trip_processed(root, path):
            continue
        candidates.append((path.stat().st_mtime_ns, path, value))
    if not candidates:
        return None
    _, path, value = max(candidates)
    return path, value


def last_json_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last = None
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                last = value
    return last


def is_world_runner_process(cmdline: bytes, cwd: Path | None, root: Path) -> bool:
    """Distinguish the runner from watchdog arguments naming its pattern."""
    arguments = [value.decode(errors="replace") for value in cmdline.split(b"\0") if value]
    path_belongs_to_root = False
    for value in arguments:
        candidate = Path(value)
        if candidate.is_absolute() and (candidate == root or root in candidate.parents):
            path_belongs_to_root = True
            break
    return (
        b"run_agent_economics_experiment.py" in cmdline
        and b"llm_api_watchdog.py" not in cmdline
        and (path_belongs_to_root or cwd == root)
    )


def runner_alive(root: Path) -> bool:
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            value = cmdline.read_bytes()
            cwd = Path(os.readlink(cmdline.parent / "cwd"))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if is_world_runner_process(value, cwd, root):
            return True
    return False


def world_runner_pids(root: Path) -> list[int]:
    result: list[int] = []
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            value = cmdline.read_bytes()
            cwd = Path(os.readlink(cmdline.parent / "cwd"))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if is_world_runner_process(value, cwd, root):
            result.append(int(cmdline.parent.name))
    return sorted(result)


def run_task_container_ids(run_id: str) -> list[str]:
    result = run([
        "docker", "ps", "-q", "--filter", f"label=authority.run_id={run_id}",
    ])
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def tmux_alive(session: str) -> bool:
    return run(["tmux", "has-session", "-t", session]).returncode == 0


def memory_available_gib() -> float:
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024 / 1024
    return 0.0


def disk_consumption_rate_gib_per_minute(
    previous_free_gib: float,
    previous_at: float,
    current_free_gib: float,
    current_at: float,
) -> float:
    """Return only positive disk consumption, normalized to GiB/minute."""
    elapsed_minutes = (current_at - previous_at) / 60
    if elapsed_minutes <= 0:
        return 0.0
    return max(0.0, previous_free_gib - current_free_gib) / elapsed_minutes


class Supervisor:
    def __init__(self, config: dict[str, Any], *, dry_run: bool) -> None:
        self.config = config
        self.dry_run = dry_run
        self.log_path = Path(config["log_path"])
        self.counters: dict[str, int] = {}
        self.healthy_admission_samples = 0
        self.previous_disk_sample: tuple[float, float] | None = None
        self.recovery_started_this_sample = False
        self.recovery_cooldown_until = 0.0

    def emit(self, kind: str, **payload: Any) -> None:
        record = {"at": iso_now(), "kind": kind, **payload}
        print(json.dumps(record, sort_keys=True), flush=True)
        if self.dry_run:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()

    def act(
        self,
        action: str,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        **evidence: Any,
    ) -> bool:
        if self.dry_run:
            self.emit("would_recover", action=action, command=command, **evidence)
            return True
        result = run(command, cwd=cwd, env=env)
        self.emit(
            "recovery",
            action=action,
            command=command,
            returncode=result.returncode,
            stdout=result.stdout[-1000:],
            stderr=result.stderr[-1000:],
            **evidence,
        )
        return result.returncode == 0

    def set_admission(self, pause: bool, reasons: list[str]) -> None:
        raw = self.config.get("queue_pause_file")
        if not raw:
            return
        path = Path(raw)
        if pause:
            self.healthy_admission_samples = 0
            if not path.exists():
                self.emit("admission_paused", reasons=reasons)
                if not self.dry_run:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"at": iso_now(), "reasons": reasons}, indent=2) + "\n", encoding="utf-8")
            return
        self.healthy_admission_samples += 1
        required = int(self.config.get("resume_after_healthy_samples", 3))
        if path.exists() and self.healthy_admission_samples >= required:
            self.emit("admission_resumed")
            if not self.dry_run:
                path.unlink(missing_ok=True)

    def compose_context(self, world: dict[str, Any], marker: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
        root = Path(world["root"])
        spec = marker["spec"]
        env_file = root / spec["env_file"]
        compose_file = root / world.get("compose_file", "docker-compose.v2.fallback.yml")
        command = ["docker", "compose", "--env-file", str(env_file), "-f", str(compose_file)]
        environment = os.environ.copy()
        environment["WORLD_CONFIG_FILE"] = Path(spec["config"]).name
        return command, environment

    def provider_paths(self) -> list[Path]:
        paths: list[Path] = [Path(value) for value in self.config.get("gateway_paths", [])]
        for raw_root in self.config.get("provider_observation_roots", []):
            paths.append(Path(raw_root) / "gateway-data-v2/authority-world-v1.gateway.jsonl")
        for world in self.config.get("worlds", []):
            paths.append(Path(world["root"]) / "gateway-data-v2/authority-world-v1.gateway.jsonl")
        # A path may be both managed and observed; count each provider terminal once.
        return list(dict.fromkeys(path.resolve() for path in paths))

    def fail_close_world(self, world: dict[str, Any], reason: str, evidence: dict[str, Any]) -> bool:
        root = Path(world["root"])
        state_path = root / "data-v2/authority-world-v2.state.json"
        marker_path = root / "agent-economics-active-run.json"
        if not state_path.exists() or not marker_path.exists():
            return False
        try:
            state = load_object(state_path)
            marker = load_object(marker_path)
        except (OSError, ValueError, RuntimeError) as error:
            self.emit("global_fail_close_error", root=str(root), error=f"invalid_state:{error}")
            return False
        if state.get("status") not in {"scheduled", "running"}:
            return False
        run_id = state.get("run_id")
        if latest_unprocessed_trip(root, str(run_id) if run_id else None) is not None:
            return False
        receipt = root / "watchdog/trips" / (
            "trip-" + dt.datetime.now().strftime("%Y%m%dT%H%M%S%f") + ".json"
        )
        payload = {
            "schema": "authority-llm-watchdog-trip-v1",
            "tripped_at": iso_now(),
            "reason": reason,
            "evidence": {
                **evidence,
                "run_id": run_id,
                "world_status": state.get("status"),
                "day": state.get("day"),
                "event_seq": state.get("event_seq"),
            },
        }
        if self.dry_run:
            self.emit("would_global_fail_close", root=str(root), receipt=str(receipt), **payload)
            return True
        receipt.parent.mkdir(parents=True, exist_ok=True)
        temporary = receipt.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(receipt)

        session = str(world["session"])
        action_results: list[bool] = []
        if tmux_alive(session):
            action_results.append(self.act("global_fail_close_runner_session", ["tmux", "kill-session", "-t", session], root=str(root), run_id=run_id))
        pids = world_runner_pids(root)
        if pids:
            action_results.append(self.act("global_fail_close_runner_pids", ["kill", "-TERM", *map(str, pids)], root=str(root), run_id=run_id))
        for watchdog in self.config.get("watchdogs", []):
            if Path(watchdog["root"]).resolve() != root.resolve():
                continue
            watchdog_session = str(watchdog["session"])
            if tmux_alive(watchdog_session):
                action_results.append(self.act(
                    "global_fail_close_watchdog_session",
                    ["tmux", "kill-session", "-t", watchdog_session],
                    root=str(root),
                    run_id=run_id,
                ))
        compose, environment = self.compose_context(world, marker)
        action_results.append(self.act(
            "global_fail_close_compose",
            compose + ["down"],
            cwd=root,
            env=environment,
            root=str(root),
            run_id=run_id,
        ))
        task_ids = run_task_container_ids(str(run_id)) if run_id else []
        if task_ids:
            action_results.append(self.act(
                "global_fail_close_task_containers",
                ["docker", "stop", "-t", "10", *task_ids],
                root=str(root),
                run_id=run_id,
            ))
        if not all(action_results):
            self.emit(
                "global_fail_close_incomplete",
                root=str(root),
                run_id=run_id,
                reason=reason,
                receipt=str(receipt),
            )
            return False
        enforced = {
            "at": iso_now(),
            "kind": "enforced",
            "source": "environment_supervisor_global_fail_close",
            "run_id": run_id,
            "day": state.get("day"),
            "event_seq": state.get("event_seq"),
            "reason": reason,
            "trip": str(receipt),
            "trip_sha256": sha256(receipt),
        }
        watchdog_log = root / "watchdog/watchdog.jsonl"
        watchdog_log.parent.mkdir(parents=True, exist_ok=True)
        with watchdog_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(enforced, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.emit(
            "global_fail_closed",
            root=str(root),
            run_id=run_id,
            reason=reason,
            receipt=str(receipt),
            enforced_receipt=enforced,
        )
        return True

    def inspect_world(self, world: dict[str, Any], *, recovery_allowed: bool) -> dict[str, Any]:
        root = Path(world["root"])
        recovery_hold = root / str(world.get("automatic_recovery_hold_file", "MANUAL_RECOVERY_HOLD.json"))
        state_path = root / "data-v2/authority-world-v2.state.json"
        event_path = root / "data-v2/authority-world-v2.events.jsonl"
        marker_path = root / "agent-economics-active-run.json"
        if not state_path.exists() or not marker_path.exists():
            return {"root": str(root), "active": False}
        try:
            state = load_object(state_path)
            marker = load_object(marker_path)
        except (OSError, ValueError, RuntimeError) as error:
            return {"root": str(root), "active": True, "error": f"invalid_state:{error}"}
        status = state.get("status")
        if status not in {"scheduled", "running"}:
            return {"root": str(root), "active": False, "status": status}
        event_mtime = event_path.stat().st_mtime if event_path.exists() else 0.0
        allowed_reasons = set(
            world.get("automatic_recovery_allowed_reasons", DEFAULT_AUTOMATIC_RECOVERY_REASONS)
        )
        pending_trip = latest_unprocessed_trip(root, state.get("run_id"))
        recoverable = latest_recoverable_trip(root, allowed_reasons, state.get("run_id"))
        tripped_after_progress = pending_trip is not None
        process_alive = runner_alive(root)
        session = str(world["session"])
        missing_key = f"missing:{root}"
        recovery_key = f"automatic_recovery:{root}"
        if not process_alive and not tripped_after_progress:
            self.counters[missing_key] = self.counters.get(missing_key, 0) + 1
            if self.counters[missing_key] >= 2:
                launcher = str(world["launcher"])
                if not tmux_alive(session):
                    self.act(
                        "resume_runner",
                        ["tmux", "new-session", "-d", "-s", session, "-c", str(root), launcher],
                        root=str(root),
                        run_id=state.get("run_id"),
                    )
                self.counters[missing_key] = 0
        else:
            self.counters[missing_key] = 0

        recovery_command = world.get("automatic_recovery_command")
        recovery_samples = int(world.get("automatic_recovery_samples", 3))
        recovery_pending = bool(not process_alive and recoverable is not None and recovery_command)
        recovery_held = recovery_hold.exists()
        if recovery_pending and recovery_allowed and not recovery_held:
            self.counters[recovery_key] = self.counters.get(recovery_key, 0) + 1
            if self.counters[recovery_key] >= recovery_samples:
                if not isinstance(recovery_command, list) or not recovery_command or not all(
                    isinstance(value, str) and value for value in recovery_command
                ):
                    self.emit(
                        "automatic_recovery_configuration_error",
                        root=str(root),
                        error="automatic_recovery_command must be a non-empty list of non-empty strings",
                    )
                else:
                    recovery_succeeded = self.act(
                        "automatic_time_compensated_recovery",
                        recovery_command,
                        cwd=root,
                        root=str(root),
                        run_id=state.get("run_id"),
                        day=state.get("day"),
                        event_seq=state.get("event_seq"),
                        healthy_samples=self.counters[recovery_key],
                    )
                    if recovery_succeeded:
                        self.recovery_started_this_sample = True
                        self.recovery_cooldown_until = time.time() + float(
                            self.config.get("automatic_recovery_cooldown_seconds", 300)
                        )
                self.counters[recovery_key] = 0
        else:
            self.counters[recovery_key] = 0

        compose, environment = self.compose_context(world, marker)
        health = run(
            compose + ["exec", "-T", "backend", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/health',timeout=3).read()"],
            cwd=root,
            env=environment,
        )
        health_key = f"health:{root}"
        restore_untripped = bool(world.get("restore_compose_on_untripped_failure", True))
        if health.returncode != 0 and not tripped_after_progress and restore_untripped:
            self.counters[health_key] = self.counters.get(health_key, 0) + 1
            if self.counters[health_key] >= 3:
                self.act(
                    "restore_compose",
                    compose + ["up", "-d"],
                    cwd=root,
                    env=environment,
                    root=str(root),
                    run_id=state.get("run_id"),
                )
                self.counters[health_key] = 0
        else:
            self.counters[health_key] = 0
        watchdog_record = last_json_record(root / "watchdog/watchdog.jsonl") or {}
        return {
            "root": str(root),
            "active": True,
            "run_id": state.get("run_id"),
            "status": status,
            "day": state.get("day"),
            "event_seq": state.get("event_seq"),
            "event_age_seconds": round(time.time() - event_mtime, 3) if event_mtime else None,
            "runner_alive": process_alive,
            "backend_healthy": health.returncode == 0,
            "restore_compose_on_untripped_failure": restore_untripped,
            "tripped_after_progress": tripped_after_progress,
            "trip_reason": pending_trip[1].get("reason") if pending_trip else None,
            "fail_closed_nonrecoverable_trip": bool(pending_trip and recoverable is None),
            "automatic_recovery_pending": recovery_pending,
            "automatic_recovery_held": recovery_held,
            "automatic_recovery_hold_file": str(recovery_hold) if recovery_held else None,
            "automatic_recovery_healthy_samples": self.counters.get(recovery_key, 0),
            "automatic_recovery_blocked_by_admission": recovery_pending and (not recovery_allowed or recovery_held),
            "outstanding_calls": watchdog_record.get("outstanding_calls"),
            "oldest_outstanding_seconds": watchdog_record.get("oldest_outstanding_seconds"),
        }

    def inspect_systemd_workers(self) -> list[dict[str, Any]]:
        reports = []
        for worker in self.config.get("systemd_workers", []):
            output = Path(worker["output"])
            count = 0
            if output.exists():
                with output.open(encoding="utf-8", errors="replace") as stream:
                    count = sum(bool(line.strip()) for line in stream)
            target = int(worker["target_results"])
            unit = str(worker["unit"])
            active = run(["systemctl", "is-active", "--quiet", unit]).returncode == 0
            trip_dir = Path(worker["trip_dir"])
            newest_trip = newest_mtime(list(trip_dir.glob("trip-*.json")))
            output_mtime = output.stat().st_mtime if output.exists() else 0.0
            fresh_trip = newest_trip >= output_mtime and newest_trip > 0
            key = f"unit:{unit}"
            if count < target and not active and not fresh_trip:
                self.counters[key] = self.counters.get(key, 0) + 1
                if self.counters[key] >= 2:
                    self.act("restart_systemd_worker", ["systemctl", "restart", unit], unit=unit, results=count, target=target)
                    self.counters[key] = 0
            else:
                self.counters[key] = 0
            reports.append({"unit": unit, "active": active, "results": count, "target": target, "fresh_trip": fresh_trip})
        return reports

    def inspect_watchdogs(self) -> list[dict[str, Any]]:
        reports = []
        for watchdog in self.config.get("watchdogs", []):
            session = str(watchdog["session"])
            root = Path(watchdog["root"])
            active_marker = root / "agent-economics-active-run.json"
            event_path = root / "data-v2/authority-world-v2.events.jsonl"
            state_path = root / "data-v2/authority-world-v2.state.json"
            try:
                state = load_object(state_path) if state_path.exists() else {}
            except (OSError, ValueError, RuntimeError):
                state = {}
            pending_trip = latest_unprocessed_trip(root, state.get("run_id"))
            tripped_after_progress = pending_trip is not None
            alive = tmux_alive(session)
            key = f"watchdog:{session}"
            if active_marker.exists() and not alive and not tripped_after_progress:
                self.counters[key] = self.counters.get(key, 0) + 1
                if self.counters[key] >= 2:
                    self.act(
                        "restart_watchdog",
                        ["tmux", "new-session", "-d", "-s", session, "-c", str(root), str(watchdog["launcher"])],
                        session=session,
                        root=str(root),
                    )
                    self.counters[key] = 0
            else:
                self.counters[key] = 0
            reports.append({
                "session": session,
                "alive": alive,
                "root": str(root),
                "tripped_after_progress": tripped_after_progress,
                "trip_reason": pending_trip[1].get("reason") if pending_trip else None,
            })
        return reports

    def sample(self) -> None:
        now = time.time()
        total_calls = total_errors = 0
        for gateway_path in self.provider_paths():
            calls, errors = tail_gateway(gateway_path, now - 900)
            total_calls += calls
            total_errors += errors
        load1 = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        memory_gib = memory_available_gib()
        disk_path = Path(self.config.get("disk_path", "/"))
        disk_gib = shutil.disk_usage(disk_path).free / 1024**3
        disk_sampled_at = time.time()
        disk_consumption_rate = 0.0
        if self.previous_disk_sample is not None:
            previous_disk_gib, previous_disk_at = self.previous_disk_sample
            disk_consumption_rate = disk_consumption_rate_gib_per_minute(
                previous_disk_gib,
                previous_disk_at,
                disk_gib,
                disk_sampled_at,
            )
        self.previous_disk_sample = (disk_gib, disk_sampled_at)
        reasons = []
        if total_calls >= int(self.config.get("pause_calls_15m", 550)):
            reasons.append("aggregate_call_budget")
        if total_calls >= 20 and total_errors / total_calls >= float(self.config.get("pause_error_rate", 0.05)):
            reasons.append("aggregate_provider_error_rate")
        if total_errors >= int(self.config.get("pause_errors_15m", 6)):
            reasons.append("aggregate_provider_errors")
        oldest = max(
            (
                float(record["oldest_outstanding_seconds"])
                for world in self.config.get("worlds", [])
                for record in [last_json_record(Path(world["root"]) / "watchdog/watchdog.jsonl") or {}]
                if isinstance(record.get("oldest_outstanding_seconds"), (int, float))
            ),
            default=0.0,
        )
        if oldest >= float(self.config.get("pause_oldest_outstanding_seconds", 120)):
            reasons.append("provider_response_slow")
        if load1 >= cpu_count * float(self.config.get("pause_load_fraction", 0.9)):
            reasons.append("host_load")
        if memory_gib < float(self.config.get("minimum_memory_gib", 8)):
            reasons.append("host_memory")
        if disk_gib < float(self.config.get("minimum_disk_gib", 20)):
            reasons.append("host_disk")
        disk_rate_limit = self.config.get("pause_disk_consumption_gib_per_minute")
        disk_burn_key = "admission:disk_consumption_rate"
        if disk_rate_limit is not None and disk_consumption_rate >= float(disk_rate_limit):
            self.counters[disk_burn_key] = self.counters.get(disk_burn_key, 0) + 1
        else:
            self.counters[disk_burn_key] = 0
        required_disk_burn_samples = int(self.config.get("pause_disk_consumption_samples", 2))
        if self.counters[disk_burn_key] >= required_disk_burn_samples:
            reasons.append("host_disk_consumption_rate")
        self.set_admission(bool(reasons), reasons)
        hard_reasons: list[str] = []
        hard_call_limit = self.config.get("fail_close_calls_15m")
        if hard_call_limit is not None and total_calls >= int(hard_call_limit):
            hard_reasons.append("aggregate_api_call_budget")
        hard_disk_limit = self.config.get("fail_close_disk_gib")
        if hard_disk_limit is not None and disk_gib < float(hard_disk_limit):
            hard_reasons.append("host_disk_hard_limit")
        if hard_reasons:
            evidence = {
                "calls_15m": total_calls,
                "provider_errors_15m": total_errors,
                "hard_call_limit": int(hard_call_limit) if hard_call_limit is not None else None,
                "disk_available_gib": round(disk_gib, 3),
                "hard_disk_limit_gib": float(hard_disk_limit) if hard_disk_limit is not None else None,
                "hard_reasons": hard_reasons,
                "provider_paths": [str(path) for path in self.provider_paths()],
            }
            trip_reason = hard_reasons[0] if len(hard_reasons) == 1 else "aggregate_host_safety_budget"
            for world in self.config.get("worlds", []):
                self.fail_close_world(world, trip_reason, evidence)
        self.recovery_started_this_sample = False
        world_reports = []
        for world in self.config.get("worlds", []):
            recovery_allowed = (
                not reasons
                and not self.recovery_started_this_sample
                and time.time() >= self.recovery_cooldown_until
            )
            world_reports.append(self.inspect_world(world, recovery_allowed=recovery_allowed))
        workers = self.inspect_systemd_workers()
        watchdogs = self.inspect_watchdogs()
        self.emit(
            "heartbeat",
            calls_15m=total_calls,
            provider_errors_15m=total_errors,
            oldest_outstanding_seconds=oldest,
            load1=load1,
            cpu_count=cpu_count,
            memory_available_gib=round(memory_gib, 3),
            disk_available_gib=round(disk_gib, 3),
            disk_consumption_gib_per_minute=round(disk_consumption_rate, 3),
            disk_consumption_samples=self.counters[disk_burn_key],
            admission_paused=bool(reasons),
            reasons=reasons,
            automatic_recovery_cooldown_remaining_seconds=round(
                max(0.0, self.recovery_cooldown_until - time.time()), 3
            ),
            worlds=world_reports,
            workers=workers,
            watchdogs=watchdogs,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=30)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    supervisor = Supervisor(load_object(args.config), dry_run=args.dry_run)
    while True:
        try:
            supervisor.sample()
        except Exception as error:
            supervisor.emit("supervisor_error", error=f"{type(error).__name__}: {error}")
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
