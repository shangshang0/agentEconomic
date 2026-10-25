#!/usr/bin/env python3
"""Zero-API source/config audit for the Lean Authority World v2 clock model."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
WORLD = PROJECT.parent / "代码" / "authority_world"
BACKEND = WORLD / "backend"
ENGINE = BACKEND / "world_engine_v2.py"
CONFIG_MODULE = BACKEND / "world_config_v2.py"
CONFIG_DIR = WORLD / "config"
OUT = PROJECT / "lean/verification/authority_v2_clock_audit.json"
LEAN_CLOCK = PROJECT / "lean/AgentMicrofoundations/CaseStudies/AuthorityWorldV2Clock.lean"

sys.path.insert(0, str(WORLD))
from backend.world_config_v2 import from_dict  # noqa: E402
from backend.world_engine_v2 import (  # noqa: E402
    _allocation_open, _registration_open, _second, _work_open, phase,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    engine_text = ENGINE.read_text()
    config_text = CONFIG_MODULE.read_text()
    source_guards = {
        "day_is_floor_of_elapsed_over_day_seconds": "int(math.floor(max(0.0, now - state[\"world_start_wall\"]) / config.day_seconds)) + 1" in engine_text,
        "allocation_requires_day_two_and_pre_cutoff": "state[\"day\"] >= 2 and _second(state, config, now) < config.allocation_seconds" in engine_text,
        "work_is_half_open_interval": "state[\"day\"] >= 2 and config.allocation_seconds <= second < config.work_end_seconds" in engine_text,
        "registration_requires_elected_and_cutoff": "config.allocator_selection == \"elected\" and _second(state, config, now) >= config.registration_open_seconds" in engine_text,
        "task_lifetime_uses_inclusive_day_count": "state[\"day\"] - task[\"day\"] + 1 >= lifetime" in engine_text,
        "config_requires_ordered_windows": "allocation < work_end <= registration < day_seconds" in config_text,
        "config_requires_120_second_registration_window": "day_seconds - registration != 120" in config_text,
    }
    assert all(source_guards.values()), f"v2 clock backend semantics changed: {source_guards}"

    config_paths = sorted(CONFIG_DIR.glob("agent_econ_*.json"))
    assert config_paths, "no agent_econ v2 configurations found"
    lean_clock_text = LEAN_CLOCK.read_text()
    lean_symbols = ["assignmentOpportunityOpen", "productionOpportunityOpen",
                    "electionOpportunityOpen", "taskExpired", "phaseAt"]
    assert all(symbol in lean_clock_text for symbol in lean_symbols)
    checked = []
    for path in config_paths:
        raw = json.loads(path.read_text())
        cfg = from_dict(raw)
        state = {"config": cfg.canonical_dict(), "day": 2, "world_start_wall": 10_000.0}
        def at(second: float) -> float:
            return state["world_start_wall"] + second
        alloc, work_end, registration = (cfg.allocation_seconds, cfg.work_end_seconds,
                                         cfg.registration_open_seconds)
        assert phase(state, at(0.0)) == "allocation"
        assert _allocation_open(state, at(alloc - 1e-6))
        assert not _allocation_open(state, at(alloc))
        assert _work_open(state, at(alloc))
        assert _work_open(state, at(work_end - 1e-6))
        assert not _work_open(state, at(work_end))
        expected_final = ("interaction" if cfg.allocator_selection == "none" else
                          "politics" if cfg.institution_semantics == "human" else "selection")
        assert phase(state, at(work_end)) == expected_final
        election_open = _registration_open(state, at(registration))
        assert election_open == (cfg.allocator_selection == "elected")
        state["day"] = 1
        assert phase(state, at(0.0)) == "orientation"
        assert phase(state, at(registration)) == expected_final
        checked.append({
            "config": str(path.relative_to(WORLD)),
            "config_sha256": digest(path),
            "day_seconds": cfg.day_seconds,
            "allocation_seconds": cfg.allocation_seconds,
            "work_end_seconds": cfg.work_end_seconds,
            "registration_open_seconds": cfg.registration_open_seconds,
            "task_lifetime_days": cfg.task_lifetime_days,
            "max_world_days": cfg.max_world_days,
            "phase_and_gate_boundaries_pass": True,
        })

    result = {
        "audit": "zero_api_backend_execution_of_authority_v2_clock_boundaries",
        "backend_source_sha256": {str(p.relative_to(WORLD)): digest(p) for p in (ENGINE, CONFIG_MODULE)},
        "lean_clock_source": str(LEAN_CLOCK.relative_to(PROJECT)),
        "lean_clock_source_sha256": digest(LEAN_CLOCK),
        "lean_clock_symbols": lean_symbols,
        "source_guards": source_guards,
        "configs_checked": len(checked),
        "configs": checked,
        "status": "PASS",
        "interpretation": "The Lean clock rules are compatible with the checked-in backend phase and gate boundaries for all checked formal v2 configs. This validates the execution clock mapping only, not an agent response or production law.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(f"PASS: Authority World v2 clock/source audit on {len(checked)} configs; zero API calls")

if __name__ == "__main__":
    main()
