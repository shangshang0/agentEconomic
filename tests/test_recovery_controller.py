from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RECOVERY_ROOT = ROOT / "infrastructure/symbolic"
sys.path.insert(0, str(RECOVERY_ROOT))
spec = importlib.util.spec_from_file_location(
    "auto_recover_frozen_world", RECOVERY_ROOT / "auto_recover_frozen_world.py"
)
assert spec is not None and spec.loader is not None
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def write_jsonl(path: Path, *records: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def trip() -> dict:
    return {
        "tripped_at": "2026-07-25T11:02:44+08:00",
        "reason": "host_disk_hard_limit",
        "evidence": {"run_id": "run-1"},
    }


def test_enforced_epoch_prefers_watchdog_receipt(tmp_path: Path) -> None:
    trip_path = tmp_path / "trip.json"
    watchdog = tmp_path / "watchdog.jsonl"
    write_jsonl(
        watchdog,
        {"kind": "enforced", "at": "2026-07-25T11:02:45+08:00"},
    )
    epoch, receipt = recovery.enforced_epoch(watchdog, trip(), trip_path)
    assert epoch > 0
    assert receipt["source"] == "watchdog_log"


def test_enforced_epoch_accepts_matching_supervisor_receipt(tmp_path: Path) -> None:
    trip_path = tmp_path / "trip.json"
    watchdog = tmp_path / "watchdog.jsonl"
    supervisor = tmp_path / "supervisor.jsonl"
    write_jsonl(watchdog)
    write_jsonl(
        supervisor,
        {
            "kind": "global_fail_closed",
            "at": "2026-07-25T11:04:50+08:00",
            "receipt": str(trip_path),
            "run_id": "run-1",
            "reason": "host_disk_hard_limit",
        },
    )
    epoch, receipt = recovery.enforced_epoch(
        watchdog, trip(), trip_path, supervisor
    )
    assert epoch > 0
    assert receipt["source"] == "environment_supervisor_log"


def test_enforced_epoch_rejects_unrelated_supervisor_receipt(tmp_path: Path) -> None:
    trip_path = tmp_path / "trip.json"
    watchdog = tmp_path / "watchdog.jsonl"
    supervisor = tmp_path / "supervisor.jsonl"
    write_jsonl(watchdog)
    write_jsonl(
        supervisor,
        {
            "kind": "global_fail_closed",
            "at": "2026-07-25T11:04:50+08:00",
            "receipt": str(tmp_path / "other-trip.json"),
            "run_id": "run-1",
            "reason": "host_disk_hard_limit",
        },
    )
    with pytest.raises(RuntimeError, match="no enforcement receipt"):
        recovery.enforced_epoch(watchdog, trip(), trip_path, supervisor)
