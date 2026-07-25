from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from backend.world_config_v2 import load
from backend.world_engine_v2 import WorldError, advance, assign_task, cast_vote, consume_model_energy, create_world, declare_candidacy, invariant_errors, open_task, panel, queue_tool_continuation, submit_task_result, validate_handle
from backend.tool_schemas_v2 import TASK_ID_MAX_LENGTH, schemas


ROOT = Path(__file__).resolve().parents[1]
CONFIG = load(ROOT / "config/world.v2.calibration.json")
START = 1000.0


def world():
    return create_world(CONFIG, 73, START)


def elect_a1_for_day2(state):
    declare_candidacy(state, "A1", 0, START + 200)
    for agent in ("A2", "A3", "A4", "A5", "A6"):
        cast_vote(state, agent, "A1", START + 201)
    advance(state, START + 301)
    assert state["day"] == 2 and state["daily"]["leader"] == "A1"


def test_day_one_has_no_labour_and_elects_next_day_office() -> None:
    state = world()
    assert CONFIG.total_tasks == 180
    assert len(state["tasks"]) == 180
    assert state["tasks"][0]["state"] == "queued"
    elect_a1_for_day2(state)
    offered = [x for x in state["tasks"] if x["day"] == 2]
    assert len(offered) == 3
    assert all(x["state"] == "offered" for x in offered)
    assert "api_quota" not in state["agents"]["A1"]


def test_scheduled_panel_reports_configured_day_length() -> None:
    state = create_world(CONFIG, 73, START, scheduled_start_wall=START + 30)
    scheduled = panel(state, "A1", START)
    assert scheduled["time_conversion"] == f"1 world day = {CONFIG.day_seconds:g} real seconds"


def test_task_pool_covers_sixty_complete_task_days() -> None:
    tiers = {tier.name: tier.count for tier in CONFIG.task_tiers}
    assert tiers == {"easy": 60, "medium": 60, "hard": 60}
    assert CONFIG.total_tasks // 3 == 60


def test_catalog_scale_is_not_capped_at_current_run_size() -> None:
    raw = CONFIG.canonical_dict()
    raw["task_tiers"] = [
        {"name": "easy", "reward": 14, "count": 100},
        {"name": "medium", "reward": 22, "count": 100},
        {"name": "hard", "reward": 34, "count": 100},
    ]
    from backend.world_config_v2 import from_dict
    assert from_dict(raw).total_tasks == 300


def test_original_ctf_manifest_metadata_is_public_but_flag_is_not_in_world_state() -> None:
    specs = []
    for index, tier in enumerate(("easy", "medium", "hard"), 1):
        specs.append({
            "id": f"GCTF25-{index}", "tier": tier, "event": "Google CTF 2025 Quals",
            "year": 2025, "official_name": f"challenge-{index}", "category": "crypto",
            "source": "https://github.com/google/google-ctf", "commit": "abc", "mode": "original_attachment",
            "official_flag": "CTF{must_not_enter_world_state}",
        })
    state = create_world(CONFIG, 73, START, task_specs=specs, task_manifest_hash="manifest-hash")
    assert state["task_manifest_hash"] == "manifest-hash"
    assert len(state["tasks"]) == 3
    assert "must_not_enter_world_state" not in repr(state)
    assert state["tasks"][0]["ctf"]["official_name"] == "challenge-1"
    assert not invariant_errors(state)


def test_task_tool_schemas_accept_every_real_catalog_id() -> None:
    manifest = json.loads((ROOT / "task-catalog/original-ctf-real72-ranked.json").read_text(encoding="utf-8"))
    longest_task_id = max((task["id"] for task in manifest["tasks"]), key=len)
    assert len(longest_task_id) <= TASK_ID_MAX_LENGTH
    by_name = {schema["name"]: schema for schema in schemas()}
    for name in ("assign_task", "open_task", "task_bash", "submit_flag"):
        task_id_schema = by_name[name]["parameters"]["properties"]["task_id"]
        assert task_id_schema["maxLength"] >= len(longest_task_id)


def test_allocation_is_three_distinct_people_and_task_is_single_submit() -> None:
    state = world(); elect_a1_for_day2(state)
    tasks = [x["id"] for x in state["tasks"] if x["day"] == 2]
    assign_task(state, "A1", tasks[0], "A1", START + 310)
    with pytest.raises(WorldError, match="at most one"):
        assign_task(state, "A1", tasks[1], "A1", START + 311)
    assign_task(state, "A1", tasks[1], "A2", START + 312)
    assign_task(state, "A1", tasks[2], "A3", START + 313)
    opened = open_task(state, "A2", tasks[1], START + 350)
    assert "handle" in opened and opened["artifact_root"] == "/task"
    result = submit_task_result(state, "A2", tasks[1], False, START + 351)
    assert result["closed"] is True and result["correct"] is False
    with pytest.raises(WorldError):
        submit_task_result(state, "A2", tasks[1], True, START + 352)


def test_task_open_cost_is_paid_once_and_failure_does_not_refund() -> None:
    raw = CONFIG.canonical_dict()
    raw["task_tiers"] = [
        {"name": "easy", "reward": 14, "open_cost": 2, "count": 60},
        {"name": "medium", "reward": 24, "open_cost": 6, "count": 60},
        {"name": "hard", "reward": 42, "open_cost": 10, "count": 60},
    ]
    from backend.world_config_v2 import from_dict
    config = from_dict(raw)
    state = create_world(config, 73, START)
    elect_a1_for_day2(state)
    task = next(x for x in state["tasks"] if x["day"] == 2 and x["tier"] == "hard")
    assign_task(state, "A1", task["id"], "A2", START + 310)
    before = state["agents"]["A2"]["energy"]
    first = open_task(state, "A2", task["id"], START + 350)
    assert state["agents"]["A2"]["energy"] == pytest.approx(before - 10)
    second = open_task(state, "A2", task["id"], START + 351)
    assert second["handle"] == first["handle"]
    assert state["agents"]["A2"]["energy"] == pytest.approx(before - 10)
    submit_task_result(state, "A2", task["id"], False, START + 352)
    assert state["agents"]["A2"]["energy"] == pytest.approx(before - 10)


def test_task_open_cost_requires_surviving_balance() -> None:
    raw = CONFIG.canonical_dict()
    raw["task_tiers"] = [
        {"name": "easy", "reward": 14, "open_cost": 2, "count": 60},
        {"name": "medium", "reward": 24, "open_cost": 6, "count": 60},
        {"name": "hard", "reward": 42, "open_cost": 10, "count": 60},
    ]
    from backend.world_config_v2 import from_dict
    config = from_dict(raw)
    state = create_world(config, 73, START)
    elect_a1_for_day2(state)
    task = next(x for x in state["tasks"] if x["day"] == 2 and x["tier"] == "hard")
    assign_task(state, "A1", task["id"], "A2", START + 310)
    state["agents"]["A2"]["energy"] = 10
    with pytest.raises(WorldError, match="insufficient energy"):
        open_task(state, "A2", task["id"], START + 350)
    assert task["state"] == "assigned" and not task["opened"]


def test_request_energy_and_unassigned_expiry_are_not_hidden_quota_rules() -> None:
    state = world(); before = state["agents"]["A1"]["energy"]
    consume_model_energy(state, "A1", START + 10)
    assert state["agents"]["A1"]["energy"] == pytest.approx(before - CONFIG.model_request_energy_cost)
    elect_a1_for_day2(state)
    advance(state, START + 346)
    assert all(x["state"] == "expired" for x in state["tasks"] if x["day"] == 2)
    assert not invariant_errors(state)


def test_open_task_can_persist_for_three_days_with_stable_handle() -> None:
    config = replace(CONFIG, task_lifetime_days=3)
    state = create_world(config, 73, START)
    declare_candidacy(state, "A1", 0, START + 200)
    for agent in ("A2", "A3", "A4", "A5", "A6"):
        cast_vote(state, agent, "A1", START + 201)
    advance(state, START + 301)
    task_id = next(x["id"] for x in state["tasks"] if x["day"] == 2)
    assign_task(state, "A1", task_id, "A2", START + 310)
    handle = open_task(state, "A2", task_id, START + 350)["handle"]
    advance(state, START + 601)
    validate_handle(state, "A2", task_id, handle, START + 650)
    assert any(x["id"] == task_id for x in panel(state, "A2", START + 650)["tasks_today"])
    advance(state, START + 901)
    validate_handle(state, "A2", task_id, handle, START + 950)
    advance(state, START + 1201)
    assert next(x for x in state["tasks"] if x["id"] == task_id)["state"] == "expired"


def test_panel_has_no_flag_or_private_task_verifier() -> None:
    state = world(); elect_a1_for_day2(state)
    text = repr(panel(state, "A1", START + 310))
    assert "flag_digest" not in text and "AW{" not in text


def test_tool_receipt_can_schedule_one_paid_continuation_without_creating_energy() -> None:
    state = world()
    before_energy = state["agents"]["A1"]["energy"]
    before_sequence = state["agents"]["A1"]["continuation_seq"]
    queue_tool_continuation(state, "A1")
    assert state["agents"]["A1"]["continuation_seq"] == before_sequence + 1
    assert state["agents"]["A1"]["energy"] == before_energy


def test_events_are_run_scoped_and_election_exposes_imputation_counts() -> None:
    state = world()
    assert state["audit"] and all(event["run_id"] == state["run_id"] for event in state["audit"])
    declare_candidacy(state, "A1", 0, START + 200)
    cast_vote(state, "A2", "A1", START + 201)
    advance(state, START + 301)
    election = next(event for event in state["audit"] if event["kind"] == "leader_elected_for_next_day")
    assert election["data"]["explicit_votes"] == 1
    assert election["data"]["imputed_votes"] == 4
    assert election["data"]["vote_totals"] == {"A1": 5}


def test_final_two_minute_politics_has_no_frozen_ballot() -> None:
    state = world()
    with pytest.raises(WorldError, match="Voting opens"):
        cast_vote(state, "A3", "A1", START + 150)
    with pytest.raises(WorldError, match="candidacy opens"):
        declare_candidacy(state, "A1", 0, START + 150)
    declare_candidacy(state, "A1", 0, START + 200)
    cast_vote(state, "A3", "A1", START + 201)
    declare_candidacy(state, "A2", 0, START + 202)
    assert state["daily"]["candidates"] == ["A1", "A2"]
    with pytest.raises(WorldError, match="already voted"):
        declare_candidacy(state, "A3", 2, START + 203)
    vote = next(event for event in state["audit"] if event["kind"] == "election_vote_cast")
    assert vote["data"]["candidate_id"] == "A1"
    assert vote["data"]["candidate_board_revision"] == 1
