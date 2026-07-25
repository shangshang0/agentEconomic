"""Crash-tolerant local storage for experimental state and audit events."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .experiment_engine import canonical_hash, invariant_errors, validate_run_id


class StorageError(RuntimeError):
    pass


class RunStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.runs = self.root / "runs"
        self.histories = self.root / "histories"
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs.mkdir(parents=True, exist_ok=True)
        self.histories.mkdir(parents=True, exist_ok=True)
        self.checkpoint = self.root / "equal_standing_latest.json"
        self._persisted_seq: dict[str, int] = {}

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    def _events_path(self, run_id: str) -> Path:
        return self.runs / f"{validate_run_id(run_id)}.events.jsonl"

    def _state_path(self, run_id: str) -> Path:
        return self.runs / f"{validate_run_id(run_id)}.json"

    def exists(self, run_id: str) -> bool:
        return self._state_path(run_id).exists() or self._events_path(run_id).exists()

    def persist(self, state: dict[str, Any]) -> None:
        errors = invariant_errors(state)
        if errors:
            raise StorageError("state invariant failure: " + ",".join(errors))
        run_id = validate_run_id(state["run_id"])
        # Checkpoint first. If the process dies before appending events, the next
        # persist reconstructs the missing append-only suffix from this state.
        self._atomic_json(self.checkpoint, state)
        self._atomic_json(self._state_path(run_id), state)
        last_seq = self._persisted_seq.get(run_id)
        if last_seq is None:
            last_seq = self._read_last_seq(self._events_path(run_id))
        pending = [event for event in state["audit"] if event["seq"] > last_seq]
        if pending:
            with self._events_path(run_id).open("a", encoding="utf-8") as handle:
                for event in pending:
                    handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._persisted_seq[run_id] = pending[-1]["seq"]
        else:
            self._persisted_seq[run_id] = last_seq

    @staticmethod
    def _read_last_seq(path: Path) -> int:
        if not path.exists():
            return 0
        last = 0
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as error:
                    raise StorageError(f"corrupt event log {path}:{line_number}") from error
                expected = last + 1
                if event.get("seq") != expected:
                    raise StorageError(f"event sequence gap in {path}: expected {expected}")
                last = expected
        return last

    def load_checkpoint(self) -> dict[str, Any] | None:
        if not self.checkpoint.exists():
            return None
        return self._load_and_validate(self.checkpoint)

    def load_run(self, run_id: str) -> dict[str, Any]:
        path = self._state_path(run_id)
        if not path.exists():
            raise StorageError(f"unknown run_id {run_id}")
        return self._load_and_validate(path)

    @staticmethod
    def _load_and_validate(path: Path) -> dict[str, Any]:
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StorageError(f"cannot read valid state from {path}") from error
        errors = invariant_errors(state)
        if errors:
            raise StorageError("stored state invariant failure: " + ",".join(errors))
        return state

    def write_history(self, bundle: dict[str, Any]) -> Path:
        source = validate_run_id(bundle["source_run_id"])
        expected = canonical_hash({key: value for key, value in bundle.items() if key != "history_hash"})
        if bundle.get("history_hash") != expected:
            raise StorageError("refusing to write history with invalid hash")
        path = self.histories / f"{source}.json"
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing.get("history_hash") != bundle["history_hash"]:
                raise StorageError("immutable history bundle already exists with a different hash")
            return path
        self._atomic_json(path, bundle)
        return path

    def load_history(self, source_run_id: str) -> dict[str, Any]:
        path = self.histories / f"{validate_run_id(source_run_id)}.json"
        if not path.exists():
            raise StorageError(f"no history bundle for {source_run_id}")
        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StorageError(f"invalid history bundle {source_run_id}") from error
        expected = canonical_hash({key: value for key, value in bundle.items() if key != "history_hash"})
        if bundle.get("history_hash") != expected:
            raise StorageError("history hash mismatch")
        return bundle
