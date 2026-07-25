from __future__ import annotations

import pytest

from scripts.run_agent_economics_experiment import registered_runs, select_registered_seeds


def protocol(status: str = "frozen_after_discovery") -> dict:
    return {
        "mechanism_validation": {
            "status": status,
            "replicates_per_model": 2,
            "seed_base": 2026080000,
            "models": [
                {"id": "m1", "env_file": ".env.m1"},
                {"id": "m2", "env_file": ".env.m2"},
            ],
            "conditions": [
                {"id": "c1", "config": "config/c1.json", "estimand": "e1"},
                {"id": "c2", "config": "config/c2.json", "estimand": "e2"},
            ],
        }
    }


def test_mechanism_runs_are_condition_model_and_seed_separated() -> None:
    runs = registered_runs(protocol(), "mechanism-validation", None)
    assert len(runs) == 8
    assert {(run["condition"], run["model"]) for run in runs} == {
        ("c1", "m1"), ("c1", "m2"), ("c2", "m1"), ("c2", "m2")
    }
    assert len({run["seed"] for run in runs}) == 8


def test_mechanism_runner_refuses_unfrozen_protocol() -> None:
    with pytest.raises(RuntimeError, match="post-discovery"):
        registered_runs(protocol("do_not_run_before_discovery_codebook_is_frozen"), "mechanism-validation", None)


def test_only_seed_selects_preregistered_infrastructure_rerun() -> None:
    runs = registered_runs(protocol(), "mechanism-validation", None)
    selected = select_registered_seeds(runs, [2026080002])
    assert len(selected) == 1
    assert selected[0]["seed"] == 2026080002


def test_only_seed_refuses_unregistered_seed() -> None:
    runs = registered_runs(protocol(), "mechanism-validation", None)
    with pytest.raises(RuntimeError, match="not preregistered"):
        select_registered_seeds(runs, [2026999999])
