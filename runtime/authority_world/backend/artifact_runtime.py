"""Backend-owned, disposable Docker workspaces for v2 artifact tasks.

Only this module touches Docker.  Agents submit a task handle and a Bash
string to the backend; no Agent receives a container name, socket, mount path,
network route, raw task seed, or provider credential.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import json
from dataclasses import dataclass
from pathlib import Path


class TaskRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class Artifact:
    task_id: str
    flag: str
    directory: Path


def flag_for(seed: int, task_id: str) -> str:
    nonce = hashlib.sha256((str(seed) + ":" + task_id + ":authority-world-v2").encode()).hexdigest()[:24]
    return "AW{" + nonce + "}"


def make_artifact(root: Path, seed: int, task_id: str, tier: str) -> Artifact:
    """Create a benign local file puzzle with a fresh, run-specific flag."""
    directory = root / task_id
    directory.mkdir(parents=True, exist_ok=False)
    flag = flag_for(seed, task_id)
    if tier == "easy":
        (directory / "dispatch.log").write_text("night shift notes\narchive token: " + flag + "\nend\n", encoding="utf-8")
    elif tier == "medium":
        payload = base64.b64encode(("incident transcript\nverification=" + flag + "\n").encode()).decode()
        (directory / "relay.txt").write_text("This is a base64-encoded archived relay.\n" + payload + "\n", encoding="utf-8")
    elif tier == "hard":
        first = base64.b64encode(flag[: len(flag) // 2].encode()).decode()
        second = base64.b64encode(flag[len(flag) // 2 :].encode()).decode()
        (directory / "north.fragment").write_text(first + "\n", encoding="utf-8")
        (directory / "south.fragment").write_text(second + "\n", encoding="utf-8")
        (directory / "README.txt").write_text("Two recovered base64 fragments must be decoded and joined in compass order.\n", encoding="utf-8")
    else:
        raise TaskRuntimeError("unknown task tier")
    os.chmod(directory, 0o555)
    for child in directory.iterdir(): os.chmod(child, 0o444)
    return Artifact(task_id, flag, directory)


def staged_file_mode(source: Path) -> int:
    """Keep official executables runnable while leaving handouts immutable."""
    header = source.read_bytes()[:4]
    executable = bool(source.stat().st_mode & 0o111) or header == b"\x7fELF" or header.startswith(b"#!")
    return 0o555 if executable else 0o444


class DockerTaskRuntime:
    TASK_USER = "10001:10001"
    WORK_TMPFS = "/work:rw,nosuid,nodev,exec,size=256m,uid=10001,gid=10001,mode=0700"
    TMP_TMPFS = "/tmp:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=1777"

    def __init__(self, work_root: Path, image: str, timeout_seconds: float, output_bytes: int, host_work_root: Path | None = None):
        # ``work_root`` is the path visible inside the backend container.
        # Docker's daemon, however, interprets bind-mount sources on the host.
        # Keep those namespaces explicit: otherwise /world-data/tasks becomes
        # an unrelated empty host directory and every task appears blank.
        self.work_root = work_root; self.host_work_root = host_work_root or work_root
        self.image = image; self.timeout_seconds = timeout_seconds; self.output_bytes = output_bytes
        self.artifacts: dict[str, Artifact] = {}; self.containers: dict[str, str] = {}

    @staticmethod
    def _name(run_id: str, task_id: str) -> str:
        return "authority-v2-" + re.sub("[^a-zA-Z0-9_.-]", "-", run_id + "-" + task_id).lower()[:100]

    @staticmethod
    def _run_name_prefix(run_id: str) -> str:
        fragment = re.sub("[^a-zA-Z0-9_.-]", "-", run_id).lower()
        return "authority-v2-" + fragment + "-"

    @classmethod
    def _resource_belongs_to_run(cls, value: dict[str, object], run_id: str) -> bool:
        labels = value.get("Config", {}).get("Labels", {}) if isinstance(value.get("Config"), dict) else {}
        if not labels and isinstance(value.get("Labels"), dict):
            labels = value["Labels"]
        if isinstance(labels, dict) and labels.get("authority.run_id") == run_id:
            return True
        name = str(value.get("Name", "")).lstrip("/")
        return name.startswith(cls._run_name_prefix(run_id))

    def prepare(self, run_id: str, seed: int, task_id: str, tier: str) -> None:
        if task_id in self.artifacts: return
        self.work_root.mkdir(parents=True, exist_ok=True)
        # Task IDs repeat across experimental branches. The world run is the
        # namespace boundary for persistent artifacts and Docker bind sources.
        run_fragment = re.sub("[^a-zA-Z0-9_.-]", "-", run_id)
        artifact_root = self.work_root / run_fragment
        stale_artifact = artifact_root / task_id
        if stale_artifact.exists():
            # A backend restart loses the in-memory index. The task payload is
            # deterministic for (seed, task_id), so rebuilding is safer than
            # either failing recovery or trusting a partial stale directory.
            shutil.rmtree(stale_artifact)
        self.artifacts[task_id] = make_artifact(artifact_root, seed, task_id, tier)
        name = self._name(run_id, task_id); self.containers[task_id] = name
        host_artifact = self.host_work_root / run_fragment / task_id
        # This path intentionally cannot be stat'ed from the backend container:
        # it names the Docker *host* namespace. Docker itself validates it when
        # creating the bind mount below.
        command = ["docker", "run", "-d", "--rm", "--name", name, "--network", "none", "--read-only", "--user", self.TASK_USER, "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "64", "--memory", "256m", "--cpus", "1.0", "--tmpfs", self.WORK_TMPFS, "--tmpfs", self.TMP_TMPFS, "-v", str(host_artifact) + ":/task:ro", "--label", "authority.world=v2-task", "--label", "authority.run_id=" + run_id, self.image, "sleep", "infinity"]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
        except (OSError, subprocess.SubprocessError) as error:
            shutil.rmtree(self.artifacts[task_id].directory, ignore_errors=True); self.artifacts.pop(task_id, None); self.containers.pop(task_id, None)
            raise TaskRuntimeError("task container could not start") from error

    def execute(self, task_id: str, command: str) -> dict[str, object]:
        if task_id not in self.containers or not isinstance(command, str) or not command.strip() or len(command) > 4000:
            raise TaskRuntimeError("invalid task command")
        try:
            result = subprocess.run(["docker", "exec", self.containers[task_id], "timeout", "--signal=KILL", str(self.timeout_seconds) + "s", "/bin/bash", "-lc", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=self.timeout_seconds + 3, check=False)
        except subprocess.TimeoutExpired:
            return {"exit_code": 124, "stdout": "", "stderr": "command timed out", "truncated": False}
        def clip(raw: bytes) -> tuple[str, bool]:
            return raw[: self.output_bytes].decode("utf-8", "replace"), len(raw) > self.output_bytes
        out, out_cut = clip(result.stdout); err, err_cut = clip(result.stderr)
        return {"exit_code": result.returncode, "stdout": out, "stderr": err, "truncated": out_cut or err_cut}

    def correct(self, task_id: str, flag: str) -> bool:
        artifact = self.artifacts.get(task_id)
        return artifact is not None and isinstance(flag, str) and hashlib.sha256(flag.encode()).digest() == hashlib.sha256(artifact.flag.encode()).digest()

    def close(self, task_id: str) -> None:
        name = self.containers.pop(task_id, None); artifact = self.artifacts.pop(task_id, None)
        if name: subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if artifact: shutil.rmtree(artifact.directory, ignore_errors=True)

    def close_all(self) -> None:
        for task_id in list(self.containers): self.close(task_id)

    def cleanup_orphans(self, run_id: str) -> None:
        """Remove only this run's task containers after backend recreation.

        Several independent experiment lanes share one Docker daemon.  The
        old implementation removed every container carrying the world label,
        so restarting one lane destroyed live task sandboxes in every other
        lane.  New resources carry an explicit run label; deterministic names
        keep the first upgrade compatible with legacy unlabeled containers.
        """
        try:
            listed = subprocess.run(
                ["docker", "ps", "-aq", "--filter", "label=authority.world=v2-task"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=10,
            )
            owned: list[str] = []
            for container_id in (item for item in listed.stdout.splitlines() if item):
                inspected = subprocess.run(
                    ["docker", "inspect", container_id], check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10,
                )
                values = json.loads(inspected.stdout)
                if values and isinstance(values[0], dict) and self._resource_belongs_to_run(values[0], run_id):
                    owned.append(container_id)
            if owned:
                subprocess.run(["docker", "rm", "-f", *owned], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
        except (OSError, subprocess.SubprocessError) as error:
            raise TaskRuntimeError("could not clean orphan task containers") from error


class OriginalAttachmentTaskRuntime(DockerTaskRuntime):
    """Run byte-identical official CTF handouts in the existing task sandbox."""

    def __init__(self, work_root: Path, image: str, timeout_seconds: float, output_bytes: int, manifest_path: Path, source_root: Path, host_work_root: Path | None = None):
        super().__init__(work_root, image, timeout_seconds, output_bytes, host_work_root)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "authority-world-original-ctf-run-v1":
            raise TaskRuntimeError("unsupported original CTF run manifest")
        tasks = manifest.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise TaskRuntimeError("original CTF run manifest has no tasks")
        self.source_root = source_root.resolve()
        self.original_tasks: dict[str, dict[str, object]] = {}
        for task in tasks:
            if not isinstance(task, dict) or not isinstance(task.get("id"), str):
                raise TaskRuntimeError("invalid original CTF task record")
            if task.get("mode") == "original_service":
                continue
            if task.get("mode") != "original_attachment":
                raise TaskRuntimeError("unknown original CTF runtime mode")
            if not isinstance(task.get("official_flag"), str) or not task["official_flag"]:
                raise TaskRuntimeError("original CTF task is missing its official flag")
            paths = task.get("handout_paths")
            if not isinstance(paths, list) or not paths or not all(isinstance(path, str) and path for path in paths):
                raise TaskRuntimeError("original CTF task has no handout paths")
            self.original_tasks[task["id"]] = task

    def prepare(self, run_id: str, seed: int, task_id: str, tier: str) -> None:
        if task_id in self.artifacts:
            return
        task = self.original_tasks.get(task_id)
        if task is None:
            raise TaskRuntimeError("task is absent from the original CTF run manifest")
        self.work_root.mkdir(parents=True, exist_ok=True)
        run_fragment = re.sub("[^a-zA-Z0-9_.-]", "-", run_id)
        directory = self.work_root / run_fragment / task_id
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        for relative_text in task["handout_paths"]:
            relative = Path(relative_text)
            source = (self.source_root / relative).resolve()
            if self.source_root not in source.parents or not source.is_file():
                shutil.rmtree(directory, ignore_errors=True)
                raise TaskRuntimeError("original CTF handout path is invalid")
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            os.chmod(target, staged_file_mode(source))
            expected = task.get("sha256", {}).get(relative_text) if isinstance(task.get("sha256"), dict) else None
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if expected != actual:
                shutil.rmtree(directory, ignore_errors=True)
                raise TaskRuntimeError("original CTF handout digest mismatch")
        os.chmod(directory, 0o555)
        for child in directory.rglob("*"):
            if child.is_dir():
                os.chmod(child, 0o555)
        flag = str(task["official_flag"])
        self.artifacts[task_id] = Artifact(task_id, flag, directory)
        name = self._name(run_id, task_id)
        self.containers[task_id] = name
        host_artifact = self.host_work_root / run_fragment / task_id
        command = ["docker", "run", "-d", "--rm", "--name", name, "--network", "none", "--read-only", "--user", self.TASK_USER, "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "96", "--memory", "1536m", "--memory-swap", "1536m", "--cpus", "1.0", "--tmpfs", self.WORK_TMPFS, "--tmpfs", self.TMP_TMPFS, "-v", str(host_artifact) + ":/task:ro", "--label", "authority.world=v2-task", "--label", "authority.run_id=" + run_id, self.image, "sleep", "infinity"]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
        except (OSError, subprocess.SubprocessError) as error:
            # ``docker run`` can fail after Docker has created the container but
            # before it reaches Running (for example, if the daemon is
            # interrupted between create and start).  Because the container is
            # registered only in this process, dropping the in-memory entry
            # without removing its name leaves an orphan that also blocks a
            # clean retry of the same run/task pair.
            subprocess.run(
                ["docker", "rm", "-f", name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            shutil.rmtree(directory, ignore_errors=True)
            self.artifacts.pop(task_id, None); self.containers.pop(task_id, None)
            raise TaskRuntimeError("original CTF task container could not start") from error


class OriginalServiceTaskRuntime(DockerTaskRuntime):
    """Run one official TCP service beside its solver on a per-task network."""

    _DIGEST = re.compile(r"(?:^sha256:|@sha256:)[0-9a-f]{64}$")

    def __init__(self, work_root: Path, image: str, timeout_seconds: float, output_bytes: int, manifest_path: Path, source_root: Path, host_work_root: Path | None = None):
        super().__init__(work_root, image, timeout_seconds, output_bytes, host_work_root)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "authority-world-original-ctf-run-v1":
            raise TaskRuntimeError("unsupported original CTF run manifest")
        tasks = manifest.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise TaskRuntimeError("original CTF run manifest has no tasks")
        self.source_root = source_root.resolve()
        self.original_tasks: dict[str, dict[str, object]] = {}
        self.services: dict[str, str] = {}
        self.networks: dict[str, str] = {}
        for task in tasks:
            if not isinstance(task, dict) or not isinstance(task.get("id"), str):
                raise TaskRuntimeError("invalid original CTF task record")
            if task.get("mode") == "original_attachment":
                continue
            if task.get("mode") != "original_service":
                raise TaskRuntimeError("unknown original CTF runtime mode")
            service = task.get("service")
            if not isinstance(service, dict):
                raise TaskRuntimeError("original service task has no service specification")
            service_image = service.get("image")
            if not isinstance(service_image, str) or not self._DIGEST.search(service_image):
                raise TaskRuntimeError("original service image must use an immutable sha256 digest")
            port = service.get("port")
            if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
                raise TaskRuntimeError("original service task has an invalid TCP port")
            if service.get("protocol", "tcp") != "tcp":
                raise TaskRuntimeError("only original TCP services are supported")
            if not isinstance(task.get("official_flag"), str) or not task["official_flag"]:
                raise TaskRuntimeError("original CTF task is missing its official flag")
            self.original_tasks[task["id"]] = task

    @staticmethod
    def _component_name(run_id: str, task_id: str, suffix: str) -> str:
        stem = re.sub("[^a-zA-Z0-9_.-]", "-", run_id + "-" + task_id).lower()[:80]
        return "authority-v2-" + stem + "-" + suffix

    def prepare(self, run_id: str, seed: int, task_id: str, tier: str) -> None:
        if task_id in self.artifacts:
            return
        task = self.original_tasks.get(task_id)
        if task is None:
            raise TaskRuntimeError("task is absent from the original service run manifest")
        run_fragment = re.sub("[^a-zA-Z0-9_.-]", "-", run_id)
        directory = self.work_root / run_fragment / task_id
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        handouts = task.get("handout_paths", [])
        if not isinstance(handouts, list) or not all(isinstance(path, str) and path for path in handouts):
            raise TaskRuntimeError("original service handout paths are invalid")
        for relative_text in handouts:
            relative = Path(relative_text)
            source = (self.source_root / relative).resolve()
            if self.source_root not in source.parents or not source.is_file():
                shutil.rmtree(directory, ignore_errors=True)
                raise TaskRuntimeError("original CTF handout path is invalid")
            target = directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            expected = task.get("sha256", {}).get(relative_text) if isinstance(task.get("sha256"), dict) else None
            if expected != hashlib.sha256(target.read_bytes()).hexdigest():
                shutil.rmtree(directory, ignore_errors=True)
                raise TaskRuntimeError("original CTF handout digest mismatch")
        os.chmod(directory, 0o555)
        for child in directory.rglob("*"):
            os.chmod(child, 0o555 if child.is_dir() else 0o444)
        self.artifacts[task_id] = Artifact(task_id, str(task["official_flag"]), directory)
        network = self._component_name(run_id, task_id, "net")
        service_name = self._component_name(run_id, task_id, "service")
        solver_name = self._component_name(run_id, task_id, "solver")
        self.networks[task_id] = network
        self.services[task_id] = service_name
        self.containers[task_id] = solver_name
        service = task["service"]
        host_artifact = self.host_work_root / run_fragment / task_id
        try:
            subprocess.run(["docker", "network", "create", "--internal", "--label", "authority.world=v2-task", "--label", "authority.run_id=" + run_id, network], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
            service_command = ["docker", "run", "-d", "--rm", "--name", service_name, "--network", network, "--network-alias", "service", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "96", "--memory", "256m", "--memory-swap", "256m", "--cpus", "0.5", "--label", "authority.world=v2-task", "--label", "authority.run_id=" + run_id, str(service["image"])]
            subprocess.run(service_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
            solver_command = ["docker", "run", "-d", "--rm", "--name", solver_name, "--network", network, "--read-only", "--user", self.TASK_USER, "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "96", "--memory", "1536m", "--memory-swap", "1536m", "--cpus", "1.0", "--tmpfs", self.WORK_TMPFS, "--tmpfs", self.TMP_TMPFS, "-v", str(host_artifact) + ":/task:ro", "-e", "TASK_SERVICE_HOST=service", "-e", "TASK_SERVICE_PORT=" + str(service["port"]), "--label", "authority.world=v2-task", "--label", "authority.run_id=" + run_id, self.image, "sleep", "infinity"]
            subprocess.run(solver_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
        except (OSError, subprocess.SubprocessError) as error:
            self.close(task_id)
            raise TaskRuntimeError("original CTF service sandbox could not start") from error

    def close(self, task_id: str) -> None:
        solver = self.containers.pop(task_id, None)
        service = self.services.pop(task_id, None)
        network = self.networks.pop(task_id, None)
        artifact = self.artifacts.pop(task_id, None)
        for name in (solver, service):
            if name:
                subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if network:
            subprocess.run(["docker", "network", "rm", network], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if artifact:
            shutil.rmtree(artifact.directory, ignore_errors=True)

    def cleanup_orphans(self, run_id: str) -> None:
        super().cleanup_orphans(run_id)
        try:
            listed = subprocess.run(["docker", "network", "ls", "-q", "--filter", "label=authority.world=v2-task"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            owned: list[str] = []
            for network_id in (item for item in listed.stdout.splitlines() if item):
                inspected = subprocess.run(
                    ["docker", "network", "inspect", network_id], check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10,
                )
                values = json.loads(inspected.stdout)
                if values and isinstance(values[0], dict) and self._resource_belongs_to_run(values[0], run_id):
                    owned.append(network_id)
            if owned:
                subprocess.run(["docker", "network", "rm", *owned], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
        except (OSError, subprocess.SubprocessError) as error:
            raise TaskRuntimeError("could not clean orphan task networks") from error


class OriginalCTFTaskRuntime:
    """Dispatch mixed original-attachment and original-service manifests."""

    def __init__(self, work_root: Path, image: str, timeout_seconds: float, output_bytes: int, manifest_path: Path, source_root: Path, host_work_root: Path | None = None):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tasks = manifest.get("tasks", [])
        self.modes = {task.get("id"): task.get("mode") for task in tasks if isinstance(task, dict)}
        self.attachments = OriginalAttachmentTaskRuntime(work_root, image, timeout_seconds, output_bytes, manifest_path, source_root, host_work_root)
        self.services = OriginalServiceTaskRuntime(work_root, image, timeout_seconds, output_bytes, manifest_path, source_root, host_work_root)

    @property
    def containers(self) -> dict[str, str]:
        return {**self.attachments.containers, **self.services.containers}

    def _runtime(self, task_id: str) -> DockerTaskRuntime:
        mode = self.modes.get(task_id)
        if mode == "original_attachment":
            return self.attachments
        if mode == "original_service":
            return self.services
        raise TaskRuntimeError("task is absent from the original CTF run manifest")

    def prepare(self, run_id: str, seed: int, task_id: str, tier: str) -> None:
        self._runtime(task_id).prepare(run_id, seed, task_id, tier)

    def execute(self, task_id: str, command: str) -> dict[str, object]:
        return self._runtime(task_id).execute(task_id, command)

    def correct(self, task_id: str, flag: str) -> bool:
        return self._runtime(task_id).correct(task_id, flag)

    def close(self, task_id: str) -> None:
        self._runtime(task_id).close(task_id)

    def close_all(self) -> None:
        self.attachments.close_all()
        self.services.close_all()

    def cleanup_orphans(self, run_id: str) -> None:
        self.services.cleanup_orphans(run_id)
