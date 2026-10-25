import Std

/-!
One-round causal interface separating agent proposals from institutional
execution and verified production. The mechanism is applied after proposals
are recorded. `productiveIfExecuted` is a fixed potential outcome, so this
interface does not cover mechanisms that change the task or production process.
-/
namespace AgentMicrofoundations.CausalInterface

structure Trial where
  proposal : Option Bool
  productiveIfExecuted : Bool
  deriving DecidableEq, Repr

def proposed (trial : Trial) : Bool := trial.proposal.isSome

def executed (gateOpen : Bool) (trial : Trial) : Bool :=
  proposed trial && gateOpen

def verifiedProduction (gateOpen : Bool) (trial : Trial) : Bool :=
  executed gateOpen trial && trial.productiveIfExecuted

def countWhere (trials : List Trial) (predicate : Trial → Bool) : Nat :=
  (trials.filter predicate).length

theorem countWhere_mono (trials : List Trial) (p q : Trial → Bool)
    (implication : ∀ trial, p trial = true → q trial = true) :
    countWhere trials p ≤ countWhere trials q := by
  induction trials with
  | nil => simp [countWhere]
  | cons trial rest ih =>
      have ih' := ih
      have ihFilter : (rest.filter p).length ≤ (rest.filter q).length := by
        simpa [countWhere] using ih'
      by_cases hp : p trial = true
      · have hq := implication trial hp
        simp [countWhere, hp, hq]
        omega
      · by_cases hq : q trial = true
        · simp [countWhere, hp, hq]
          omega
        · simpa [countWhere, hp, hq] using ihFilter

def proposalCount (trials : List Trial) : Nat :=
  countWhere trials proposed

def executionCount (gateOpen : Bool) (trials : List Trial) : Nat :=
  countWhere trials (executed gateOpen)

def verifiedProductionCount (gateOpen : Bool) (trials : List Trial) : Nat :=
  countWhere trials (verifiedProduction gateOpen)

/- Verified production is nested inside execution, which is nested inside
   proposal. This is a finite-trace restriction that requires no independence
   assumptions between agents or trials. -/
theorem verified_count_le_execution_count
    (gateOpen : Bool) (trials : List Trial) :
    verifiedProductionCount gateOpen trials ≤ executionCount gateOpen trials := by
  apply countWhere_mono
  intro trial h
  simp only [verifiedProduction, executed, Bool.and_eq_true] at h ⊢
  exact h.1

theorem execution_count_le_proposal_count
    (gateOpen : Bool) (trials : List Trial) :
    executionCount gateOpen trials ≤ proposalCount trials := by
  apply countWhere_mono
  intro trial h
  simp only [executed, Bool.and_eq_true] at h ⊢
  exact h.1

theorem closed_gate_prevents_verified_production
    (trials : List Trial) : verifiedProductionCount false trials = 0 := by
  simp [verifiedProductionCount, countWhere, verifiedProduction, executed]

/- Opening the gate changes realized output only for proposals whose fixed
   production potential is positive. This is the direct mechanism effect in
   this deliberately narrow model. -/
theorem open_gate_output_is_proposal_times_fixed_production
    (trial : Trial) :
    verifiedProduction true trial =
      (proposed trial && trial.productiveIfExecuted) := by
  cases trial with
  | mk proposal productive => cases proposal <;> cases productive <;> rfl

/- Final outcomes under a closed gate do not identify whether there was no
   proposal or a proposal blocked by the mechanism. Recording proposals is
   therefore necessary to separate behavior from institutional filtering. -/
theorem closed_gate_observational_equivalence_example :
    verifiedProduction false ⟨none, true⟩ =
        verifiedProduction false ⟨some true, true⟩ ∧
      proposed ⟨none, true⟩ ≠ proposed ⟨some true, true⟩ := by
  decide

end AgentMicrofoundations.CausalInterface
