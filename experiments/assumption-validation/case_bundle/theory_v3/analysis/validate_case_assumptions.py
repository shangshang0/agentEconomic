#!/usr/bin/env python3
"""Zero-API audit of empirical restrictions used by the frozen CTF case.

This script checks measurements and case-specific restrictions. It does not
turn these observations into axioms, and it does not validate a universal
behavioral law.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
RESULTS = PROJECT / "theory_v3" / "analysis" / "ctf_case" / "results"
PILOT = PROJECT / "WWW2027_submission" / "appendix" / "pilot" / "pilot_v2.jsonl"
BACKEND = PROJECT / "代码" / "authority_world" / "backend" / "world_engine_v2.py"
OUT = PROJECT / "theory_v3" / "lean" / "verification" / "assumption_validation.json"
REPORT = PROJECT / "theory_v3" / "ASSUMPTION_VALIDATION.md"
AUTHORITY_CLOCK_AUDIT = PROJECT / "theory_v3" / "analysis" / "audit_authority_v2_clock.py"
AUTHORITY_CLOCK_REPORT = PROJECT / "theory_v3" / "lean" / "verification" / "authority_v2_clock_audit.json"
AUTHORITY_ELECTION_AUDIT = PROJECT / "theory_v3" / "analysis" / "audit_authority_v2_election.py"
AUTHORITY_ELECTION_REPORT = PROJECT / "theory_v3" / "lean" / "verification" / "authority_v2_election_audit.json"
EPS = 1e-8


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    subprocess.run([sys.executable, str(AUTHORITY_CLOCK_AUDIT)], cwd=PROJECT, check=True)
    authority_clock = json.loads(AUTHORITY_CLOCK_REPORT.read_text())
    assert authority_clock["status"] == "PASS"
    subprocess.run([sys.executable, str(AUTHORITY_ELECTION_AUDIT)], cwd=PROJECT, check=True)
    authority_election = json.loads(AUTHORITY_ELECTION_REPORT.read_text())
    assert authority_election["status"] == "PASS"
    worlds_path = RESULTS / "world_summary.csv"
    panel_path = RESULTS / "agent_day_panel.csv"
    forecast_path = RESULTS / "stage1_frozen_stage2_predictions.csv"
    input_summary_path = RESULTS / "full-input-reconstruction" / "full_input_signature_summary.json"
    worlds = read_csv(worlds_path)
    panel = read_csv(panel_path)
    forecasts = read_csv(forecast_path)
    input_summary = json.loads(input_summary_path.read_text())
    backend_source = BACKEND.read_text()
    pilot_rows = [json.loads(line) for line in PILOT.read_text().splitlines() if line.strip()]

    # These are direct archive integrity checks, independent of model behavior.
    ledger_ok = [r for r in worlds if r["resource_ledger_replay_match"] == "1"]
    joins_ok = [r for r in worlds if r["task_menu_join_complete"] == "1"]
    event_outcomes_ok = [r for r in worlds if r["verified_outcomes_from_events"] == "1"]
    agent_day_keys = [(r["run_id"], r["day"], r["agent_id"]) for r in panel]
    agents_by_run_day: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in panel:
        agents_by_run_day[(r["run_id"], r["day"])].add(r["agent_id"])
    assert len(worlds) == 24, f"expected 24 archived worlds, got {len(worlds)}"
    assert len(ledger_ok) == len(worlds), "a world failed resource-ledger replay"
    assert len(joins_ok) == len(worlds), "a world has an incomplete task/menu join"
    assert len(event_outcomes_ok) == len(worlds), "a world has an outcome not derived from events"
    assert len(set(agent_day_keys)) == len(agent_day_keys), "duplicate agent-day identity row"
    assert all(len(agents) == 6 for agents in agents_by_run_day.values()), "agent identity set changes within a world-day profile"

    # A short descriptive application of the temporal persistence bounds.
    # The finite unit is the six named agents within one world, not a random
    # sample of worlds or an iid population. H=8 is fixed before reading the
    # persistence outcomes; incomplete/non-six-agent profiles are rejected.
    horizon = 8
    state_by_run_day: dict[str, dict[int, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    for row in panel:
        state_by_run_day[row["run_id"]][int(row["day"])][row["agent_id"]] = int(row["alive_end"])
    persistence_case_rows = []
    for run_id, days in state_by_run_day.items():
        if not all(day in days and len(days[day]) == 6 for day in range(1, horizon + 1)):
            continue
        agents = sorted(days[1])
        if any(set(days[day]) != set(agents) for day in range(1, horizon + 1)):
            continue
        per_agent = {
            agent: [days[day][agent] for day in range(1, horizon + 1)]
            for agent in agents
        }
        no_reentry = all(
            not (path[t] == 0 and any(path[later] == 1 for later in range(t + 1, horizon)))
            for path in per_agent.values()
            for t in range(horizon)
        )
        persistent_share = Fraction(
            sum(int(all(path)) for path in per_agent.values()), len(agents)
        )
        terminal_share = Fraction(sum(days[horizon][agent] for agent in agents), len(agents))
        period_marginals = [
            Fraction(sum(days[day][agent] for agent in agents), len(agents))
            for day in range(1, horizon + 1)
        ]
        lower = max(Fraction(0), Fraction(1) - sum((1 - p for p in period_marginals), Fraction(0)))
        upper = min(period_marginals)
        persistence_case_rows.append({
            "run_id": run_id,
            "period_marginals": period_marginals,
            "lower": lower,
            "upper": upper,
            "persistence_share": persistent_share,
            "terminal_share": terminal_share,
            "no_reentry": no_reentry,
            "inside_distribution_free_interval": lower <= persistent_share <= upper,
            "absorbing_identity_holds": persistent_share == terminal_share,
        })
    assert len(persistence_case_rows) == len(worlds), (
        f"expected complete six-agent H={horizon} profiles for all worlds; "
        f"found {len(persistence_case_rows)}/{len(worlds)}"
    )
    assert all(r["no_reentry"] for r in persistence_case_rows), "an agent re-entered after exiting"
    assert all(r["inside_distribution_free_interval"] for r in persistence_case_rows)
    assert all(r["absorbing_identity_holds"] for r in persistence_case_rows)

    # Complete agent-visible gateway inputs are archived and hash-indexed.
    # Uniqueness means historical exact-input repeats cannot estimate a response
    # distribution; it is not a reason to treat input reconstruction as blocked.
    assert input_summary["worlds"] == len(worlds)
    assert input_summary["gateway_exchanges"] == 45180
    assert input_summary["full_request_signatures"] == input_summary["gateway_exchanges"]
    assert input_summary["full_request_signatures_reused_across_worlds"] == 0

    # Audit the actual backend gate that gives the survival-currency subcase
    # its meaning. Keep this scoped to the exact backend source being hashed.
    symbolic_bypass = 'if _config(state).energy_consequence == "symbolic":\n        return'
    operational_death_gate = 'if state["agents"][agent_id]["energy"] <= 0:\n            _kill(state, agent_id, "energy_depleted", now)'
    assert symbolic_bypass in backend_source, "symbolic energy no longer bypasses mortality check"
    assert operational_death_gate in backend_source, "operational energy mortality gate changed"

    # A currency-survival coupling is a regime rule, not a universal ontology.
    alive_negative = defaultdict(lambda: {"alive_start": 0, "alive_end": 0,
                                         "rows": 0, "alive_start_rows": 0})
    for r in panel:
        x = alive_negative[r["regime"]]
        x["rows"] += 1
        if r["alive_start"] == "1":
            x["alive_start_rows"] += 1
            x["alive_start"] += int(float(r["energy_start_replayed"]) < -EPS)
        if r["alive_end"] == "1":
            x["alive_end"] += int(float(r["energy_end_replayed"]) < -EPS)
    operational = [r for r in panel if r["regime"] != "symbolic-energy"]
    operational_negative_alive_start = sum(
        int(r["alive_start"] == "1" and float(r["energy_start_replayed"]) < -EPS)
        for r in operational)
    operational_negative_alive_end = sum(
        int(r["alive_end"] == "1" and float(r["energy_end_replayed"]) < -EPS)
        for r in operational)
    non_symbolic_negative_balance_observations = sum(
        int(float(r[field]) < -EPS)
        for r in operational
        for field in ("energy_start_replayed", "energy_end_replayed"))
    symbolic_negative_alive_start = alive_negative["symbolic-energy"]["alive_start"]
    symbolic_negative_alive_end = alive_negative["symbolic-energy"]["alive_end"]
    assert operational_negative_alive_start == 0
    assert operational_negative_alive_end == 0
    assert non_symbolic_negative_balance_observations == 0
    assert symbolic_negative_alive_start > 0
    assert symbolic_negative_alive_end > 0

    # The previously used tier-frequency forecast is scored only as a
    # retrospective diagnostic; these worlds were not prospectively blinded.
    forecast_cells = []
    for r in forecasts:
        slots = int(r["offered_slots"])
        rate_error = abs(float(r["assignment_error_observed_minus_predicted"])) / slots
        forecast_cells.append({
            "family": r["family"], "regime": r["regime"],
            "offered_slots": slots,
            "absolute_assignment_rate_error": rate_error,
            "exceeds_retrospective_5pp_screen": rate_error > 0.05,
        })
    assert len(forecast_cells) == 4

    # The pilot is an optional, simple local test of a response restriction;
    # no stable/general response law is inferred from it.
    assert len(pilot_rows) == 40, f"expected 40 valid pilot calls, got {len(pilot_rows)}"
    assert all(r.get("ok") is True and r.get("valid_action") is True for r in pilot_rows)
    per_signal = Counter(int(r["displayed_energy"]) for r in pilot_rows)
    assert per_signal == Counter({2: 20, 5: 20})
    work_by_signal = Counter(int(r["displayed_energy"]) for r in pilot_rows if r["action"] == "work")
    work_proposals = [r for r in pilot_rows if r["action"] == "work"]
    replay_counts = Counter()
    for r in work_proposals:
        replay = r["counterfactual_gate_replay"]
        replay_counts[2] += int(replay["actual_energy_2"]["accepted"])
        replay_counts[5] += int(replay["actual_energy_5"]["accepted"])
        assert replay["actual_energy_2"]["accepted"] is False
        assert replay["actual_energy_5"]["accepted"] is True
    assert len(work_proposals) == 35
    assert replay_counts == Counter({5: 35, 2: 0})

    # An explicit admissibility registry prevents a formally convenient
    # condition from silently becoming an empirical premise. Every empirical
    # restriction used in a case forecast must have an executable low-cost
    # check, a reject rule, and an explicit failure action. Restrictions that
    # cannot currently be checked are retained as excluded/open obligations,
    # never treated as satisfied.
    assumption_registry = [
        {
            "id": "MATH-FINITE-LAW",
            "kind": "mathematical_interface_invariant",
            "verification_cost": "FORMAL_ONLY",
            "restriction": "A finite probability law has nonnegative rational weights summing to one.",
            "check": "Lean FiniteDistribution constructor and kernel build; no empirical fitting assumption.",
            "reject_rule": "A law that is not normalized/nonnegative cannot be instantiated as FiniteDistribution.",
            "failure_action": "Reject the mathematical input; do not run numerical forecast.",
            "status": "ENFORCED_BY_LEAN_TYPE",
            "evidence": "Ontology.lean: FiniteDistribution",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-LEDGER-CLOSURE",
            "kind": "case_mapping_restriction",
            "verification_cost": "ZERO_API_ARCHIVE_REPLAY",
            "restriction": "Recorded resource changes equal event-level replay for every archived world.",
            "check": "Zero-API replay and world-level ledger comparison.",
            "reject_rule": "Any world has resource_ledger_replay_match != 1.",
            "failure_action": "Reject the resource-to-agent case mapping before interpreting predictions.",
            "status": "PASS",
            "evidence": f"{len(ledger_ok)}/{len(worlds)} worlds; source data SHA-256 recorded",
            "used_for_case_prediction": True,
        },
        {
            "id": "CASE-FULL-INPUT",
            "kind": "case_measurement_restriction",
            "verification_cost": "ZERO_API_ARCHIVE_AUDIT",
            "restriction": "Each archived gateway request can be reconstructed with its full agent-visible payload.",
            "check": "Count complete request signatures and compare with gateway exchanges.",
            "reject_rule": "Any request lacks payload, or signature count differs from exchange count.",
            "failure_action": "Refuse same-input response claims for unreconstructable requests.",
            "status": "PASS",
            "evidence": f"{input_summary['full_request_signatures']}/{input_summary['gateway_exchanges']} complete; exact signatures reused across worlds={input_summary['full_request_signatures_reused_across_worlds']}",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-OPERATIONAL-DEATH-GATE",
            "kind": "case-execution-rule",
            "verification_cost": "ZERO_API_SOURCE_AND_TRACE_AUDIT",
            "restriction": "The CTF backend terminates an alive agent at energy <= 0 in non-symbolic regimes and bypasses this gate in symbolic-energy.",
            "check": "Static backend source guard plus alive/energy trace cross-check.",
            "reject_rule": "Backend branch changes or any non-symbolic alive observation contradicts the replayed gate.",
            "failure_action": "Withdraw the energy-survival case mapping; do not use survival-currency results.",
            "status": "PASS",
            "evidence": f"source guards pass; operational negative-alive observations={operational_negative_alive_start + operational_negative_alive_end}; symbolic negative-alive observations={symbolic_negative_alive_start + symbolic_negative_alive_end}",
            "used_for_case_prediction": True,
        },
        {
            "id": "CASE-NONNEGATIVE-BALANCE",
            "kind": "case-domain-restriction",
            "verification_cost": "ZERO_API_TRACE_SCAN",
            "restriction": "Every balance in the stochastic resource upper-bound application is nonnegative.",
            "check": "Direct scan of all archived non-symbolic agent-day start/end balances.",
            "reject_rule": "Any scanned balance is negative.",
            "failure_action": "Do not instantiate ResourceSurvivalBound for that regime; use a signed-resource model instead.",
            "status": "PASS_FOR_NON_SYMBOLIC_TRACE",
            "evidence": f"negative observations={non_symbolic_negative_balance_observations}; symbolic negative-alive start/end={symbolic_negative_alive_start}/{symbolic_negative_alive_end}",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-POSITIVE-CONTINUATION-RESERVE",
            "kind": "case-domain-restriction",
            "verification_cost": "ZERO_API_SOURCE_AND_EVENT_SCAN",
            "restriction": "A positive common reserve d is enforced before the continuation event being predicted.",
            "check": "Read the backend death threshold and scheduled mandatory costs from the actual event sequence.",
            "reject_rule": "No positive enforced reserve exists, or the checking point does not match the modeled next-period event.",
            "failure_action": "Do not report the positive-reserve probability bound as a CTF survival prediction.",
            "status": "NOT_SATISFIED_ZERO_DEATH_THRESHOLD",
            "evidence": "Backend death gate is energy <= 0; direct reserve d=0 makes the positive-reserve bound uninformative.",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-RESPONSE-KERNEL",
            "kind": "behavioral-restriction",
            "verification_cost": "SMALL_PAIRED_API_DIAGNOSTIC_REQUIRED_NOT_YET_RUN",
            "restriction": "A frozen response kernel maps complete inputs and states to proposal probabilities.",
            "check": "Exact-input repeats, or a preregistered low-cost paired replay experiment with fixed inputs and controlled conditions.",
            "reject_rule": "Held-out proposal frequencies fall outside the predeclared predictive interval, or the supposedly fixed input/configuration changes.",
            "failure_action": "Reject that response restriction; do not add post-hoc state variables to rescue it.",
            "status": "NOT_IDENTIFIED_EXACT_INPUTS_UNIQUE",
            "evidence": f"{input_summary['gateway_exchanges']} complete archived requests; {input_summary['full_request_signatures_reused_across_worlds']} exact signatures reused across worlds; existing pilot is vignette-local only.",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-ALLOCATION-PRODUCTION-JOINT-LAW",
            "kind": "behavioral-production-restriction",
            "verification_cost": "ZERO_API_EVENT_JOIN_AND_WORLD_HOLDOUT",
            "restriction": "A frozen joint law predicts assignment and verified production, preserving arbitrary dependence.",
            "check": "Use agent-task event joins; fit on calibration worlds and score world-level holdouts with a frozen rule.",
            "reject_rule": "Any predeclared holdout statistic exceeds the frozen tolerance; current tier-frequency screen already fails 4/4 retrospective cells.",
            "failure_action": "Reject that candidate law; retain only identified bounds or collect a new minimal calibration sample.",
            "status": "NO_ACCEPTED_FROZEN_LAW",
            "evidence": f"retrospective tier-frequency baseline rejected in {sum(c['exceeds_retrospective_5pp_screen'] for c in forecast_cells)}/{len(forecast_cells)} cells; this is diagnostic, not a prospective test.",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-ANONYMITY-INDEPENDENCE",
            "kind": "behavioral-restriction",
            "verification_cost": "CONTROLLED_API_POPULATION_TEST_REQUIRED_NOT_ADMITTED",
            "restriction": "Exchangeability/anonymity or cross-agent independence.",
            "check": "Would require identity permutation or joint-response tests over repeated controlled populations.",
            "reject_rule": "Any label-permutation or dependence diagnostic violates the preregistered tolerance.",
            "failure_action": "Never impose this restriction for CTF forecasts without the test; current general interfaces allow asymmetry and dependence.",
            "status": "EXCLUDED_NOT_REQUIRED",
            "evidence": "Lean population interfaces and joint lotteries permit arbitrary identities and dependence.",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-PERSISTENCE-DECOMPOSITION",
            "kind": "case-event-restriction",
            "verification_cost": "ZERO_API_AGENT_PATH_SCAN",
            "restriction": "For a fixed horizon, persistence is the conjunction of period-level alive events; with absorbing exits, it equals terminal alive status.",
            "check": f"For each world and each of its six identities, compare all alive_end flags on days 1..{horizon} to day-{horizon} alive_end and scan for exit followed by re-entry.",
            "reject_rule": "Any path in the positive-support case sample disagrees, or backend uses an unrecorded reset/revival event.",
            "failure_action": "Do not use temporal intersection bounds for survival; retain only the full path simulator or redefine the event from audited state transitions.",
            "status": f"PASS_DESCRIPTIVE_{sum(r['absorbing_identity_holds'] for r in persistence_case_rows)}/{len(persistence_case_rows)}_WORLD_PATHS",
            "evidence": f"H={horizon}; six named agents per world; no-reentry={sum(r['no_reentry'] for r in persistence_case_rows)}/{len(persistence_case_rows)}; persistence equals terminal alive share={sum(r['absorbing_identity_holds'] for r in persistence_case_rows)}/{len(persistence_case_rows)}; interval contains persistence={sum(r['inside_distribution_free_interval'] for r in persistence_case_rows)}/{len(persistence_case_rows)}. Descriptive finite-population shares only, not a cross-world forecast.",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-AUTHORITY-V2-CLOCK-MAPPING",
            "kind": "case-execution-rule",
            "verification_cost": "ZERO_API_BACKEND_CONFIG_BOUNDARY_AUDIT",
            "restriction": "Lean AuthorityWorldV2Clock reproduces the v2 backend's day phase, allocation/work half-open windows, election registration gate, and inclusive task-lifetime boundary.",
            "check": "Execute the actual Python config parser and runtime gate functions at open/close boundaries for every checked-in agent_econ_*.json; guard the corresponding backend source rules.",
            "reject_rule": "Any source guard changes, any config violates the encoded ordering, or any runtime gate differs from the Lean boundary fixture.",
            "failure_action": "Withdraw the v2 clock-to-opportunity mapping; do not use the Lean timing module for that backend until the semantics are reconciled.",
            "status": "PASS",
            "evidence": f"{authority_clock['configs_checked']} configs; zero API; source and config hashes recorded in authority_v2_clock_audit.json",
            "used_for_case_prediction": False,
        },
        {
            "id": "CASE-AUTHORITY-V2-ELECTION-MAPPING",
            "kind": "case-execution-rule",
            "verification_cost": "ZERO_API_BACKEND_BRANCH_AUDIT",
            "restriction": "Given the recorded alive set, candidate set, explicit ballots, and seed-conditioned choices, the Lean election map reproduces no-candidate, all-candidate, missing-ballot, plurality, and tie branches.",
            "check": "Run the actual Python _finalize_election on boundary profiles and guard its branch semantics against the Lean case model; retain source/config hashes.",
            "reject_rule": "Any backend branch, seed tag, vote-imputation rule, or tested outcome differs from the encoded case map.",
            "failure_action": "Withdraw this v2 election mapping and do not use it to simulate office selection until reconciled.",
            "status": "PASS",
            "evidence": "Zero-API synthetic branch audit; no-candidate and all-candidate paths plus a Lean-matched four-agent 1:1 plurality tie with one imputed ballot.",
            "used_for_case_prediction": False,
        },
    ]

    required_registry_fields = {
        "id", "kind", "verification_cost", "restriction", "check", "reject_rule",
        "failure_action", "status", "evidence", "used_for_case_prediction",
    }
    assert all(required_registry_fields <= entry.keys() for entry in assumption_registry)
    assert len({entry["id"] for entry in assumption_registry}) == len(assumption_registry)
    for entry in assumption_registry:
        if entry["kind"] not in {"mathematical_interface_invariant"}:
            assert entry["check"].strip(), f"{entry['id']} has no verification method"
            assert entry["reject_rule"].strip(), f"{entry['id']} has no reject rule"
            assert entry["failure_action"].strip(), f"{entry['id']} has no failure action"
        if entry["used_for_case_prediction"]:
            assert entry["status"] in {"PASS", "PASS_FOR_NON_SYMBOLIC_TRACE"}, (
                f"unverified restriction {entry['id']} is used by a case prediction"
            )

    result = {
        "audit_type": "zero_api_case_assumption_validation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "principle": "definitions are not empirical assumptions; every case restriction is either directly audited, locally tested, or left unasserted",
        "source_sha256": {
            str(p.relative_to(PROJECT)): sha256(p)
            for p in (worlds_path, panel_path, forecast_path, input_summary_path, PILOT, BACKEND,
                      AUTHORITY_CLOCK_AUDIT, AUTHORITY_CLOCK_REPORT,
                      AUTHORITY_ELECTION_AUDIT, AUTHORITY_ELECTION_REPORT)
        },
        "archive_integrity": {
            "worlds": len(worlds), "agent_day_rows": len(panel),
            "unique_world_day_profiles": len(agents_by_run_day),
            "six_distinct_agent_identities_per_profile": all(len(agents) == 6 for agents in agents_by_run_day.values()),
            "ledger_replay_pass": f"{len(ledger_ok)}/{len(worlds)}",
            "complete_task_menu_join": f"{len(joins_ok)}/{len(worlds)}",
            "verified_outcomes_from_events": f"{len(event_outcomes_ok)}/{len(worlds)}",
            "status": "PASS",
        },
        "input_reconstruction": {
            "gateway_exchanges_with_complete_input_payload": input_summary["gateway_exchanges"],
            "unique_full_request_signatures": input_summary["full_request_signatures"],
            "reused_signatures_across_worlds": input_summary["full_request_signatures_reused_across_worlds"],
            "interpretation": "input reconstruction is complete for archived gateway exchanges; exact-input response variation is not estimable because signatures are unique",
            "status": "INPUT_AUDITED_RESPONSE_REPEAT_UNIDENTIFIED",
        },
        "backend_threshold_rule": {
            "source": str(BACKEND.relative_to(PROJECT)),
            "source_lines": "215-220 (manually inspected source; substring guard prevents silent drift)",
            "operational_rule": "alive agent with energy <= 0 is terminated at _deaths check",
            "symbolic_rule": "_deaths returns without applying the energy mortality gate",
            "status": "SOURCE_RULE_AUDITED",
        },
        "resource_survival_case_restriction": {
            "non_symbolic_regimes": sorted({r["regime"] for r in operational}),
            "operational_alive_with_negative_start_balance": operational_negative_alive_start,
            "operational_alive_with_negative_end_balance": operational_negative_alive_end,
            "non_symbolic_negative_balance_observations": non_symbolic_negative_balance_observations,
            "verified_balance_domain_for_positive_reserve_bound": non_symbolic_negative_balance_observations == 0,
            "symbolic_energy_alive_with_negative_start_balance": symbolic_negative_alive_start,
            "symbolic_energy_alive_with_negative_end_balance": symbolic_negative_alive_end,
            "interpretation": "panel and backend source jointly validate this case-specific execution rule; symbolic-energy directly falsifies universal coupling",
            "status": "CASE_SCOPED_ONLY",
        },
        "tier_frequency_assignment_law": {
            "evaluation": "retrospective diagnostic; not a prospectively registered confirmation",
            "screen": "reject a cell if absolute assignment-rate error exceeds 5 percentage points",
            "cells": forecast_cells,
            "rejected_cells": sum(c["exceeds_retrospective_5pp_screen"] for c in forecast_cells),
            "total_cells": len(forecast_cells),
            "status": "REJECTED_AS_CASE_POINT_FORECAST",
        },
        "pilot_response_restriction": {
            "valid_calls": len(pilot_rows),
            "calls_per_displayed_energy": dict(sorted(per_signal.items())),
            "work_proposals_by_displayed_energy": dict(sorted(work_by_signal.items())),
            "identical_work_proposals_accepted_by_execution_replay": {
                "true_energy_2": replay_counts[2], "true_energy_5": replay_counts[5],
                "work_proposals": len(work_proposals),
            },
            "interpretation": "local pilot evidence only; does not license a general monotone response axiom",
            "status": "LOCAL_DIAGNOSTIC_ONLY",
        },
        "unvalidated_behavioral_restrictions": [
            "rational choice or stable preferences",
            "agent independence, exchangeability, or anonymity",
            "a universal mapping from resource balance to survival or action",
            "a response law transported across population sizes, prompts, or mechanisms",
        ],
        "assumption_registry": assumption_registry,
        "prediction_admissibility": {
            "all_empirical_restrictions_have_low_cost_check_and_reject_rule": True,
            "untested_or_rejected_restrictions_used_in_case_forecast": 0,
            "positive_reserve_survival_forecast_admissible_for_current_ctf": False,
            "point_forecast_from_behavioral_kernel_admissible": False,
            "reason": "positive enforced reserve and accepted frozen joint response-production kernel are both absent; report execution facts, case diagnostics, or identified bounds only",
        },
        "temporal_persistence_case": {
            "horizon_days": horizon,
            "unit": "six explicitly named agents within each world; empirical finite-population share, not iid or superpopulation probability",
            "worlds": len(persistence_case_rows),
            "no_reentry_worlds": sum(r["no_reentry"] for r in persistence_case_rows),
            "absorbing_identity_worlds": sum(r["absorbing_identity_holds"] for r in persistence_case_rows),
            "general_intersection_interval_contains_observed_persistence": sum(r["inside_distribution_free_interval"] for r in persistence_case_rows),
            "interval_exact_worlds": sum(r["lower"] == r["upper"] for r in persistence_case_rows),
            "max_interval_width": str(max(r["upper"] - r["lower"] for r in persistence_case_rows)),
            "cases": [
                {k: (str(v) if isinstance(v, Fraction) else
                     [str(x) for x in v] if isinstance(v, list) else v)
                 for k, v in row.items()}
                for row in persistence_case_rows
            ],
            "interpretation": "For these archived traces, no re-entry makes persistence through day 8 exactly equal terminal alive share; observed shares lie in the distribution-free intersection interval. This is a descriptive case audit, not an ex ante forecast or a population-level inference.",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    report_lines = [
        "# Case Assumption Verification Register",
        "",
        "Generated by `analysis/validate_case_assumptions.py`; source of truth is the machine-readable JSON beside the Lean verification manifest.",
        "",
        "No empirical restriction may enter a case forecast unless it has a low-cost check, a reject rule, and a stated failure action. Untested restrictions remain excluded.",
        "",
        "| ID | Status | Verification cost | Restriction | Check | If rejected | Used in forecast? |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in assumption_registry:
        safe = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        report_lines.append(
            "| " + " | ".join(safe(entry[key]) for key in (
                "id", "status", "verification_cost", "restriction", "check", "failure_action", "used_for_case_prediction"
            )) + " |"
        )
    report_lines.extend([
        "",
        "## Eligibility decision",
        "",
        "Current CTF does **not** instantiate the positive-reserve stochastic survival bound: the operative death threshold is zero. It does instantiate a descriptive finite-population persistence audit for the first 8 days: the no-re-entry condition passes in every archived world, so persistence equals the day-8 alive share. This does not predict new worlds. Current CTF also has no accepted frozen behavioral joint law for point forecasts. These are explicit exclusions, not blockers to the general Lean theory.",
        "",
        f"For the persistence audit, {len(persistence_case_rows)}/{len(worlds)} worlds had complete six-agent profiles through day {horizon}; no re-entry and terminal/persistent-share equality both passed in {sum(r['absorbing_identity_holds'] for r in persistence_case_rows)}/{len(persistence_case_rows)} worlds. The distribution-free interval contains the observed share in {sum(r['inside_distribution_free_interval'] for r in persistence_case_rows)}/{len(persistence_case_rows)} worlds; it collapses to a point in {sum(r['lower'] == r['upper'] for r in persistence_case_rows)}/{len(persistence_case_rows)} and has maximum width {max(r['upper'] - r['lower'] for r in persistence_case_rows)}. These are finite-population descriptions, not run-level inferential probabilities.",
        "",
        "The resource bound itself is a formal conditional result. Its mathematical premises are checked by Lean; empirical mapping premises are checked above. A failed premise rejects that case application and leaves the reusable theorem intact.",
    ])
    REPORT.write_text("\n".join(report_lines) + "\n")
    print(f"PASS: zero-API assumption audit written to {OUT} and {REPORT}")


if __name__ == "__main__":
    main()
