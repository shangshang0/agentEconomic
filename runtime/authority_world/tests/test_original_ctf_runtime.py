from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from backend.artifact_runtime import OriginalAttachmentTaskRuntime, OriginalCTFTaskRuntime, OriginalServiceTaskRuntime, TaskRuntimeError


ROOT = Path(__file__).resolve().parents[1]


def test_task_image_declares_catalog_specific_runtimes() -> None:
    dockerfile = (ROOT / "Dockerfile.task").read_text(encoding="utf-8")
    assert " clamav " in dockerfile
    assert " sagemath " in dockerfile


def test_original_attachment_is_copied_byte_for_byte_and_uses_official_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    handout = source / "event" / "challenge" / "attachments" / "sample.bin"
    handout.parent.mkdir(parents=True)
    payload = b"official handout bytes\x00\xff"
    handout.write_bytes(payload)
    relative = str(handout.relative_to(source))
    manifest = tmp_path / "run.json"
    manifest.write_text(json.dumps({
        "schema": "authority-world-original-ctf-run-v1",
        "tasks": [{
            "id": "T001", "mode": "original_attachment",
            "official_flag": "CTF{official}", "handout_paths": [relative],
            "sha256": {relative: hashlib.sha256(payload).hexdigest()},
        }],
    }))
    runtime = OriginalAttachmentTaskRuntime(tmp_path / "work", "unused", 8, 8192, manifest, source, tmp_path / "host")
    # Avoid Docker in this unit test while exercising manifest validation and copy logic.
    runtime._name = lambda run_id, task_id: "test-original-task"
    calls: list[list[str]] = []
    monkeypatch.setattr("backend.artifact_runtime.subprocess.run", lambda command, **kwargs: calls.append(command) or type("Result", (), {})())
    runtime.prepare("run-1", 1, "T001", "hard")
    copied = runtime.artifacts["T001"].directory / relative
    assert copied.read_bytes() == payload
    assert runtime.correct("T001", "CTF{official}")
    assert not runtime.correct("T001", "AW{replacement}")
    command = calls[0]
    tmpfs_values = [command[index + 1] for index, value in enumerate(command) if value == "--tmpfs"]
    assert "/work:rw,nosuid,nodev,exec,size=256m,uid=10001,gid=10001,mode=0700" in tmpfs_values
    assert "/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777" in tmpfs_values
    assert command[command.index("--memory") + 1] == "1536m"
    assert command[command.index("--memory-swap") + 1] == "1536m"
    assert command[command.index("--pids-limit") + 1] == "96"
    assert command[command.index("--cpus") + 1] == "1.0"


def test_original_attachment_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"; source.mkdir(); handout = source / "x"; handout.write_bytes(b"x")
    manifest = tmp_path / "run.json"
    manifest.write_text(json.dumps({"schema": "authority-world-original-ctf-run-v1", "tasks": [{"id": "T001", "mode": "original_attachment", "official_flag": "CTF{x}", "handout_paths": ["x"], "sha256": {"x": "0" * 64}}]}))
    runtime = OriginalAttachmentTaskRuntime(tmp_path / "work", "unused", 8, 8192, manifest, source)
    with pytest.raises(TaskRuntimeError, match="digest mismatch"):
        runtime.prepare("run-1", 1, "T001", "hard")


def test_original_attachment_start_failure_removes_created_container(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"; source.mkdir(); handout = source / "x"; handout.write_bytes(b"x")
    manifest = tmp_path / "run.json"
    manifest.write_text(json.dumps({"schema": "authority-world-original-ctf-run-v1", "tasks": [{"id": "T001", "mode": "original_attachment", "official_flag": "CTF{x}", "handout_paths": ["x"], "sha256": {"x": hashlib.sha256(b"x").hexdigest()}}]}))
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> object:
        calls.append(command)
        if command[:2] == ["docker", "run"]:
            raise subprocess.CalledProcessError(125, command)
        return type("Result", (), {})()

    monkeypatch.setattr("backend.artifact_runtime.subprocess.run", fake_run)
    runtime = OriginalAttachmentTaskRuntime(tmp_path / "work", "solver", 8, 8192, manifest, source, tmp_path / "host")
    with pytest.raises(TaskRuntimeError, match="container could not start"):
        runtime.prepare("run-1", 1, "T001", "hard")
    name = runtime._name("run-1", "T001")
    assert ["docker", "rm", "-f", name] in calls
    assert "T001" not in runtime.artifacts
    assert "T001" not in runtime.containers


def test_original_attachment_preserves_runnable_handouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"; source.mkdir()
    executable = source / "challenge"; executable.write_bytes(b"\x7fELFpayload")
    script = source / "solve"; script.write_bytes(b"#!/bin/sh\nexit 0\n")
    note = source / "note.txt"; note.write_text("read only")
    manifest = tmp_path / "run.json"
    records = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (executable, script, note)}
    manifest.write_text(json.dumps({"schema": "authority-world-original-ctf-run-v1", "tasks": [{"id": "T001", "mode": "original_attachment", "official_flag": "CTF{x}", "handout_paths": list(records), "sha256": records}]}))
    monkeypatch.setattr("backend.artifact_runtime.subprocess.run", lambda *args, **kwargs: type("Result", (), {})())
    runtime = OriginalAttachmentTaskRuntime(tmp_path / "work", "solver", 8, 8192, manifest, source, tmp_path / "host")
    runtime.prepare("run", 1, "T001", "easy")
    staged = runtime.artifacts["T001"].directory
    assert (staged / "challenge").stat().st_mode & 0o111
    assert (staged / "solve").stat().st_mode & 0o111
    assert not (staged / "note.txt").stat().st_mode & 0o111


def service_manifest(tmp_path: Path, image: str = "example/service@sha256:" + "1" * 64) -> Path:
    manifest = tmp_path / "service-run.json"
    manifest.write_text(json.dumps({
        "schema": "authority-world-original-ctf-run-v1",
        "tasks": [{
            "id": "S001", "mode": "original_service", "official_flag": "CTF{service}",
            "handout_paths": [], "sha256": {},
            "service": {"image": image, "protocol": "tcp", "port": 31337},
        }],
    }))
    return manifest


def test_original_service_requires_immutable_image_digest(tmp_path: Path) -> None:
    with pytest.raises(TaskRuntimeError, match="immutable sha256 digest"):
        OriginalServiceTaskRuntime(tmp_path / "work", "solver", 8, 8192, service_manifest(tmp_path, "example/service:latest"), tmp_path)


def test_original_service_uses_private_network_and_hardened_solver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> object:
        calls.append(command)
        return type("Result", (), {"stdout": ""})()

    monkeypatch.setattr("backend.artifact_runtime.subprocess.run", fake_run)
    runtime = OriginalServiceTaskRuntime(tmp_path / "work", "solver-image", 8, 8192, service_manifest(tmp_path), tmp_path, tmp_path / "host")
    runtime.prepare("run-1", 1, "S001", "hard")
    assert calls[0][:4] == ["docker", "network", "create", "--internal"]
    service = calls[1]
    assert "--network-alias" in service and "service" in service
    assert "--publish" not in service and "-p" not in service
    solver = calls[2]
    assert "--read-only" in solver and ["--cap-drop", "ALL"] == solver[solver.index("--cap-drop"):solver.index("--cap-drop") + 2]
    assert "TASK_SERVICE_HOST=service" in solver and "TASK_SERVICE_PORT=31337" in solver
    assert calls[1][calls[1].index("--memory") + 1] == "256m"
    assert calls[1][calls[1].index("--memory-swap") + 1] == "256m"
    assert solver[solver.index("--memory") + 1] == "1536m"
    assert solver[solver.index("--memory-swap") + 1] == "1536m"
    tmpfs_values = [solver[index + 1] for index, value in enumerate(solver) if value == "--tmpfs"]
    assert len(tmpfs_values) == 2
    assert all("uid=10001,gid=10001" in value for value in tmpfs_values)


def test_mixed_original_runtime_dispatches_by_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = tmp_path / "mixed.json"
    manifest.write_text(json.dumps({
        "schema": "authority-world-original-ctf-run-v1",
        "tasks": [
            {"id": "A001", "mode": "original_attachment", "official_flag": "CTF{a}", "handout_paths": ["a"], "sha256": {"a": hashlib.sha256(b"a").hexdigest()}},
            {"id": "S001", "mode": "original_service", "official_flag": "CTF{s}", "handout_paths": [], "sha256": {}, "service": {"image": "service@sha256:" + "2" * 64, "protocol": "tcp", "port": 1}},
        ],
    }))
    (tmp_path / "a").write_bytes(b"a")
    runtime = OriginalCTFTaskRuntime(tmp_path / "work", "solver", 8, 8192, manifest, tmp_path)
    seen: list[str] = []
    monkeypatch.setattr(runtime.attachments, "prepare", lambda *args: seen.append("attachment"))
    monkeypatch.setattr(runtime.services, "prepare", lambda *args: seen.append("service"))
    runtime.attachments.containers["A001"] = "attachment-container"
    runtime.services.containers["S001"] = "service-container"
    runtime.prepare("run", 1, "A001", "easy")
    runtime.prepare("run", 1, "S001", "hard")
    assert seen == ["attachment", "service"]
    assert runtime.containers == {"A001": "attachment-container", "S001": "service-container"}
