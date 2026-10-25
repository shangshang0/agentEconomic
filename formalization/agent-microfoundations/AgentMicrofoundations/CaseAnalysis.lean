import AgentMicrofoundations.Ontology
import AgentMicrofoundations.ResponseIdentification

/-!
The case-analysis layer is deliberately downstream from the reusable
microfoundations. A case selects/calibrates a model using calibration rows;
held-out observations are only compared with predictions and are not an input
to the fitted model's type. The tolerance is a predeclared discrepancy band,
not a confidence interval: a statistical interpretation additionally requires
an explicit sampling-unit and dependence design.
-/
namespace AgentMicrofoundations.CaseAnalysis

open AgentMicrofoundations.Ontology

/-- Number of rows in which an event is observed. These rows must be the
    evaluation units declared by the case (for example, independent worlds),
    not automatically nested request rows. -/
def eventCount {Outcome : Type} : List Outcome → (Outcome → Bool) → Nat
  | [], _ => 0
  | outcome :: rest, event =>
      (if event outcome then 1 else 0) + eventCount rest event

/-- Sum of the theory's event probabilities over the inputs of a held-out
    sample. This is an expected count under the fitted case model. -/
def predictedEventCount {Input Outcome : Type}
    (law : Input → FiniteDistribution Outcome) :
    List (Input × Outcome) → (Outcome → Bool) → Rat
  | [], _ => 0
  | (input, _) :: rest, event =>
      eventMass (law input) event + predictedEventCount law rest event

/-- A case-level evaluation pipeline. The fitted model is computed by applying
    a declared fitting function to calibrationRows; heldOutRows enter only the
    evaluation predicates below. This records the data flow, but Lean cannot
    prove that a human did not encode held-out information inside the fitting
    function when constructing the record. Freeze that function before
    revealing the holdout. -/
structure SplitCaseAnalysis
    (Foundation Calibration Input Outcome : Type) where
  calibrationRows : List Calibration
  heldOutRows : List (Input × Outcome)
  estimate : List Calibration → Foundation
  law : Foundation → Input → FiniteDistribution Outcome
  tolerance : Rat
  toleranceNonnegative : 0 ≤ tolerance

def fittedFoundation {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome) : Foundation :=
  analysis.estimate analysis.calibrationRows

def fittedLaw {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome)
    (input : Input) : FiniteDistribution Outcome :=
  analysis.law (fittedFoundation analysis) input

def observedEventCount {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome)
    (event : Outcome → Bool) : Rat :=
  (eventCount (analysis.heldOutRows.map Prod.snd) event : Rat)

def predictedCaseEventCount {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome)
    (event : Outcome → Bool) : Rat :=
  AgentMicrofoundations.CaseAnalysis.predictedEventCount (fittedLaw analysis)
    analysis.heldOutRows event

def toleranceAllowance {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome) : Rat :=
  analysis.tolerance * (analysis.heldOutRows.length : Rat)

/-- A predeclared finite-sample discrepancy check between the held-out event
    count and the model's expected event count. It does not itself claim a
    sampling distribution or statistical coverage guarantee. -/
def withinTolerance {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome)
    (event : Outcome → Bool) : Prop :=
  observedEventCount analysis event ≤
      predictedCaseEventCount analysis event + toleranceAllowance analysis ∧
    predictedCaseEventCount analysis event ≤
      observedEventCount analysis event + toleranceAllowance analysis

/-- The expected-count band is a descriptive discrepancy screen. It is not a
    calibrated statistical test because the marginal laws alone do not specify
    the joint sampling distribution or the finite-sample tail probability. -/
def outsideMeanBand {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome)
    (event : Outcome → Bool) : Prop :=
  predictedCaseEventCount analysis event + toleranceAllowance analysis <
      observedEventCount analysis event ∨
    observedEventCount analysis event + toleranceAllowance analysis <
      predictedCaseEventCount analysis event

/-- Exact finite-sample test whose samplingLaw is the declared joint null law
    for the evaluation unit (for example, a world-level outcome vector). The
    law may encode arbitrary dependence. `levelBound` is a checkable case
    obligation: compute the test's exact rejection mass under this law and
    establish that it is at most the prespecified level. Row-wise marginals do
    not determine this joint law. -/
structure ExactFiniteCaseTest (Outcome : Type) where
  samplingLaw : FiniteDistribution (List Outcome)
  reject : List Outcome → Bool
  level : Rat
  levelNonnegative : 0 ≤ level
  levelBound : eventMass samplingLaw reject ≤ level

/-- Exact false-rejection probability under the explicitly declared null
    sampling law. -/
def exactRejectionProbability {Outcome : Type}
    (test : ExactFiniteCaseTest Outcome) : Rat :=
  eventMass test.samplingLaw test.reject

/-- The case test controls its finite-sample rejection probability at the
    declared level under its stated joint sampling law. This says nothing about
    whether that law is empirically correct; that is a separate case-model
    assumption open to rejection. -/
theorem exact_case_test_controls_rejection_probability {Outcome : Type}
    (test : ExactFiniteCaseTest Outcome) :
    exactRejectionProbability test ≤ test.level := by
  exact test.levelBound

/-- Any particular rejected sample has null probability at most the test
    level. Its singleton event is contained in the rejection region, so its
    mass cannot exceed the certified total rejection mass. This gives a
    pointwise interpretation of an exact finite-sample rejection certificate. -/
theorem rejected_sample_point_mass_le_level {Outcome : Type}
    [DecidableEq Outcome]
    (test : ExactFiniteCaseTest Outcome) (sample : List Outcome)
    (rejected : test.reject sample = true) :
    eventMass test.samplingLaw (fun candidate => decide (candidate = sample)) ≤
      test.level := by
  have inclusion : ∀ candidate weight,
      (candidate, weight) ∈ test.samplingLaw.outcomes → 0 < weight →
        decide (candidate = sample) = true → test.reject candidate = true := by
    intro candidate weight _ _ equal
    have candidateEq : candidate = sample := of_decide_eq_true equal
    rw [candidateEq]
    exact rejected
  have singletonLeReject :=
    AgentMicrofoundations.ResponseIdentification.eventFold_mono_of_support_inclusion
      test.samplingLaw.outcomes (fun candidate => decide (candidate = sample))
      test.reject test.samplingLaw.nonnegative inclusion
  calc
    eventMass test.samplingLaw (fun candidate => decide (candidate = sample)) ≤
        eventMass test.samplingLaw test.reject := by
      simpa [eventMass, AgentMicrofoundations.ResponseIdentification.eventFold]
        using singletonLeReject
    _ = exactRejectionProbability test := rfl
    _ ≤ test.level := test.levelBound

/-- With the same frozen fitting function and calibration rows, changing the
    held-out sample cannot change the fitted foundation. This is the formal
    noninterference guarantee provided by the interface; provenance/freeze is
    an empirical protocol obligation. -/
theorem fitted_foundation_invariant_to_holdout
    {Foundation Calibration Input Outcome : Type}
    (first second : SplitCaseAnalysis Foundation Calibration Input Outcome)
    (sameFit : first.estimate = second.estimate)
    (sameCalibration : first.calibrationRows = second.calibrationRows) :
    fittedFoundation first = fittedFoundation second := by
  unfold fittedFoundation
  rw [sameFit, sameCalibration]

theorem held_out_excess_exceeds_descriptive_band
    {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome)
    (event : Outcome → Bool)
    (excess : predictedCaseEventCount analysis event +
        toleranceAllowance analysis < observedEventCount analysis event) :
    outsideMeanBand analysis event := by
  exact Or.inl excess

theorem held_out_shortfall_exceeds_descriptive_band
    {Foundation Calibration Input Outcome : Type}
    (analysis : SplitCaseAnalysis Foundation Calibration Input Outcome)
    (event : Outcome → Bool)
    (shortfall : observedEventCount analysis event +
        toleranceAllowance analysis < predictedCaseEventCount analysis event) :
    outsideMeanBand analysis event := by
  exact Or.inr shortfall

end AgentMicrofoundations.CaseAnalysis
