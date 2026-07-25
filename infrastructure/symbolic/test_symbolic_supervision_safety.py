from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


supervisor = load_module("symbolic_supervisor", HERE / "experiment_environment_supervisor.py")
watchdog = load_module("symbolic_watchdog", HERE / "llm_api_watchdog.py")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def make_active_root(root: Path, run_id: str = "run-1") -> None:
    write_json(
        root / "agent-economics-active-run.json",
        {
            "spec": {
                "env_file": ".env.gpt55",
                "config": "config/symbolic.json",
            }
        },
    )
    write_json(
        root / "data-v2/authority-world-v2.state.json",
        {"run_id": run_id, "status": "running", "day": 2, "event_seq": 12},
    )
    (root / "data-v2/authority-world-v2.events.jsonl").write_text("{}\n", encoding="utf-8")


def make_trip(root: Path, reason: str, run_id: str = "run-1") -> Path:
    path = root / "watchdog/trips/trip-1.json"
    write_json(
        path,
        {
            "schema": "authority-llm-watchdog-trip-v1",
            "reason": reason,
            "evidence": {"run_id": run_id},
        },
    )
    return path


def test_rate_trip_is_fail_closed_even_when_not_recoverable(tmp_path: Path) -> None:
    root = tmp_path / "authority-symbolic-root"
    make_trip(root, "api_call_rate_runaway")
    assert supervisor.latest_unprocessed_trip(root, "run-1") is not None
    assert (
        supervisor.latest_recoverable_trip(
            root, supervisor.DEFAULT_AUTOMATIC_RECOVERY_REASONS, "run-1"
        )
        is None
    )


def test_nonrecoverable_trip_never_naked_restarts_runner_or_compose(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "authority-symbolic-root"
    make_active_root(root)
    make_trip(root, "api_call_rate_runaway")
    (root / ".env.gpt55").write_text("MODEL=test\n", encoding="utf-8")
    actions: list[str] = []
    instance = supervisor.Supervisor(
        {"log_path": str(tmp_path / "supervisor.jsonl")}, dry_run=True
    )
    monkeypatch.setattr(supervisor, "runner_alive", lambda _root: False)
    monkeypatch.setattr(supervisor, "tmux_alive", lambda _session: False)
    monkeypatch.setattr(
        supervisor,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "down"),
    )
    monkeypatch.setattr(
        instance,
        "act",
        lambda action, *_args, **_kwargs: actions.append(action) or True,
    )
    report = instance.inspect_world(
        {
            "root": str(root),
            "session": "symbolic",
            "launcher": "/bin/false",
            "restore_compose_on_untripped_failure": True,
        },
        recovery_allowed=True,
    )
    assert actions == []
    assert report["trip_reason"] == "api_call_rate_runaway"
    assert report["fail_closed_nonrecoverable_trip"] is True


def test_provider_observation_paths_are_included_and_deduplicated(tmp_path: Path) -> None:
    root = tmp_path / "authority-symbolic-root"
    gateway = root / "gateway-data-v2/authority-world-v1.gateway.jsonl"
    instance = supervisor.Supervisor(
        {
            "log_path": str(tmp_path / "supervisor.jsonl"),
            "gateway_paths": [str(gateway)],
            "provider_observation_roots": [str(root)],
            "worlds": [{"root": str(root)}],
        },
        dry_run=True,
    )
    assert instance.provider_paths() == [gateway.resolve()]


def test_global_fail_close_writes_rate_trip_before_actions(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "authority-symbolic-root"
    make_active_root(root)
    (root / ".env.gpt55").write_text("MODEL=test\n", encoding="utf-8")
    (root / "docker-compose.v2.fallback.yml").write_text("services: {}\n", encoding="utf-8")
    instance = supervisor.Supervisor(
        {"log_path": str(tmp_path / "supervisor.jsonl"), "watchdogs": []},
        dry_run=False,
    )
    actions: list[str] = []
    monkeypatch.setattr(supervisor, "tmux_alive", lambda _session: False)
    monkeypatch.setattr(supervisor, "world_runner_pids", lambda _root: [])
    monkeypatch.setattr(supervisor, "run_task_container_ids", lambda _run_id: [])
    monkeypatch.setattr(
        instance,
        "act",
        lambda action, *_args, **_kwargs: actions.append(action) or True,
    )
    assert instance.fail_close_world(
        {
            "root": str(root),
            "session": "symbolic",
            "launcher": "/bin/false",
        },
        "aggregate_api_call_budget",
        {"calls_15m": 550, "hard_limit": 550},
    )
    pending = supervisor.latest_unprocessed_trip(root, "run-1")
    assert pending is not None
    assert pending[1]["reason"] == "aggregate_api_call_budget"
    assert actions == ["global_fail_close_compose"]


def test_watchdog_stops_only_run_labeled_task_containers(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        if command[:3] == ["docker", "ps", "-q"]:
            return subprocess.CompletedProcess(command, 0, "one\ntwo\n", "")
        return subprocess.CompletedProcess(command, 0, "one\ntwo\n", "")

    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)
    result = watchdog.stop_run_task_containers("run-1")
    assert result["container_ids"] == ["one", "two"]
    assert commands[0][-1] == "label=authority.run_id=run-1"
    assert commands[1] == ["docker", "stop", "-t", "10", "one", "two"]


def test_agent_runtime_ignores_compose_created_replacements(monkeypatch, tmp_path: Path) -> None:
    running = [f"running-{index}" for index in range(1, 7)]
    created = [f"created-{index}" for index in range(1, 7)]

    def fake_run(command, **_kwargs):
        if command[:3] == ["docker", "ps", "-a"]:
            return subprocess.CompletedProcess(command, 0, "\n".join(running + created) + "\n", "")
        container_id = command[-1]
        prefix, raw_index = container_id.split("-")
        payload = [{
            "Config": {"Labels": {"com.docker.compose.service": f"agent_a{raw_index}"}},
            "State": {"Status": "running" if prefix == "running" else "created", "ExitCode": 0},
            "RestartCount": 0,
        }]
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)
    result = watchdog.agent_runtime_summary(tmp_path, 6)
    assert result["healthy"] is True
    assert result["observed"] == 6
    assert result["ignored_nonrunning"] == 6
    assert {sample["status"] for sample in result["ignored_nonrunning_samples"]} == {"created"}


def test_agent_runtime_still_fails_when_a_running_worker_is_missing(monkeypatch, tmp_path: Path) -> None:
    running = [f"running-{index}" for index in range(1, 6)]
    created = [f"created-{index}" for index in range(1, 7)]

    def fake_run(command, **_kwargs):
        if command[:3] == ["docker", "ps", "-a"]:
            return subprocess.CompletedProcess(command, 0, "\n".join(running + created) + "\n", "")
        container_id = command[-1]
        prefix, raw_index = container_id.split("-")
        payload = [{
            "Config": {"Labels": {"com.docker.compose.service": f"agent_a{raw_index}"}},
            "State": {"Status": "running" if prefix == "running" else "created", "ExitCode": 0},
            "RestartCount": 0,
        }]
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)
    result = watchdog.agent_runtime_summary(tmp_path, 6)
    assert result["healthy"] is False
    assert result["observed"] == 5
    assert result["ignored_nonrunning"] == 6


def test_agent_runtime_failure_requires_consecutive_samples() -> None:
    count = 0
    for _ in range(2):
        count, confirmed = watchdog.agent_runtime_failure_confirmation(
            {"healthy": False}, count, 3
        )
        assert confirmed is False
    count, confirmed = watchdog.agent_runtime_failure_confirmation(
        {"healthy": False}, count, 3
    )
    assert count == 3
    assert confirmed is True
    count, confirmed = watchdog.agent_runtime_failure_confirmation(
        {"healthy": True}, count, 3
    )
    assert count == 0
    assert confirmed is False


def test_launchers_use_correct_per_lane_rate_limit() -> None:
    for name in (
        "run-watchdog-symbolic-clean-gpt-v2.sh",
        "run-watchdog-symbolic-clean-ds-v2.sh",
    ):
        text = (HERE / name).read_text(encoding="utf-8")
        assert "--max-calls-per-window 250" in text
        assert "--max-calls-per-window 120" not in text
