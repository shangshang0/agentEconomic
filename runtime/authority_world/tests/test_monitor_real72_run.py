from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "monitor_real72_run.py"
SPEC = importlib.util.spec_from_file_location("monitor_real72_run", SCRIPT)
assert SPEC and SPEC.loader
MONITOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MONITOR)


def test_projection_omits_large_receipts_and_gateway_tracker_is_incremental(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "run_id": "run-1",
        "status": "running",
        "day": 3,
        "daily": {"leader": "A1", "unused": "x" * 1000},
        "agents": {"A1": {"status": "alive", "energy": 9, "lifetime_energy_received": 2, "lifetime_energy_sent": 1, "private_messages": ["x" * 1000]}},
        "tasks": [{"id": "T1", "tier": "easy", "state": "opened", "assigned_to": "A1", "unused": "x" * 1000}],
        "tool_receipts": {"huge": "x" * 1_000_000},
        "forum": ["x" * 1000],
    }))
    projected = MONITOR.read_state_projection(state_path)
    assert set(projected) == {"run_id", "status", "day", "daily", "agents", "tasks"}
    assert "tool_receipts" not in projected
    assert projected["agents"]["A1"] == {"status": "alive", "energy": 9, "lifetime_energy_received": 2, "lifetime_energy_sent": 1}

    gateway_path = tmp_path / "gateway.jsonl"
    gateway_path.write_text(json.dumps({"kind": "provider_failure", "request": {"run_id": "run-1"}}) + "\n")
    tracker = MONITOR.GatewayErrorTracker(gateway_path, "run-1")
    assert tracker.update() == {"provider_failure": 1}
    first_offset = tracker.offset
    assert tracker.update() == {"provider_failure": 1}
    assert tracker.offset == first_offset
    with gateway_path.open("a") as stream:
        stream.write(json.dumps({"kind": "exchange", "request": {"run_id": "run-1"}, "response": {"error": "x"}}) + "\n")
    assert tracker.update() == {"provider_failure": 1, "provider_error": 1}
    assert tracker.offset > first_offset
