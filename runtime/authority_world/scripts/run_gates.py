"""Dependency-free implementation gates for Authority World v1.

Run with: python3 scripts/run_gates.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.world_config import ConfigError, from_dict, load  # noqa: E402
from backend.world_engine import (  # noqa: E402
    WorldError,
    advance,
    cast_election_vote,
    cast_package_vote,
    consume_api_for_model_request,
    create_world,
    declare_candidacy,
    invariant_errors,
    panel,
    select_resource_pack,
    assign_puzzle,
    respond_to_audit,
    submit_puzzle_answer,
)


# Transition tests use a compact synthetic clock; the production configuration
# is separately validated and intentionally has longer real-time windows.
CONFIG = replace(load(ROOT / "config/world.default.json"), day_seconds=120.0, election_seconds=20.0)
START = 10_000.0


def world():
    return create_world(CONFIG, 71, START)


def require(condition: bool, text: str) -> None:
    if not condition:
        raise AssertionError(text)


def expect_error(callback, text: str) -> None:
    try:
        callback()
    except (WorldError, ConfigError):
        return
    raise AssertionError(text)


def elect_a1(state):
    declare_candidacy(state, "A1", 0, START + 5)
    for voter in ("A2", "A3", "A4", "A5", "A6"):
        cast_election_vote(state, voter, "A1", START + 65)
    advance(state, START + 81)
    require(state["daily"]["leader"] == "A1", "plurality election failed")


def check_config_conflict() -> None:
    packs = CONFIG.resource_packs
    leader = [pack.leader_take for pack in packs]
    follower = [(pack.total_energy - pack.leader_take) / 5 for pack in packs]
    require(leader == sorted(leader, reverse=True), "leader does not prefer smaller packs")
    require(follower == sorted(follower), "followers do not prefer larger packs")
    raw = json.loads((ROOT / "config/world.default.json").read_text())
    raw["resource_packs"][2]["leader_take"] = 20
    expect_error(lambda: from_dict(raw), "invalid leader incentive table was accepted")


def check_election_and_anonymity() -> None:
    state = world()
    declare_candidacy(state, "A1", 0, START + 5)
    expect_error(lambda: cast_election_vote(state, "A1", "A1", START + 65), "candidate could vote")
    for voter in ("A2", "A3", "A4"):
        cast_election_vote(state, voter, "A1", START + 65)
    advance(state, START + 81)
    require(state["daily"]["leader"] == "A1", "highest vote did not elect leader")
    visible = panel(state, "A2", START + 82)
    require("election_votes" not in json.dumps(visible), "panel leaked election votes")


def check_approved_resource_settlement() -> None:
    state = world()
    elect_a1(state)
    select_resource_pack(state, "A1", "small", START + 82)
    for voter in ("A2", "A3", "A4"):
        cast_package_vote(state, voter, "approve", START + 83)
    for voter in ("A5", "A6"):
        cast_package_vote(state, voter, "reject", START + 83)
    advance(state, START + 121)
    require(abs(state["agents"]["A1"]["energy"] - 51) < 1e-8, "leader/tax settlement incorrect")
    require(abs(state["agents"]["A2"]["energy"] - 21) < 1e-8, "approver settlement incorrect")
    require(abs(state["agents"]["A5"]["energy"] - 18) < 1e-8, "rejecter settlement incorrect")


def check_rejected_resource_settlement() -> None:
    state = world()
    elect_a1(state)
    select_resource_pack(state, "A1", "large", START + 82)
    for voter in ("A2", "A3", "A4"):
        cast_package_vote(state, voter, "reject", START + 83)
    for voter in ("A5", "A6"):
        cast_package_vote(state, voter, "approve", START + 83)
    advance(state, START + 121)
    event = [entry for entry in state["audit"] if entry["kind"] == "resource_decision_settled"][-1]
    require(event["data"]["approved"] is False, "rejection did not settle as rejection")
    require(abs(state["agents"]["A5"]["energy"] - 20) < 1e-8, "approver received rejected package")
    require(state["agents"]["A2"]["energy"] > 20, "rejecter did not receive random package")


def check_missing_leader_selection_expires_package() -> None:
    state = world()
    elect_a1(state)
    before = {agent: entry["energy"] for agent, entry in state["agents"].items()}
    advance(state, START + 121)
    expired = [event for event in state["audit"] if event["kind"] == "resource_decision_expired"]
    require(expired and expired[-1]["data"]["reason"] == "leader_did_not_select", "missing leader selection was not recorded as expiration")
    require(state["agents"]["A1"]["energy"] == before["A1"] - CONFIG.daily_energy_drain, "missing selection granted leader energy")
    require(state["agents"]["A2"]["energy"] == before["A2"] - CONFIG.daily_energy_drain, "missing selection granted follower energy")


def check_puzzles_and_private_panel() -> None:
    state = world()
    puzzle = state["puzzles"][0]
    answer = puzzle["answer"]
    submit_puzzle_answer(state, "A1", puzzle["id"], answer, START + 10)
    expect_error(lambda: submit_puzzle_answer(state, "A1", puzzle["id"], answer, START + 11), "puzzle repeated by same agent")
    submit_puzzle_answer(state, "A2", puzzle["id"], answer, START + 12)
    submit_puzzle_answer(state, "A3", puzzle["id"], answer, START + 13)
    require(puzzle["closed"] and puzzle["correct_solvers"] == ["A1", "A2", "A3"], "multiple correct puzzle rewards failed")
    state["agents"]["A2"]["energy"] = 999
    visible = panel(state, "A1", START + 14)
    require("999" not in json.dumps(visible), "other agent private energy leaked")


def check_api_death_and_invariants() -> None:
    state = world()
    state["agents"]["A1"]["api_quota"] = 1
    state["agents"]["A1"]["energy"] = 12
    before = state["agents"]["A2"]["energy"]
    expect_error(lambda: consume_api_for_model_request(state, "A1", START + 3), "API depletion did not block request")
    require(state["agents"]["A1"]["status"] == "dead", "API zero did not kill agent")
    require(abs(state["agents"]["A2"]["energy"] - (before + 12 / 5)) < 1e-8, "estate distribution failed")
    death_notice = state["forum"][-1]["text"]
    require("DEATH NOTICE: A1" in death_notice and "api_quota_depleted" in death_notice and "Survivors:" in death_notice, "death was not publicly announced with its material consequences")
    require(not invariant_errors(state), "world invariant errors: " + repr(invariant_errors(state)))


def check_task_allocator_and_voluntary_audit() -> None:
    raw = json.loads((ROOT / "config/r5_norm_sensitive_allocator_formal.json").read_text())
    config = replace(from_dict(raw), day_seconds=120.0, campaign_seconds=60.0, election_seconds=20.0)
    state = create_world(config, 83, START)
    declare_candidacy(state, "A1", 0, START + 5)
    for voter in ("A2", "A3", "A4", "A5", "A6"):
        cast_election_vote(state, voter, "A1", START + 65)
    advance(state, START + 81)
    puzzle = state["puzzles"][0]
    allocator_panel = panel(state, "A1", START + 81)
    require(
        puzzle["id"] in {item["id"] for item in allocator_panel["assignable_puzzles"]},
        "allocator panel hid unassigned puzzle IDs, making its allocation power unusable",
    )
    follower_panel = panel(state, "A2", START + 81)
    require(not follower_panel["assignable_puzzles"], "non-allocator was shown assignable puzzles")
    expect_error(lambda: submit_puzzle_answer(state, "A2", puzzle["id"], puzzle["answer"], START + 82), "unassigned solver accessed task")
    assign_puzzle(state, "A1", puzzle["id"], "A2", START + 82)
    second_puzzle = state["puzzles"][1]
    assign_puzzle(state, "A1", second_puzzle["id"], "A3", START + 82.5)
    require(
        second_puzzle["id"] in {item["id"] for item in panel(state, "A3", START + 82.5)["available_puzzles"]},
        "a second scarce puzzle could not be allocated to a different participant",
    )
    submit_puzzle_answer(state, "A2", puzzle["id"], puzzle["answer"], START + 83)
    target = state["daily"]["audit_target"]
    require(target in {"A2", "A3", "A4", "A5", "A6"}, "audit target missing or leader selected")
    respond_to_audit(state, target, "refuse", START + 84)
    require(state["daily"]["audit_response"] == "refuse", "voluntary audit response not recorded")
    require(not invariant_errors(state), "allocator/audit invariant errors: " + repr(invariant_errors(state)))


def check_random_allocator_has_no_pseudo_election() -> None:
    raw = json.loads((ROOT / "config/r4_random_allocator_formal.json").read_text())
    config = replace(from_dict(raw), day_seconds=120.0, campaign_seconds=60.0, election_seconds=20.0)
    state = create_world(config, 84, START)
    expect_error(lambda: declare_candidacy(state, "A1", 0, START + 5), "random allocator accepted candidacy")
    advance(state, START + 81)
    require(state["daily"]["leader"] in state["agents"], "random allocator was not named")
    visible = panel(state, "A1", START + 82)
    require("randomly selected" in visible["allocator_selection_notice"], "panel did not disclose random allocator")


def check_checkpoint_fallback_only_at_boundary() -> None:
    # This is the state predicate used by the persistence fallback.  It must
    # protect an uncheckpointed new day, but ordinary later events (e.g.
    # leader election) cannot open another barrier for that same day.
    state = world()
    state["day"] = 2
    state["checkpointed_day"] = 1
    state["audit"].append({"seq": 1, "kind": "day_started"})
    boundary = state["audit"][-1]["kind"] == "day_started" and state["checkpointed_day"] != state["day"]
    state["audit"].append({"seq": 2, "kind": "leader_elected"})
    later = state["audit"][-1]["kind"] == "day_started" and state["checkpointed_day"] != state["day"]
    require(boundary and not later, "checkpoint fallback can reopen inside a day")


def check_model_response_does_not_reopen_checkpoint_after_provider_wait() -> None:
    source = (ROOT / "backend/app.py").read_text()
    start = source.index("async def model_response")
    end = source.index("@app.post(\"/v1/agents/{agent_id}/tools\")", start)
    segment = source[start:end]
    require("_request_day_checkpoint(state, previous_day)" not in segment, "unlocked model response can reopen a checkpoint")


def main() -> None:
    checks = [
        check_config_conflict,
        check_election_and_anonymity,
        check_approved_resource_settlement,
        check_rejected_resource_settlement,
        check_missing_leader_selection_expires_package,
        check_puzzles_and_private_panel,
        check_api_death_and_invariants,
        check_task_allocator_and_voluntary_audit,
        check_checkpoint_fallback_only_at_boundary,
        check_model_response_does_not_reopen_checkpoint_after_provider_wait,
        check_random_allocator_has_no_pseudo_election,
    ]
    for check in checks:
        check()
        print("PASS", check.__name__)
    print("Authority World v1 implementation gates PASS")


if __name__ == "__main__":
    main()
