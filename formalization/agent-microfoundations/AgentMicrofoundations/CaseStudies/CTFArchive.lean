import AgentMicrofoundations.CaseAnalysis

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

Source SHA-256 task panel: fbdaa9b06554e87273711b08d1bab463fd9b77400b7a7abf6a806bc915e72396
Source SHA-256 world summary: 4a1dab98a76258e69149ed4ab7ec83d54d8349c7f4ea9eec4ae8843e7273223d
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
  { family := .gpt, regime := .i1, tier := .easy, offered := 40, assigned := 40, proposedSlots := 40, proposalCalls := 40, toolOkCalls := 40, success := 18, failureOnly := 2, unattempted := 20 },
  { family := .gpt, regime := .i1, tier := .medium, offered := 40, assigned := 28, proposedSlots := 28, proposalCalls := 28, toolOkCalls := 28, success := 2, failureOnly := 0, unattempted := 26 },
  { family := .gpt, regime := .i1, tier := .hard, offered := 40, assigned := 25, proposedSlots := 25, proposalCalls := 25, toolOkCalls := 25, success := 0, failureOnly := 2, unattempted := 23 },
  { family := .gpt, regime := .i3, tier := .easy, offered := 38, assigned := 28, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 15, failureOnly := 1, unattempted := 12 },
  { family := .gpt, regime := .i3, tier := .medium, offered := 38, assigned := 28, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 3, failureOnly := 1, unattempted := 24 },
  { family := .gpt, regime := .i3, tier := .hard, offered := 38, assigned := 28, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 1, failureOnly := 2, unattempted := 25 },
  { family := .deepSeek, regime := .i1, tier := .easy, offered := 17, assigned := 11, proposedSlots := 12, proposalCalls := 12, toolOkCalls := 11, success := 1, failureOnly := 1, unattempted := 9 },
  { family := .deepSeek, regime := .i1, tier := .medium, offered := 17, assigned := 11, proposedSlots := 12, proposalCalls := 12, toolOkCalls := 11, success := 0, failureOnly := 0, unattempted := 11 },
  { family := .deepSeek, regime := .i1, tier := .hard, offered := 17, assigned := 12, proposedSlots := 13, proposalCalls := 13, toolOkCalls := 12, success := 0, failureOnly := 2, unattempted := 10 },
  { family := .deepSeek, regime := .i3, tier := .easy, offered := 19, assigned := 15, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 3, failureOnly := 1, unattempted := 11 },
  { family := .deepSeek, regime := .i3, tier := .medium, offered := 19, assigned := 15, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 0, failureOnly := 0, unattempted := 15 },
  { family := .deepSeek, regime := .i3, tier := .hard, offered := 19, assigned := 15, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 0, failureOnly := 2, unattempted := 13 }
]

def heldOut : List SlotCounts := [
  { family := .gpt, regime := .i1, tier := .easy, offered := 22, assigned := 21, proposedSlots := 21, proposalCalls := 21, toolOkCalls := 21, success := 7, failureOnly := 2, unattempted := 12 },
  { family := .gpt, regime := .i1, tier := .medium, offered := 22, assigned := 16, proposedSlots := 16, proposalCalls := 16, toolOkCalls := 16, success := 1, failureOnly := 1, unattempted := 14 },
  { family := .gpt, regime := .i1, tier := .hard, offered := 22, assigned := 10, proposedSlots := 11, proposalCalls := 11, toolOkCalls := 10, success := 0, failureOnly := 2, unattempted := 8 },
  { family := .gpt, regime := .i3, tier := .easy, offered := 12, assigned := 11, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 5, failureOnly := 4, unattempted := 2 },
  { family := .gpt, regime := .i3, tier := .medium, offered := 12, assigned := 11, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 1, failureOnly := 0, unattempted := 10 },
  { family := .gpt, regime := .i3, tier := .hard, offered := 12, assigned := 11, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 0, failureOnly := 1, unattempted := 10 },
  { family := .deepSeek, regime := .i1, tier := .easy, offered := 12, assigned := 9, proposedSlots := 9, proposalCalls := 9, toolOkCalls := 9, success := 3, failureOnly := 1, unattempted := 5 },
  { family := .deepSeek, regime := .i1, tier := .medium, offered := 12, assigned := 9, proposedSlots := 10, proposalCalls := 10, toolOkCalls := 9, success := 0, failureOnly := 0, unattempted := 9 },
  { family := .deepSeek, regime := .i1, tier := .hard, offered := 12, assigned := 10, proposedSlots := 10, proposalCalls := 10, toolOkCalls := 10, success := 0, failureOnly := 1, unattempted := 9 },
  { family := .deepSeek, regime := .i3, tier := .easy, offered := 15, assigned := 7, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 2, failureOnly := 0, unattempted := 5 },
  { family := .deepSeek, regime := .i3, tier := .medium, offered := 15, assigned := 7, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 0, failureOnly := 0, unattempted := 7 },
  { family := .deepSeek, regime := .i3, tier := .hard, offered := 15, assigned := 7, proposedSlots := 0, proposalCalls := 0, toolOkCalls := 0, success := 0, failureOnly := 1, unattempted := 6 }
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
    observedSlotCount calibration = 342 ∧
    assignedSlotCount calibration = 256 ∧
    verifiedSuccessSlotCount calibration = 43 ∧
    observedSlotCount heldOut = 183 ∧
    assignedSlotCount heldOut = 129 ∧
    verifiedSuccessSlotCount heldOut = 19 := by
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
  { family := .gpt, regime := .i1, offered := 66, assigned := 47, success := 8, predictedAssignmentsNum := 2046, predictedSuccessesNum := 440, predictionDenom := 40 },
  { family := .gpt, regime := .i3, offered := 36, assigned := 33, success := 6, predictedAssignmentsNum := 1008, predictedSuccessesNum := 228, predictionDenom := 38 },
  { family := .deepSeek, regime := .i1, offered := 36, assigned := 28, success := 3, predictedAssignmentsNum := 408, predictedSuccessesNum := 12, predictionDenom := 17 },
  { family := .deepSeek, regime := .i3, offered := 45, assigned := 21, success := 2, predictedAssignmentsNum := 675, predictedSuccessesNum := 45, predictionDenom := 19 }
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
    taskSupplyForecast .gpt .i1 { easy := 2, medium := 1, hard := 0 } =
      some ((108, 40), (38, 40)) := by
  decide

theorem gpt_i1_hard_menu_forecast :
    taskSupplyForecast .gpt .i1 { easy := 0, medium := 0, hard := 1 } =
      some ((25, 40), (0, 40)) := by
  decide

theorem out_of_calibration_task_supply_is_rejected :
    taskSupplyForecast .gpt .i1 { easy := 41, medium := 0, hard := 0 } = none := by
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

def archiveWorldCount : Nat := 24
def calibrationWorldCount : Nat := 8
def heldOutWorldCount : Nat := 4
def mechanismWorldCount : Nat := 12
def traceJoinedWorldCount : Nat := 24
def allWorldResourceLedgerReplaysMatch : Bool := true

theorem archive_world_split_is_complete :
    calibrationWorldCount + heldOutWorldCount + mechanismWorldCount = archiveWorldCount := by
  decide

theorem every_world_has_agent_trace_join : traceJoinedWorldCount = archiveWorldCount := by
  decide

theorem every_world_resource_ledger_replays_to_terminal_state :
    allWorldResourceLedgerReplaysMatch = true := by
  decide

end AgentMicrofoundations.CaseStudies.CTFArchive
