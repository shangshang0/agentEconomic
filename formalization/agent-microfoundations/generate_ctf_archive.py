#!/usr/bin/env python3
"""Generate a Lean-checked finite audit of the trace-derived CTF case."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "analysis" / "ctf_case" / "results"
TASKS = DATA / "task_panel.csv"
WORLDS = DATA / "world_summary.csv"
TARGET = ROOT / "AgentMicrofoundations" / "CaseStudies" / "CTFArchive.lean"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path):
    with path.open() as f:
        return list(csv.DictReader(f))


def main() -> None:
    if not TASKS.exists() or not WORLDS.exists():
        raise SystemExit("Run analysis/ctf_case/build_ctf_case.py first")
    task_rows = read_rows(TASKS)
    world_rows = read_rows(WORLDS)
    if len(world_rows) != 24 or len(task_rows) != 1728:
        raise SystemExit(f"unexpected archive dimensions: {len(world_rows)} worlds, {len(task_rows)} task rows")

    labels = {
        "family": {"GPT": "gpt", "DeepSeek": "deepSeek"},
        "regime": {"I1": "i1", "I3": "i3"},
        "tier": {"easy": "easy", "medium": "medium", "hard": "hard"},
    }
    grouped = defaultdict(lambda: {"offered": 0, "assigned": 0, "success": 0, "failure": 0,
                                   "unattempted": 0, "proposed_slots": 0,
                                   "proposal_calls": 0, "tool_ok_calls": 0})
    for row in task_rows:
        if row["stage"] not in ("stage1", "stage2") or row["offered"] != "1":
            continue
        if row["regime"] not in labels["regime"] or row["family"] not in labels["family"]:
            continue
        tier = row["tier"]
        if tier not in labels["tier"]:
            raise SystemExit(f"unexpected task tier {tier}")
        key = (row["stage"], row["family"], row["regime"], tier)
        cell = grouped[key]
        cell["offered"] += 1
        proposal_records = json.loads(row["allocation_proposals"])
        cell["proposed_slots"] += int(int(row["allocator_proposal_count"]) > 0)
        cell["proposal_calls"] += int(row["allocator_proposal_count"])
        cell["tool_ok_calls"] += int(row["allocator_proposal_tool_ok_count"])
        assigned = row["assigned"] == "1"
        successes = int(row["verified_successes"])
        failures = int(row["verified_failures"])
        attempts = int(row["verified_attempts"])
        if assigned:
            cell["assigned"] += 1
            if successes > 0:
                cell["success"] += 1
            elif failures > 0:
                cell["failure"] += 1
            elif attempts == 0:
                cell["unattempted"] += 1
            else:
                raise SystemExit(f"unclassified assigned task outcome: {row['run_id']} {row['task_id']}")
        elif attempts > 0:
            raise SystemExit(f"submission without an execution assignment: {row['run_id']} {row['task_id']}")

        if row["stage"] in ("stage1", "stage2") and row["regime"] == "I1":
            actual_recipients = set(json.loads(row["recipient_ids"]))
            tool_ok_recipients = {p.get("recipient") for p in proposal_records if p.get("tool_call_ok") is True}
            if actual_recipients != tool_ok_recipients:
                raise SystemExit(f"I1 proposal/execution recipient mismatch: {row['run_id']} {row['task_id']}")
        elif row["stage"] in ("stage1", "stage2") and row["regime"] == "I3" and proposal_records:
            raise SystemExit(f"I3 backend-random task has an agent assignment proposal: {row['run_id']} {row['task_id']}")

    expected_keys = {
        (stage, family, regime, tier)
        for stage in ("stage1", "stage2")
        for family in labels["family"]
        for regime in labels["regime"]
        for tier in labels["tier"]
    }
    if set(grouped) != expected_keys:
        raise SystemExit(f"missing calibration/holdout cell(s): {expected_keys - set(grouped)}")
    if any(w["resource_ledger_replay_match"] != "1" for w in world_rows):
        raise SystemExit("at least one world fails the event-ledger to terminal-state replay")

    def make_cells(stage: str) -> str:
        entries = []
        for family in ("GPT", "DeepSeek"):
            for regime in ("I1", "I3"):
                for tier in ("easy", "medium", "hard"):
                    c = grouped[(stage, family, regime, tier)]
                    if c["assigned"] != c["success"] + c["failure"] + c["unattempted"]:
                        raise SystemExit(f"assigned task outcomes do not partition in {stage}/{family}/{regime}/{tier}")
                    entries.append(
                        f"  {{ family := .{labels['family'][family]}, regime := .{labels['regime'][regime]}, "
                        f"tier := .{labels['tier'][tier]}, offered := {c['offered']}, assigned := {c['assigned']}, "
                        f"proposedSlots := {c['proposed_slots']}, proposalCalls := {c['proposal_calls']}, "
                        f"toolOkCalls := {c['tool_ok_calls']}, success := {c['success']}, failureOnly := {c['failure']}, "
                        f"unattempted := {c['unattempted']} }}"
                    )
        return ",\n".join(entries)

    stage1_worlds = sum(w["stage"] == "stage1" for w in world_rows)
    stage2_worlds = sum(w["stage"] == "stage2" for w in world_rows)
    mechanism_worlds = sum(w["stage"] == "mechanism" for w in world_rows)
    trace_joined = sum(int(w["trace_agents"]) == int(w["agents"]) for w in world_rows)
    offered_totals = {}
    assigned_totals = {}
    success_totals = {}
    for stage in ("stage1", "stage2"):
        offered_totals[stage] = sum(v["offered"] for k, v in grouped.items() if k[0] == stage)
        assigned_totals[stage] = sum(v["assigned"] for k, v in grouped.items() if k[0] == stage)
        success_totals[stage] = sum(v["success"] for k, v in grouped.items() if k[0] == stage)
    heldout_world_rows = [w for w in world_rows if w["stage"] == "stage2"]
    holdout_counts = {}
    for family in ("GPT", "DeepSeek"):
        for regime in ("I1", "I3"):
            runs = [w["run_id"] for w in heldout_world_rows
                    if w["family"] == family and w["regime"] == regime]
            if len(runs) != 1:
                raise SystemExit(f"expected one stage2 world for {family}/{regime}, found {len(runs)}")
            selected = [r for r in task_rows if r["run_id"] == runs[0] and r["offered"] == "1"]
            offered_by_tier = {
                tier: sum(1 for row in selected if row["tier"] == tier)
                for tier in ("easy", "medium", "hard")
            }
            fit = {tier: grouped[("stage1", family, regime, tier)]
                   for tier in ("easy", "medium", "hard")}
            denominators = {cell["offered"] for cell in fit.values()}
            if len(denominators) != 1:
                raise SystemExit(f"unbalanced calibration exposure for {family}/{regime}")
            holdout_counts[(family, regime)] = {
                "offered": len(selected),
                "assigned": sum(int(r["assigned"]) for r in selected),
                "success": sum(int(int(r["verified_successes"]) > 0) for r in selected),
                "prediction_denominator": next(iter(denominators)),
                "predicted_assignment_numerator": sum(
                    offered_by_tier[tier] * fit[tier]["assigned"] for tier in fit),
                "predicted_success_numerator": sum(
                    offered_by_tier[tier] * fit[tier]["success"] for tier in fit),
            }
    def holdout_record_rows() -> str:
        entries = []
        for family in ("GPT", "DeepSeek"):
            for regime in ("I1", "I3"):
                c = holdout_counts[(family, regime)]
                entries.append(
                    f"  {{ family := .{labels['family'][family]}, regime := .{labels['regime'][regime]}, "
                    f"offered := {c['offered']}, assigned := {c['assigned']}, success := {c['success']}, "
                    f"predictedAssignmentsNum := {c['predicted_assignment_numerator']}, "
                    f"predictedSuccessesNum := {c['predicted_success_numerator']}, "
                    f"predictionDenom := {c['prediction_denominator']} }}"
                )
        return ",\n".join(entries)
    source_hash = sha(TASKS)
    world_hash = sha(WORLDS)
    TARGET.write_text(f'''import AgentMicrofoundations.CaseAnalysis

/-!
Finite archive instantiation generated from the privacy-minimized CTF task
panel. A row is an offered task slot; assignment is the executed allocator
event, success is at least one correct verified submission, failureOnly is an
incorrect submission without a later correct submission, and unattempted means
the assigned task has no recorded submission. These categories partition
assigned slots in this archived sample.

The calibration uses stage1 only. Stage2 was held out by the source archive
split and is reported separately; because this rate model was specified after
the archive was observed, the evaluation is retrospective and is not a
prospectively registered test. Mechanism-validation worlds are not pooled into
the I1/I3 calibration.

Source SHA-256 task panel: {source_hash}
Source SHA-256 world summary: {world_hash}
-/
namespace AgentMicrofoundations.CaseStudies.CTFArchive

inductive Family where
  | gpt
  | deepSeek
  deriving DecidableEq, Repr

inductive Regime where
  | i1
  | i3
  deriving DecidableEq, Repr

inductive Tier where
  | easy
  | medium
  | hard
  deriving DecidableEq, Repr

structure SlotCounts where
  family : Family
  regime : Regime
  tier : Tier
  offered : Nat
  proposedSlots : Nat
  proposalCalls : Nat
  toolOkCalls : Nat
  assigned : Nat
  success : Nat
  failureOnly : Nat
  unattempted : Nat
  deriving DecidableEq, Repr

def calibration : List SlotCounts := [
{make_cells('stage1')}
]

def heldOut : List SlotCounts := [
{make_cells('stage2')}
]

def slotCountsValid (row : SlotCounts) : Bool :=
  decide (row.assigned ≤ row.offered ∧ row.success ≤ row.assigned ∧
    row.proposedSlots ≤ row.offered ∧ row.proposedSlots ≤ row.proposalCalls ∧
    row.toolOkCalls ≤ row.proposalCalls ∧
    (if row.regime = .i1 then row.toolOkCalls = row.assigned else row.proposalCalls = 0) ∧
    row.failureOnly ≤ row.assigned ∧ row.unattempted ≤ row.assigned ∧
    row.success + row.failureOnly + row.unattempted = row.assigned)

theorem calibration_counts_are_archive_consistent :
    calibration.all slotCountsValid = true := by
  decide

theorem heldout_counts_are_archive_consistent :
    heldOut.all slotCountsValid = true := by
  decide

def observedSlotCount (rows : List SlotCounts) : Nat := rows.foldr (fun row n => row.offered + n) 0

def assignedSlotCount (rows : List SlotCounts) : Nat := rows.foldr (fun row n => row.assigned + n) 0

def verifiedSuccessSlotCount (rows : List SlotCounts) : Nat := rows.foldr (fun row n => row.success + n) 0

theorem raw_stage_counts :
    observedSlotCount calibration = {offered_totals['stage1']} ∧
    assignedSlotCount calibration = {assigned_totals['stage1']} ∧
    verifiedSuccessSlotCount calibration = {success_totals['stage1']} ∧
    observedSlotCount heldOut = {offered_totals['stage2']} ∧
    assignedSlotCount heldOut = {assigned_totals['stage2']} ∧
    verifiedSuccessSlotCount heldOut = {success_totals['stage2']} := by
  decide

structure HoldoutWorld where
  family : Family
  regime : Regime
  offered : Nat
  assigned : Nat
  success : Nat
  predictedAssignmentsNum : Nat
  predictedSuccessesNum : Nat
  predictionDenom : Nat
  deriving DecidableEq, Repr

def holdoutWorlds : List HoldoutWorld := [
{holdout_record_rows()}
]

def lookupCell (rows : List SlotCounts) (family : Family) (regime : Regime)
    (tier : Tier) : Option SlotCounts :=
  rows.find? (fun row => decide
    (row.family = family ∧ row.regime = regime ∧ row.tier = tier))

def calibrationOffered (family : Family) (regime : Regime) (tier : Tier) : Nat :=
  (lookupCell calibration family regime tier).map SlotCounts.offered |>.getD 0

def calibrationAssigned (family : Family) (regime : Regime) (tier : Tier) : Nat :=
  (lookupCell calibration family regime tier).map SlotCounts.assigned |>.getD 0

def calibrationSuccess (family : Family) (regime : Regime) (tier : Tier) : Nat :=
  (lookupCell calibration family regime tier).map SlotCounts.success |>.getD 0

def holdoutOffered (family : Family) (regime : Regime) (tier : Tier) : Nat :=
  (lookupCell heldOut family regime tier).map SlotCounts.offered |>.getD 0

/-- A parameterized task menu. Counts may be changed without predefining any
    agent subgroup; exact expectations are computed from calibration
    per-slot marginal rates when every nonempty tier has calibration support. -/
structure TaskSupply where
  easy : Nat
  medium : Nat
  hard : Nat
  deriving DecidableEq, Repr

def tierHasCalibrationSupport (family : Family) (regime : Regime)
    (supplyCount : Nat) (tier : Tier) : Bool :=
  decide (supplyCount = 0 ∨ 0 < calibrationOffered family regime tier)

def taskSupplySupported (family : Family) (regime : Regime) (supply : TaskSupply) : Bool :=
  tierHasCalibrationSupport family regime supply.easy Tier.easy &&
    tierHasCalibrationSupport family regime supply.medium Tier.medium &&
    tierHasCalibrationSupport family regime supply.hard Tier.hard &&
    decide (supply.easy ≤ calibrationOffered family regime Tier.easy ∧
      supply.medium ≤ calibrationOffered family regime Tier.medium ∧
      supply.hard ≤ calibrationOffered family regime Tier.hard) &&
    decide (calibrationOffered family regime Tier.easy =
      calibrationOffered family regime Tier.medium ∧
      calibrationOffered family regime Tier.medium =
      calibrationOffered family regime Tier.hard)

def taskSupplyNumerator (supply : TaskSupply) (rate : Tier → Nat) : Nat :=
  supply.easy * rate Tier.easy + supply.medium * rate Tier.medium +
    supply.hard * rate Tier.hard

def taskSupplyDenominator (family : Family) (regime : Regime) : Nat :=
  calibrationOffered family regime Tier.easy

/-- Exact conditional expected counts for an arbitrary menu of task tiers.
    This is a calibrated baseline, not a theorem about agent choice. It uses
    linearity of expectation and makes no cross-slot independence assumption;
    its identifying restriction is stable marginal assignment/success rates
    within family × regime × tier and equal calibration exposure across tiers.
    Empty unsupported tiers are harmless, while a requested nonempty
    unsupported or out-of-range tier exposure, or an unbalanced calibration
    cell, returns `none` (the refusal rule). This is interpolation within the
    observed slot support, not extrapolation to more slots. Numerator/denominator
    pairs are exact rational numbers. -/
def taskSupplyForecast (family : Family) (regime : Regime)
    (supply : TaskSupply) : Option ((Nat × Nat) × (Nat × Nat)) :=
  if taskSupplySupported family regime supply then
    some ((taskSupplyNumerator supply (calibrationAssigned family regime),
        taskSupplyDenominator family regime),
      (taskSupplyNumerator supply (calibrationSuccess family regime),
        taskSupplyDenominator family regime))
  else none

theorem gpt_i1_small_menu_forecast :
    taskSupplyForecast .gpt .i1 {{ easy := 2, medium := 1, hard := 0 }} =
      some ((108, 40), (38, 40)) := by
  decide

theorem gpt_i1_hard_menu_forecast :
    taskSupplyForecast .gpt .i1 {{ easy := 0, medium := 0, hard := 1 }} =
      some ((25, 40), (0, 40)) := by
  decide

theorem out_of_calibration_task_supply_is_rejected :
    taskSupplyForecast .gpt .i1 {{ easy := 41, medium := 0, hard := 0 }} = none := by
  decide

/-! Since calibration exposure is balanced across the three task tiers within
each family × regime cell, the denominator is the shared per-tier calibration
exposure. Integer numerators below encode the exact frequency forecast without
floating-point rounding. -/

def expectedAssignmentNumerator (family : Family) (regime : Regime) : Nat :=
  [Tier.easy, Tier.medium, Tier.hard].foldl (fun total tier =>
    total + holdoutOffered family regime tier * calibrationAssigned family regime tier) 0

def expectedSuccessNumerator (family : Family) (regime : Regime) : Nat :=
  [Tier.easy, Tier.medium, Tier.hard].foldl (fun total tier =>
    total + holdoutOffered family regime tier * calibrationSuccess family regime tier) 0

def commonCalibrationDenominator (family : Family) (regime : Regime) : Nat :=
  calibrationOffered family regime Tier.easy

def expectedAssignmentCountFraction (family : Family) (regime : Regime) : Nat × Nat :=
  (expectedAssignmentNumerator family regime, commonCalibrationDenominator family regime)

def expectedSuccessCountFraction (family : Family) (regime : Regime) : Nat × Nat :=
  (expectedSuccessNumerator family regime, commonCalibrationDenominator family regime)

theorem calibration_tier_exposure_is_balanced :
    calibrationOffered .gpt .i1 .easy = calibrationOffered .gpt .i1 .medium ∧
    calibrationOffered .gpt .i1 .medium = calibrationOffered .gpt .i1 .hard ∧
    calibrationOffered .gpt .i3 .easy = calibrationOffered .gpt .i3 .medium ∧
    calibrationOffered .gpt .i3 .medium = calibrationOffered .gpt .i3 .hard ∧
    calibrationOffered .deepSeek .i1 .easy = calibrationOffered .deepSeek .i1 .medium ∧
    calibrationOffered .deepSeek .i1 .medium = calibrationOffered .deepSeek .i1 .hard ∧
    calibrationOffered .deepSeek .i3 .easy = calibrationOffered .deepSeek .i3 .medium ∧
    calibrationOffered .deepSeek .i3 .medium = calibrationOffered .deepSeek .i3 .hard := by
  decide

/-! The predictor is conditional on the task slots actually offered in each
held-out world. It does not predict how long a world survives or how many
future menus occur. The rates use calibration task-slot frequencies and make
no cross-task independence claim. -/

theorem frozen_stage2_point_predictions :
    expectedAssignmentNumerator .gpt .i1 = 2046 ∧ commonCalibrationDenominator .gpt .i1 = 40 ∧
    expectedSuccessNumerator .gpt .i1 = 440 ∧
    expectedAssignmentNumerator .gpt .i3 = 1008 ∧ commonCalibrationDenominator .gpt .i3 = 38 ∧
    expectedSuccessNumerator .gpt .i3 = 228 ∧
    expectedAssignmentNumerator .deepSeek .i1 = 408 ∧ commonCalibrationDenominator .deepSeek .i1 = 17 ∧
    expectedSuccessNumerator .deepSeek .i1 = 12 ∧
    expectedAssignmentNumerator .deepSeek .i3 = 675 ∧ commonCalibrationDenominator .deepSeek .i3 = 19 ∧
    expectedSuccessNumerator .deepSeek .i3 = 45 := by
  decide

def absoluteDifference (left right : Nat) : Nat :=
  if left ≤ right then right - left else left - right

/-- A descriptive point-error screen: reject if the absolute error in the
    predicted event rate exceeds five percentage points. It has no sampling
    distribution or nominal statistical level. -/
def exceedsFivePercentagePoints (observed offered predictedNumerator denominator : Nat) : Bool :=
  decide (20 * absoluteDifference (observed * denominator) predictedNumerator >
    offered * denominator)

def assignmentForecastRejected (row : HoldoutWorld) : Bool :=
  exceedsFivePercentagePoints row.assigned row.offered
    row.predictedAssignmentsNum row.predictionDenom

def successForecastRejected (row : HoldoutWorld) : Bool :=
  exceedsFivePercentagePoints row.success row.offered
    row.predictedSuccessesNum row.predictionDenom

theorem assignment_forecast_exceeds_five_point_screen_in_all_holdout_cells :
    holdoutWorlds.all assignmentForecastRejected = true := by
  decide

theorem verified_success_screen_flags_only_deepseek_i1 :
    holdoutWorlds.map successForecastRejected = [false, false, true, false] := by
  decide

def holdoutCountsValid (row : HoldoutWorld) : Bool :=
  decide (row.assigned ≤ row.offered ∧ row.success ≤ row.assigned)

theorem heldout_world_counts_are_valid :
    holdoutWorlds.all holdoutCountsValid = true := by
  decide

theorem observed_holdout_totals_by_world :
    (holdoutWorlds.map HoldoutWorld.offered).sum = 183 ∧
    (holdoutWorlds.map HoldoutWorld.assigned).sum = 129 ∧
    (holdoutWorlds.map HoldoutWorld.success).sum = 19 := by
  decide

def archiveWorldCount : Nat := {len(world_rows)}
def calibrationWorldCount : Nat := {stage1_worlds}
def heldOutWorldCount : Nat := {stage2_worlds}
def mechanismWorldCount : Nat := {mechanism_worlds}
def traceJoinedWorldCount : Nat := {trace_joined}
def allWorldResourceLedgerReplaysMatch : Bool := {str(all(w['resource_ledger_replay_match'] == '1' for w in world_rows)).lower()}

theorem archive_world_split_is_complete :
    calibrationWorldCount + heldOutWorldCount + mechanismWorldCount = archiveWorldCount := by
  decide

theorem every_world_has_agent_trace_join : traceJoinedWorldCount = archiveWorldCount := by
  decide

theorem every_world_resource_ledger_replays_to_terminal_state :
    allWorldResourceLedgerReplaysMatch = true := by
  decide

end AgentMicrofoundations.CaseStudies.CTFArchive
''')
    print(f"Generated {TARGET}")


if __name__ == "__main__":
    main()
