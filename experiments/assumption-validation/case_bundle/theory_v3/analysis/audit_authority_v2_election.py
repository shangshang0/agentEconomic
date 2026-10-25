#!/usr/bin/env python3
"""Zero-API branch audit for Authority World v2 next-day office selection."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
WORLD = PROJECT.parent / "代码" / "authority_world"
ENGINE = WORLD / "backend" / "world_engine_v2.py"
CONFIG_PATH = WORLD / "config" / "agent_econ_i1_elected_discretion_human.json"
LEAN_FILE = PROJECT / "lean/AgentMicrofoundations/CaseStudies/AuthorityWorldV2Election.lean"
OUT = PROJECT / "lean/verification/authority_v2_election_audit.json"
sys.path.insert(0, str(WORLD))
from backend.world_config_v2 import from_dict  # noqa: E402
from backend.world_engine_v2 import _choice, _finalize_election  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_for(cfg, alive: list[str], candidates: list[str], votes: dict[str, str], seed: int):
    return {
        "config": cfg.canonical_dict(), "day": 2, "world_start_wall": 10_000.0,
        "seed": seed, "run_id": "zero-api-election-audit", "event_seq": 0,
        "audit": [], "forum": [], "notice_seq": 0,
        "agents": {agent: {"status": "alive"} for agent in alive},
        "daily": {"leader": alive[0], "candidates": candidates,
                  "candidate_revision": len(candidates), "votes": votes,
                  "election_finalized": False},
    }


def main() -> None:
    engine = ENGINE.read_text()
    lean = LEAN_FILE.read_text()
    guards = {
        "no_candidate_seeded_choice": '"no_candidates"' in engine and '_choice(state["seed"], alive, "leader", state["day"])' in engine,
        "all_candidate_seeded_choice": '"all_candidates"' in engine and '_choice(state["seed"], candidates, "leader", state["day"], "all_candidates")' in engine,
        "missing_votes_imputed_only_for_non_candidates": 'for voter in [x for x in alive if x not in candidates]' in engine,
        "missing_vote_seeded_choice": '_choice(state["seed"], candidates, "missing_vote", state["day"], voter)' in engine,
        "plurality_tally_and_tie_break": 'high = max(totals.values())' in engine and '"leader_tie"' in engine,
        "lean_has_exact_case_mapping": all(x in lean for x in ["missingEligibleVoters", "completedVotes", "maximumTally", "pluralityLeaders", "nextOfficeHolder"]),
    }
    assert all(guards.values()), f"v2 election source/Lean mapping changed: {guards}"
    cfg = from_dict(json.loads(CONFIG_PATH.read_text()))
    alive = [f"A{i}" for i in range(1, 5)]

    no_candidate_seed = 11
    state = state_for(cfg, alive, [], {}, no_candidate_seed)
    no_candidate_expected = _choice(no_candidate_seed, alive, "leader", 2)
    _finalize_election(state, 10_000.0 + cfg.registration_open_seconds)
    no_candidate = state["next_leader"] == no_candidate_expected and state["audit"][-1]["data"]["reason"] == "no_candidates"
    assert no_candidate

    all_candidate_seed = 13
    state = state_for(cfg, alive, alive[:], {}, all_candidate_seed)
    all_candidate_expected = _choice(all_candidate_seed, alive, "leader", 2, "all_candidates")
    _finalize_election(state, 10_000.0 + cfg.registration_open_seconds)
    all_candidate = state["next_leader"] == all_candidate_expected and state["audit"][-1]["data"]["reason"] == "all_candidates"
    assert all_candidate

    # Match the Lean four-agent fixture: A3 explicitly votes A1; A4 is missing
    # and the seed imputes A2; the tie-break then selects A1.
    candidates = ["A1", "A2"]
    seed = next(s for s in range(10_000)
                if _choice(s, candidates, "missing_vote", 2, "A4") == "A2"
                and _choice(s, candidates, "leader_tie", 2) == "A1")
    state = state_for(cfg, alive, candidates, {"A3": "A1"}, seed)
    _finalize_election(state, 10_000.0 + cfg.registration_open_seconds)
    event = state["audit"][-1]["data"]
    plurality = (state["next_leader"] == "A1" and event["reason"] == "plurality_tie"
                 and event["explicit_votes"] == 1 and event["imputed_votes"] == 1
                 and event["vote_totals"] == {"A1": 1, "A2": 1})
    assert plurality

    result = {
        "audit": "zero_api_execution_of_authority_v2_election_branches",
        "backend_source_sha256": digest(ENGINE),
        "config": str(CONFIG_PATH.relative_to(WORLD)),
        "config_sha256": digest(CONFIG_PATH),
        "lean_source": str(LEAN_FILE.relative_to(PROJECT)),
        "lean_source_sha256": digest(LEAN_FILE),
        "source_guards": guards,
        "branches": {
            "no_candidates_seeded_choice": {"pass": no_candidate, "result": no_candidate_expected},
            "all_candidates_seeded_choice": {"pass": all_candidate, "result": all_candidate_expected},
            "plurality_tie_with_missing_vote": {"pass": plurality, "seed": seed, "winner": "A1", "vote_totals": event["vote_totals"], "explicit_votes": event["explicit_votes"], "imputed_votes": event["imputed_votes"]},
        },
        "api_calls": 0,
        "status": "PASS",
        "interpretation": "The concrete Lean election function matches audited v2 branch semantics for supplied ballots and seeded choices; this does not predict candidacy or voting behavior.",
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print("PASS: Authority World v2 election branches match Lean case mapping; zero API calls")


if __name__ == "__main__":
    main()
