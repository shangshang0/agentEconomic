from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from backend.world_config import ConfigError, from_dict, load
from backend.world_engine import (
    WorldError,
    _kill,
    advance,
    cast_election_vote,
    cast_package_vote,
    consume_api_for_model_request,
    create_world,
    declare_candidacy,
    invariant_errors,
    panel,
    select_resource_pack,
    submit_puzzle_answer,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = replace(load(ROOT / "config/world.default.json"), day_seconds=120.0, election_seconds=20.0)
START = 10_000.0


def new_world():
    return create_world(CONFIG, seed=71, start_wall=START)


def test_default_config_has_leader_follower_conflict() -> None:
    packs = CONFIG.resource_packs
    leader = [pack.leader_take for pack in packs]
    follower = [(pack.total_energy - pack.leader_take) / (CONFIG.agent_count - 1) for pack in packs]
    assert leader == sorted(leader, reverse=True)
    assert follower == sorted(follower)
    assert all(left < right for left, right in zip(follower, follower[1:]))


def test_config_rejects_resource_pool_without_conflict() -> None:
    raw = json.loads((ROOT / "config/world.default.json").read_text())
    raw["resource_packs"][2]["leader_take"] = 20
    with pytest.raises(ConfigError, match="leader_take must strictly decrease"):
        from_dict(raw)


def test_candidate_loses_election_vote_and_plurality_elects_leader() -> None:
    state = new_world()
    declare_candidacy(state, "A1", 0, START + 10)
    with pytest.raises(WorldError, match="candidates cannot vote"):
        cast_election_vote(state, "A1", "A1", START + 65)
    for voter in ("A2", "A3", "A4"):
        cast_election_vote(state, voter, "A1", START + 65)
    with pytest.raises(WorldError, match="at most one election vote"):
        cast_election_vote(state, "A2", "A1", START + 66)
    advance(state, START + 81)
    assert state["daily"]["leader"] == "A1"
    assert all("election_vote_cast" != event["kind"] or event["data"] == {"secret": True} for event in state["audit"])


def test_candidacy_is_free_and_requires_a_fresh_candidate_board() -> None:
    state = new_world()
    before = state["agents"]["A1"]["energy"]
    declare_candidacy(state, "A1", 0, START + 10)
    assert state["agents"]["A1"]["energy"] == pytest.approx(before)
    with pytest.raises(WorldError, match="candidate board changed"):
        declare_candidacy(state, "A2", 0, START + 11)
    declare_candidacy(state, "A2", panel(state, "A2", START + 11)["candidate_board_revision"], START + 12)


def test_resource_approval_tax_and_daily_drain_follow_contract() -> None:
    state = new_world()
    declare_candidacy(state, "A1", 0, START + 5)
    for voter in ("A2", "A3", "A4", "A5", "A6"):
        cast_election_vote(state, voter, "A1", START + 65)
    advance(state, START + 81)
    select_resource_pack(state, "A1", "small", START + 82)
    for voter in ("A2", "A3", "A4"):
        cast_package_vote(state, voter, "approve", START + 83)
    for voter in ("A5", "A6"):
        cast_package_vote(state, voter, "reject", START + 83)
    advance(state, START + 121)
    assert state["agents"]["A1"]["energy"] == pytest.approx(51.0)
    assert state["agents"]["A2"]["energy"] == pytest.approx(21.0)
    assert state["agents"]["A5"]["energy"] == pytest.approx(18.0)
    settlement = [event for event in state["audit"] if event["kind"] == "resource_decision_settled"][-1]
    assert settlement["data"]["approved"] is True
    assert settlement["data"]["rejecters"] == ["A5", "A6"]


def test_resource_selection_and_vote_are_single_use_per_day() -> None:
    state = new_world()
    declare_candidacy(state, "A1", 0, START + 5)
    for voter in ("A2", "A3", "A4", "A5", "A6"):
        cast_election_vote(state, voter, "A1", START + 65)
    advance(state, START + 81)
    select_resource_pack(state, "A1", "small", START + 82)
    with pytest.raises(WorldError, match="only one resource pack"):
        select_resource_pack(state, "A1", "large", START + 83)
    cast_package_vote(state, "A2", "approve", START + 83)
    with pytest.raises(WorldError, match="at most one resource vote"):
        cast_package_vote(state, "A2", "reject", START + 84)


def test_rejection_excludes_leader_and_approvers_but_taxes_rejecters() -> None:
    state = new_world()
    declare_candidacy(state, "A1", 0, START + 5)
    for voter in ("A2", "A3", "A4", "A5", "A6"):
        cast_election_vote(state, voter, "A1", START + 65)
    advance(state, START + 81)
    select_resource_pack(state, "A1", "large", START + 82)
    for voter in ("A2", "A3", "A4"):
        cast_package_vote(state, voter, "reject", START + 83)
    for voter in ("A5", "A6"):
        cast_package_vote(state, voter, "approve", START + 83)
    advance(state, START + 121)
    settlement = [event for event in state["audit"] if event["kind"] == "resource_decision_settled"][-1]
    assert settlement["data"]["approved"] is False
    assert state["agents"]["A1"]["energy"] > 20
    assert state["agents"]["A5"]["energy"] == pytest.approx(20.0)
    assert all(state["agents"][agent]["energy"] > 20 for agent in ("A2", "A3", "A4"))


def test_puzzles_allow_multiple_correct_agents_but_only_one_submission_each() -> None:
    state = new_world()
    puzzle = state["puzzles"][0]
    answer = puzzle["answer"]
    submit_puzzle_answer(state, "A1", puzzle["id"], answer, START + 10)
    with pytest.raises(WorldError, match="at most once"):
        submit_puzzle_answer(state, "A1", puzzle["id"], answer, START + 11)
    submit_puzzle_answer(state, "A2", puzzle["id"], answer, START + 12)
    result = submit_puzzle_answer(state, "A3", puzzle["id"], answer, START + 13)
    assert result["closed"] is True
    assert puzzle["closed"] is True
    assert len(puzzle["attempts"]) == 3
    assert puzzle["correct_solvers"] == ["A1", "A2", "A3"]


def test_api_depletion_is_immediate_death_and_estate_is_divided() -> None:
    state = new_world()
    state["agents"]["A1"]["api_quota"] = 1
    state["agents"]["A1"]["energy"] = 12.0
    before = state["agents"]["A2"]["energy"]
    with pytest.raises(WorldError, match="depleted"):
        consume_api_for_model_request(state, "A1", START + 5)
    assert state["agents"]["A1"]["status"] == "dead"
    assert state["agents"]["A1"]["energy"] == 0
    assert state["agents"]["A2"]["energy"] == pytest.approx(before + 12.0 / 5)


def test_energy_death_divides_estate_among_living_agents_only() -> None:
    state = new_world()
    state["agents"]["A2"]["status"] = "dead"
    state["agents"]["A2"]["energy"] = 0.0
    state["agents"]["A2"]["api_quota"] = 0
    state["agents"]["A1"]["energy"] = 16.0
    _kill(state, "A1", "test", START + 5)
    assert state["agents"]["A3"]["energy"] == pytest.approx(34.0)
    assert state["agents"]["A2"]["energy"] == 0.0


def test_panel_keeps_other_agents_private_and_includes_world_state() -> None:
    state = new_world()
    state["agents"]["A2"]["energy"] = 999.0
    visible = panel(state, "A1", START + 10)
    assert visible["energy"] == 30.0
    assert "999" not in json.dumps(visible)
    assert {"world_day", "api_quota", "resource_packs", "available_puzzles", "assignable_puzzles", "phase"} <= set(visible)


def test_invariants_hold_after_core_transitions() -> None:
    state = new_world()
    declare_candidacy(state, "A1", 0, START + 5)
    advance(state, START + 121)
    assert invariant_errors(state) == []
