import AgentMicrofoundations.AutoregressiveResponse
import AgentMicrofoundations.TokenAccounting
import AgentMicrofoundations.CouplingComparativeStatics

/-!
Resource budgets and response probabilities need not move in the same
direction.

The affordable generation budget is weakly increasing in the spendable
resource balance, but an action parser may map longer generated traces to a
different proposal. This module gives a small counterexample under one fixed
token kernel and parser: increasing the budget lowers the probability of a
designated productive proposal. It rules out a universal monotonicity claim;
it does not claim that this particular parser or behavior occurs in the case
study.
-/
namespace AgentMicrofoundations.ResourceBudgetComparativeStatics

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AutoregressiveResponse
open AgentMicrofoundations.TokenAccounting
open AgentMicrofoundations.CouplingComparativeStatics

/-- Fixed constitutive response process used only for a logical
    counterexample. The token kernel emits `true` on the first position and
    `false` on later positions. The fixed parser accepts a trace only when all
    generated tokens are `true`. -/
def budgetCounterexampleConstitution : AutoregressiveConstitution Unit Bool Bool :=
  { prompt := fun _ => []
    nextToken := fun tokensSoFar =>
      if tokensSoFar.isEmpty then pureDistribution true else pureDistribution false
    stopToken := fun _ => false
    parseProposal := fun {_budget : Nat} => fun trace => trace.tokens.all id }

/-- With a one-token budget the fixed process proposes the productive action
    with certainty. -/
theorem unit_budget_productive_probability_one :
    eventMass (proposalLaw budgetCounterexampleConstitution () 1) id = 1 := by
  simp [proposalLaw, budgetCounterexampleConstitution, generatedTokenTrace,
    extendGeneratedTrace,
    bindDistribution, bindEntries, mapDistribution, mapEntries, pureDistribution,
    scaleEntries, eventMass, Rat.add_zero]

/-- With a two-token budget the same fixed process produces one additional
    invalidating token, so the probability of the productive action is zero.
    More computational capacity therefore does not universally imply a higher
    probability of this outcome. -/
theorem larger_budget_can_lower_productive_probability :
    eventMass (proposalLaw budgetCounterexampleConstitution () 2) id = 0 := by
  simp [proposalLaw, budgetCounterexampleConstitution, generatedTokenTrace,
    extendGeneratedTrace,
    bindDistribution, bindEntries, mapDistribution, mapEntries, pureDistribution,
    scaleEntries, eventMass]

theorem no_universal_budget_monotonicity_for_productive_probability :
    ¬ (∀ (firstBudget secondBudget : Nat), firstBudget ≤ secondBudget →
      eventMass (proposalLaw budgetCounterexampleConstitution () firstBudget) id ≤
        eventMass (proposalLaw budgetCounterexampleConstitution () secondBudget) id) := by
  intro monotone
  have counterexample := monotone 1 2 (by decide)
  rw [unit_budget_productive_probability_one,
    larger_budget_can_lower_productive_probability] at counterexample
  exact (Rat.not_le.mpr (by decide : (0 : Rat) < 1)) counterexample

/-- The fixed-parser budget counterexample cannot admit any coupling under
    which productive outputs are support-wise nested from budget one to budget
    two. Thus the coupling premise in the monotonicity theorem is substantive,
    not a consequence of merely sharing an autoregressive constitution. -/
theorem budget_counterexample_rules_out_productivity_nested_couplings :
    ∀ coupling : FiniteCoupling
      (proposalLaw budgetCounterexampleConstitution () 1)
      (proposalLaw budgetCounterexampleConstitution () 2),
      ¬ (∀ pair weight, (pair, weight) ∈ coupling.joint.outcomes →
        0 < weight → id pair.1 = true → id pair.2 = true) := by
  intro coupling nested
  have monotoneProbability :=
    event_probability_mono_under_support_monotone_coupling coupling id id nested
  rw [unit_budget_productive_probability_one,
    larger_budget_can_lower_productive_probability] at monotoneProbability
  exact (Rat.not_le.mpr (by decide : (0 : Rat) < 1)) monotoneProbability

/-- In the linear token-account special case, increasing spendable balance
    from one to two raises the affordable budget from one to two, while the
    same fixed autoregressive process lowers the productive-action probability
    from one to zero. This rules out deriving productive-probability
    monotonicity from resource-to-budget monotonicity alone. -/
theorem resource_increase_can_lower_productive_probability :
    affordableGenerationBudget 1 1 2 < affordableGenerationBudget 2 1 2 ∧
      eventMass (proposalLaw budgetCounterexampleConstitution ()
        (affordableGenerationBudget 1 1 2)) id >
      eventMass (proposalLaw budgetCounterexampleConstitution ()
        (affordableGenerationBudget 2 1 2)) id := by
  have lowBudget : affordableGenerationBudget 1 1 2 = 1 := by decide
  have highBudget : affordableGenerationBudget 2 1 2 = 2 := by decide
  constructor
  · rw [lowBudget, highBudget]
    decide
  · rw [lowBudget, highBudget, unit_budget_productive_probability_one,
      larger_budget_can_lower_productive_probability]
    decide

end AgentMicrofoundations.ResourceBudgetComparativeStatics
