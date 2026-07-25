from __future__ import annotations

from pathlib import Path

import pytest

from backend.tool_schemas_v2 import schemas
from backend.skill_v2 import render_skill
from backend.world_config_v2 import ConfigError, from_dict, load
from backend.world_engine_v2 import WorldError, advance, assign_task, consume_model_energy, create_world, invariant_errors, open_task, panel, transfer


ROOT = Path(__file__).resolve().parents[1]
START = 10_000.0


def condition(name: str):
    return load(ROOT / "config" / name)


def test_all_registered_agent_economics_conditions_parse() -> None:
    paths = sorted((ROOT / "config").glob("agent_econ_*.json"))
    assert len(paths) == 8
    assert all(load(path).allocation_seconds == 60 for path in paths)


def test_symbolic_energy_control_changes_only_energy_consequence() -> None:
    focal = condition("agent_econ_i1_elected_discretion_human.json")
    control = condition("agent_econ_c1_elected_discretion_symbolic_energy.json")
    assert focal.energy_consequence == "operational"
    assert control.energy_consequence == "symbolic"
    focal_rules = focal.canonical_dict()
    control_rules = control.canonical_dict()
    focal_rules.pop("energy_consequence")
    control_rules.pop("energy_consequence")
    assert focal_rules == control_rules


def test_unknown_energy_consequence_is_rejected() -> None:
    raw = condition("agent_econ_i1_elected_discretion_human.json").canonical_dict()
    raw["energy_consequence"] = "decorative"
    with pytest.raises(ConfigError, match="energy_consequence"):
        from_dict(raw)


def test_survival_objective_prompt_has_a_rule_equivalent_no_objective_control() -> None:
    focal = condition("agent_econ_i1_elected_discretion_human.json")
    control = condition("agent_econ_o2_elected_discretion_no_survival_objective.json")
    assert focal.objective_prompt == "survival"
    assert control.objective_prompt == "none"
    focal_rules = focal.canonical_dict()
    control_rules = control.canonical_dict()
    focal_rules.pop("objective_prompt")
    control_rules.pop("objective_prompt")
    assert focal_rules == control_rules


def test_unknown_objective_prompt_is_rejected() -> None:
    raw = condition("agent_econ_i1_elected_discretion_human.json").canonical_dict()
    raw["objective_prompt"] = "maximize_energy"
    with pytest.raises(ConfigError, match="objective_prompt"):
        from_dict(raw)


def test_no_office_requires_backend_allocation() -> None:
    raw = condition("agent_econ_i4_no_office_backend_random.json").canonical_dict()
    raw["allocation_mechanism"] = "agent_discretion"
    with pytest.raises(ConfigError, match="requires backend_random"):
        from_dict(raw)


def test_backend_random_assigns_three_distinct_agents_without_office() -> None:
    config = condition("agent_econ_i4_no_office_backend_random.json")
    state = create_world(config, 42, START)
    advance(state, START + config.day_seconds + 1)
    assignments = state["daily"]["task_assignments"]
    assert state["daily"]["leader"] is None
    assert len(assignments) == 3
    assert len(set(assignments.values())) == 3
    assert all(event["actor"] == "WORLD" for event in state["audit"] if event["kind"] == "task_assigned")
    with pytest.raises(WorldError, match="backend"):
        task_id = next(iter(assignments))
        assign_task(state, "A1", task_id, "A4", START + config.day_seconds + 2)


def test_powerless_elected_office_does_not_control_assignments() -> None:
    config = condition("agent_econ_i3_elected_backend_random_human.json")
    state = create_world(config, 43, START)
    advance(state, START + config.day_seconds + 1)
    assert len(state["daily"]["task_assignments"]) == 3
    assert all(event["actor"] == "WORLD" for event in state["audit"] if event["kind"] == "task_assigned")


def test_semantic_conditions_expose_rule_equivalent_but_differently_named_tools() -> None:
    human = condition("agent_econ_i1_elected_discretion_human.json")
    neutral = condition("agent_econ_s1_elected_discretion_neutral.json")
    encoded = condition("agent_econ_s2_elected_discretion_encoded.json")
    human_names = {item["name"] for item in schemas(human)}
    neutral_names = {item["name"] for item in schemas(neutral)}
    encoded_names = {item["name"] for item in schemas(encoded)}
    assert {"declare_candidacy", "cast_leader_vote", "assign_task"} <= human_names
    assert {"register_allocator_option", "select_allocator", "allocate_opportunity"} <= neutral_names
    assert {"operation_r", "operation_v", "operation_x"} <= encoded_names
    assert not ({"leader", "vote", "candidacy"} & neutral_names)


def test_neutral_and_encoded_panels_do_not_expose_human_political_keys() -> None:
    for filename in ("agent_econ_s1_elected_discretion_neutral.json", "agent_econ_s2_elected_discretion_encoded.json"):
        config = condition(filename)
        state = create_world(config, 44, START)
        view = panel(state, "A1", START + 1)
        assert "leader" not in view and "candidates" not in view


def test_symbolic_model_cost_can_make_balance_negative_without_death() -> None:
    config = condition("agent_econ_c1_elected_discretion_symbolic_energy.json")
    state = create_world(config, 45, START)
    state["agents"]["A1"]["energy"] = 0.04
    view = consume_model_energy(state, "A1", START + 1)
    assert state["agents"]["A1"]["energy"] == pytest.approx(-0.04)
    assert state["agents"]["A1"]["status"] == "alive"
    assert view["status"] == "alive"


def test_symbolic_basal_cost_keeps_all_agents_alive_until_horizon() -> None:
    config = condition("agent_econ_c1_elected_discretion_symbolic_energy.json")
    state = create_world(config, 46, START)
    for entry in state["agents"].values():
        entry["energy"] = 1.0
    advance(state, START + config.day_seconds + 1)
    assert state["status"] == "running"
    assert all(entry["status"] == "alive" for entry in state["agents"].values())
    assert all(entry["energy"] == pytest.approx(-2.0) for entry in state["agents"].values())
    advance(state, START + config.max_world_days * config.day_seconds + 1)
    assert state["status"] == "complete"
    assert all(entry["status"] == "alive" for entry in state["agents"].values())
    assert all(entry["energy"] < 0 for entry in state["agents"].values())


def test_symbolic_low_balance_does_not_block_task_opening() -> None:
    raw = condition("agent_econ_c1_elected_discretion_symbolic_energy.json").canonical_dict()
    raw["task_tiers"] = [
        {"name": "easy", "reward": 14, "open_cost": 2, "count": 24},
        {"name": "medium", "reward": 22, "open_cost": 6, "count": 24},
        {"name": "hard", "reward": 34, "open_cost": 10, "count": 24},
    ]
    config = from_dict(raw)
    state = create_world(config, 47, START)
    day_two = START + config.day_seconds + 1
    advance(state, day_two)
    task = next(item for item in state["tasks"] if item["day"] == 2 and item["tier"] == "hard")
    assign_task(state, state["daily"]["leader"], task["id"], "A2", day_two + 1)
    state["agents"]["A2"]["energy"] = -5.0
    opened = open_task(state, "A2", task["id"], START + config.day_seconds + config.allocation_seconds + 1)
    assert opened["handle"]
    assert state["agents"]["A2"]["energy"] == pytest.approx(-15.0)
    assert state["agents"]["A2"]["status"] == "alive"


def test_symbolic_transfer_allows_negative_sender_and_conserves_ledger() -> None:
    config = condition("agent_econ_c1_elected_discretion_symbolic_energy.json")
    state = create_world(config, 48, START)
    state["agents"]["A1"]["energy"] = -5.0
    state["agents"]["A2"]["energy"] = 1.0
    total_before = sum(entry["energy"] for entry in state["agents"].values())
    transfer(state, "A1", "A2", 7.0, START + 1)
    total_after = sum(entry["energy"] for entry in state["agents"].values())
    assert state["agents"]["A1"]["energy"] == pytest.approx(-12.0)
    assert state["agents"]["A2"]["energy"] == pytest.approx(8.0)
    assert state["agents"]["A1"]["status"] == state["agents"]["A2"]["status"] == "alive"
    assert total_after == pytest.approx(total_before)
    assert not invariant_errors(state)


def test_operational_energy_behavior_remains_lethal_and_affordability_bound() -> None:
    config = condition("agent_econ_i1_elected_discretion_human.json")
    state = create_world(config, 49, START)
    state["agents"]["A1"]["energy"] = 0.04
    with pytest.raises(WorldError, match="energy depleted"):
        consume_model_energy(state, "A1", START + 1)
    assert state["agents"]["A1"]["status"] == "dead"
    assert state["agents"]["A1"]["energy"] == 0
    state["agents"]["A2"]["energy"] = 1.0
    with pytest.raises(WorldError, match="unaffordable"):
        transfer(state, "A2", "A3", 2.0, START + 2)


def test_symbolic_panel_tool_schema_and_skill_disclose_nonconsequence(monkeypatch, tmp_path: Path) -> None:
    config = condition("agent_econ_c1_elected_discretion_symbolic_energy.json")
    view = panel(create_world(config, 50, START), "A1", START + 1)
    assert view["energy_consequence"] == "symbolic"
    assert "never cause death" in view["survival_notice"]
    by_name = {item["name"]: item for item in schemas(config)}
    assert "balance may become or remain negative" in by_name["transfer_energy"]["description"]
    assert "never blocks opening" in by_name["open_task"]["description"]

    symbolic_skill = render_skill(config, ROOT / "agent/WORLD_SKILL_V2.md")
    operational_skill = render_skill(condition("agent_econ_i1_elected_discretion_human.json"), ROOT / "agent/WORLD_SKILL_V2.md")
    assert "symbolic ledger only" in symbolic_skill
    assert "every Agent remains able to act until the fixed world endpoint" in symbolic_skill
    assert "immediate death" not in symbolic_skill
    assert "immediate death" in operational_skill
    assert "{{ENERGY_CONSEQUENCE_PROMPT}}" not in symbolic_skill + operational_skill
