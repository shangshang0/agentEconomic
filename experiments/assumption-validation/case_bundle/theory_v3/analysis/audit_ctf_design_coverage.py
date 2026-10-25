#!/usr/bin/env python3
"""Field-level audit: recorded CTF controls vs actual Lean consumers.

This deliberately distinguishes an input being present in CTFDesign from its
being compiled into an executable event or forecast law.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DESIGN = PROJECT / "lean/AgentMicrofoundations/CaseStudies/CTFParameterizedSimulation.lean"
RESOURCE = PROJECT / "lean/AgentMicrofoundations/CaseStudies/CTFResourceSimulation.lean"
OUT_JSON = PROJECT / "lean/verification/ctf_design_coverage.json"
OUT_MD = PROJECT / "CTF_PARAMETER_COVERAGE.md"

# Each field's status is based on the current Lean implementation, not on the
# intended semantics of a future case family.
FIELD_AUDIT = {
    "population": ("POPULATION_INTERFACE", "CTFScenarioFamily.populationMatchesDesign", "Compare the design identities with the simulated population."),
    "officeSelection": ("REQUIRES_CASE_KERNEL_BINDING", "Authority World v2 has a separate exact case mapping; CTFScenarioFamily does not compile a universal office-selection law.", "Bind the selected case mechanism and seed outcomes to backend office events."),
    "allocationRule": ("REQUIRES_CASE_KERNEL_BINDING", "Passed as a design value; allocation behavior is supplied by the case family.", "Replay proposals and assignments under each allocator rule."),
    "voteRule": ("REQUIRES_CASE_KERNEL_BINDING", "Authority World v2 plurality execution has a separate exact case mapping; voter response and arbitrary vote rules are not universalized.", "Replay ballots, eligibility, tally, seeded tie-break, and office result."),
    "governanceMode": ("REQUIRES_CASE_KERNEL_BINDING", "Passed as a design value; no universal governance transition is compiled.", "Compare the active backend branch and resulting event sequence."),
    "auditMode": ("REQUIRES_CASE_KERNEL_BINDING", "Passed as a design value; audit effects must be supplied by the institution kernel.", "Replay audit-trigger and rejection events."),
    "offeredTasks": ("PARTIAL_RESOURCE_CONSUMER", "Task indices expose configured opening costs and rewards to resource events; opportunity-menu generation is external.", "Check task-menu joins and event-to-task indices."),
    "dayTicks": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering; no timed transition consumes the value.", "Check phase boundaries and tick units against runtime logs."),
    "prestartTicks": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check prestart boundary against backend timestamps."),
    "campaignOpensAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check campaign event timestamps against configured boundary."),
    "campaignClosesAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check campaign event timestamps against configured boundary."),
    "votingOpensAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check voting event timestamps against configured boundary."),
    "votingClosesAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check voting event timestamps against configured boundary."),
    "assignmentOpensAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check assignment event timestamps against configured boundary."),
    "assignmentClosesAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check assignment event timestamps against configured boundary."),
    "productionOpensAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check production event timestamps against configured boundary."),
    "productionClosesAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check production event timestamps against configured boundary."),
    "registrationOpensAt": ("CLOCK_VALIDATOR_ONLY", "Used in validCTFClock ordering only.", "Check registration event timestamps against configured boundary."),
    "idleCognitionTicks": ("REQUIRES_CASE_KERNEL_BINDING", "No idle-time state or response transition consumes this value.", "Compare idle intervals with model-call and action timestamps."),
    "maxSleepTicks": ("REQUIRES_CASE_KERNEL_BINDING", "No sleep/availability state transition consumes this value.", "Compare sleep/availability events with the runtime state."),
    "taskTimeoutTicks": ("REQUIRES_CASE_KERNEL_BINDING", "Resource replay does not enforce task timeouts.", "Replay start/deadline/timeout events and verify the backend cutoff."),
    "taskOutputLimit": ("REQUIRES_CASE_KERNEL_BINDING", "No output-size execution gate consumes this value.", "Compare submitted output sizes with backend accept/reject results."),
    "taskPrewarmTicks": ("REQUIRES_CASE_KERNEL_BINDING", "No prewarm transition consumes this value.", "Check prewarm start/end events in runtime logs."),
    "taskLifetimePeriods": ("REQUIRES_CASE_KERNEL_BINDING", "No task-expiry transition consumes this value.", "Check expiry and late-submission events against the configured lifetime."),
    "horizonPeriods": ("SCENARIO_ARGUMENT_ONLY", "The caller supplies forecast periods separately; this field does not set it automatically.", "Assert requested forecast horizon equals the design horizon."),
    "seedId": ("REQUIRES_CASE_KERNEL_BINDING", "The finite law may encode a seed, but no PRNG/seed decoder is supplied by this interface.", "Re-run the backend from the recorded seed and compare assignment/events."),
    "maxAssignments": ("REQUIRES_CASE_KERNEL_BINDING", "No general assignment-count gate consumes this value.", "Count executed assignment events and reject any over-limit trace."),
    "maxDistinctRecipients": ("REQUIRES_CASE_KERNEL_BINDING", "No general distinct-recipient gate consumes this value.", "Count unique recipients per window and compare with backend enforcement."),
    "correctWinnerLimit": ("REQUIRES_CASE_KERNEL_BINDING", "No general winner-limit gate consumes this value.", "Count verified winners and compare with backend enforcement."),
    "initialEnergy": ("OPERATIONAL_RESOURCE_REPLAY", "Initializes each tracked balance.", "Compare configured balances with reconstructed initial ledger."),
    "quotaSemantics": ("OPERATIONAL_RESOURCE_REPLAY", "Selects metered vs unmetered request handling.", "Compare quota mode with backend configuration and request counts."),
    "initialApiQuota": ("OPERATIONAL_RESOURCE_REPLAY", "Initializes requestsRemaining for each identity.", "Reconcile initial quota and all request debits."),
    "modelRequestEnergyCost": ("OPERATIONAL_RESOURCE_REPLAY", "Debited by modelRequest events.", "Replay request costs and compare balance deltas."),
    "basalEnergyDrain": ("OPERATIONAL_RESOURCE_REPLAY", "Debited by basalDrain events.", "Replay settlement events and compare daily drain."),
    "taxRate": ("REQUIRES_CASE_KERNEL_BINDING", "No tax event or tax arithmetic consumes this value.", "Reconcile taxed transfers/resource events with backend ledger."),
    "resourcePacks": ("REQUIRES_CASE_KERNEL_BINDING", "No resource-pack allocation event consumes this value.", "Join pack declarations to executed grants and recipient balances."),
    "energySemantics": ("OPERATIONAL_RESOURCE_REPLAY", "Selects whether a due zero-balance check terminates the agent.", "Compare backend branch and alive/energy path."),
    "deathCheck": ("OPERATIONAL_RESOURCE_REPLAY", "Selects event-time/period-settlement threshold checks.", "Replay check timing against backend event order."),
    "transfersEnabled": ("OPERATIONAL_RESOURCE_REPLAY", "Gates transfer feasibility.", "Compare enabled flag with executed/rejected transfer events."),
    "transferFee": ("OPERATIONAL_RESOURCE_REPLAY", "Applied to transfer send/receive deltas.", "Reconcile transfer amounts, fees, and balance changes."),
    "conditionId": ("REQUIRES_CASE_KERNEL_BINDING", "Metadata only unless a case family maps it into the complete input signature.", "Compare request signature condition labels with design condition."),
    "protocolVersion": ("REQUIRES_CASE_KERNEL_BINDING", "Metadata only unless bound to prompt/parser/tool-schema inputs.", "Hash and compare protocol artifacts used by each request."),
    "runtimeVersion": ("REQUIRES_CASE_KERNEL_BINDING", "Metadata only unless bound to the executed runtime.", "Record runtime commit/build and compare with design value."),
    "institutionSemantics": ("REQUIRES_CASE_KERNEL_BINDING", "Institutional wording is not automatically inserted into agent input.", "Compare assembled prompt disclosure with design wording condition."),
    "objectivePrompt": ("REQUIRES_CASE_KERNEL_BINDING", "Objective label is not automatically inserted into agent input.", "Hash complete prompts and check goal-text treatment."),
    "taskSuiteId": ("REQUIRES_CASE_KERNEL_BINDING", "Task-suite label is not automatically joined to the opportunity menu.", "Verify menu/task identifiers and suite version."),
}

def evidence_anchor(field: str, status: str) -> tuple[str, str]:
    if field == "population":
        return ("lean/AgentMicrofoundations/CaseStudies/CTFParameterizedSimulation.lean",
                "populationMatchesDesign")
    if status == "CLOCK_VALIDATOR_ONLY":
        return ("lean/AgentMicrofoundations/CaseStudies/CTFParameterizedSimulation.lean",
                "validCTFClock")
    resource_consumers = {
        "offeredTasks": "eventDelta",
        "initialEnergy": "initialResourceState",
        "quotaSemantics": "applyEvent",
        "initialApiQuota": "initialResourceState",
        "modelRequestEnergyCost": "eventDelta",
        "basalEnergyDrain": "eventDelta",
        "energySemantics": "applyEvent",
        "deathCheck": "checksDeathAfter",
        "transfersEnabled": "eventResourceFeasible",
        "transferFee": "eventDelta",
    }
    if field in resource_consumers:
        return ("lean/AgentMicrofoundations/CaseStudies/CTFResourceSimulation.lean",
                resource_consumers[field])
    return ("lean/AgentMicrofoundations/CaseStudies/CTFParameterizedSimulation.lean",
            "CTFScenarioFamily")


def main() -> None:
    source = DESIGN.read_text()
    block = source.split("structure CTFDesign (Agent Task : Type) where", 1)[1].split("/-- The configuration validator", 1)[0]
    fields = re.findall(r"^  ([A-Za-z][A-Za-z0-9_]*)\s*:", block, flags=re.M)
    missing = sorted(set(fields) - set(FIELD_AUDIT))
    stale = sorted(set(FIELD_AUDIT) - set(fields))
    if missing or stale:
        raise SystemExit(f"CTF design coverage map drift: missing={missing}, stale={stale}")
    rows = [
        {"field": name, "status": FIELD_AUDIT[name][0], "current_consumer": FIELD_AUDIT[name][1],
         "zero_api_case_check": FIELD_AUDIT[name][2],
         "evidence_file": evidence_anchor(name, FIELD_AUDIT[name][0])[0],
         "evidence_symbol": evidence_anchor(name, FIELD_AUDIT[name][0])[1]}
        for name in fields
    ]
    for row in rows:
        evidence = PROJECT / row["evidence_file"]
        if not evidence.is_file() or row["evidence_symbol"] not in evidence.read_text():
            raise SystemExit(f"Missing source evidence for CTFDesign.{row['field']}: {row['evidence_file']}::{row['evidence_symbol']}")
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    result = {
        "source": str(DESIGN.relative_to(PROJECT)),
        "resource_replay_source": str(RESOURCE.relative_to(PROJECT)),
        "field_count": len(fields),
        "status_counts": counts,
        "fields": rows,
        "interpretation": "A field recorded in CTFDesign is not automatically compiled into a scenario transition. Only listed operational consumers are executable in the current resource replay; other controls require an audited case-family binding before numeric forecasts may claim to vary them.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n")
    lines = [
        "# CTF design field coverage audit", "",
        "Generated by `analysis/audit_ctf_design_coverage.py` from the current Lean `CTFDesign` declaration.",
        "This is an implementation coverage audit, not a mathematical theorem or an empirical law.", "",
        f"Fields audited: **{len(fields)}**. Status counts: " + ", ".join(f"`{k}` {v}" for k,v in sorted(counts.items())) + ".", "",
        "A control can be passed to a scenario-specific joint kernel, but that alone does not show the current executable simulator consumes it. Unbound fields cannot support a claim that changing that setting changes the computed forecast.", "",
        "| Design field | Current Lean consumer | Source evidence | Zero-API case check | Status |", "|---|---|---|---|---|",
    ]
    for row in rows:
        clean = lambda x: str(x).replace("|", "\\|").replace("\n", " ")
        source_link = f"[`{row['evidence_symbol']}`]({row['evidence_file']})"
        lines.append("| " + " | ".join(clean(row[k]) for k in ("field", "current_consumer")) +
                     " | " + source_link + " | " + " | ".join(clean(row[k]) for k in ("zero_api_case_check", "status")) + " |")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"PASS: audited all {len(fields)} CTFDesign fields; {len(FIELD_AUDIT)} explicit mappings")

if __name__ == "__main__":
    main()
