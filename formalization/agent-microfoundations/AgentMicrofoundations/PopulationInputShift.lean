import AgentMicrofoundations.AutoregressiveContext
import AgentMicrofoundations.ResponseIdentification

/-!
Population response bound under changes in complete computational input.

With each matched agent's own response kernel fixed across conditions, agents
whose complete inputs are unchanged have identical proposal-event
probabilities. Every changed input can alter that agent's event probability by
at most one. Summing gives a population-level bound without assumptions about
rationality, common constitutions across agents, independence, or the sign of
a context effect.
-/
namespace AgentMicrofoundations.PopulationInputShift

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AutoregressiveResponse
open AgentMicrofoundations.AutoregressiveContext
open AgentMicrofoundations.ResponseIdentification

def eventRateSum {Agent Context Outcome : Type}
    (rows : List (Agent × (Context × Context)))
    (response : Agent → Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) : Rat :=
  rows.foldr
    (fun row total => eventMass (response row.1 row.2.1) event + total) 0

def changedInputMass {Agent Context : Type} [DecidableEq Context]
    (rows : List (Agent × (Context × Context))) : Rat :=
  rows.foldr
    (fun row total => (if row.2.1 = row.2.2 then 0 else 1) + total) 0

/-- The complete autoregressive input relevant to a proposal law once the
    constitution (including token kernel, stop rule, and parser) is fixed. -/
abbrev AutoregressiveInput (Token : Type) := List Token × Nat

def promptConstitution {Context Token Proposal : Type}
    (constitution : AutoregressiveConstitution Context Token Proposal) :
    AutoregressiveConstitution (List Token) Token Proposal :=
  ⟨id, constitution.nextToken, constitution.stopToken,
    constitution.parseProposal⟩

def proposalLawFromInput {Context Token Proposal : Type}
    (constitution : AutoregressiveConstitution Context Token Proposal)
    (input : AutoregressiveInput Token) : FiniteDistribution Proposal :=
  proposalLaw (promptConstitution constitution) input.1 input.2

/-- Across matched subjects, each subject's fixed conditional response law
    cannot change an aggregate event rate by more than the number of subjects
    whose complete input changed. Constitutions may differ across subjects.
    This is an expected-count bound; it makes no independence assumption about
    realized proposals. -/
theorem fixed_kernel_event_rate_shift_bounded_by_changed_inputs
    {Agent Context Outcome : Type} [DecidableEq Context]
    (rows : List (Agent × (Context × Context)))
    (response : Agent → Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) :
    (eventRateSum rows response event ≤
      eventRateSum (rows.map fun row => (row.1, (row.2.2, row.2.1))) response event +
        changedInputMass rows) ∧
    (eventRateSum (rows.map fun row => (row.1, (row.2.2, row.2.1))) response event ≤
      eventRateSum rows response event + changedInputMass rows) := by
  induction rows with
  | nil =>
      constructor
      · change (0 : Rat) ≤ 0 + 0
        calc
          0 ≤ 0 := Rat.le_refl
          _ = 0 + 0 := (Rat.zero_add 0).symm
      · change (0 : Rat) ≤ 0 + 0
        calc
          0 ≤ 0 := Rat.le_refl
          _ = 0 + 0 := (Rat.zero_add 0).symm
  | cons row rest ih =>
      rcases row with ⟨agent, contexts⟩
      rcases contexts with ⟨left, right⟩
      change
        (eventMass (response agent left) event + eventRateSum rest response event ≤
          eventMass (response agent right) event +
            eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event +
              ((if left = right then 0 else 1) + changedInputMass rest)) ∧
        (eventMass (response agent right) event +
            eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event ≤
          eventMass (response agent left) event + eventRateSum rest response event +
            ((if left = right then 0 else 1) + changedInputMass rest))
      by_cases sameInput : left = right
      · subst right
        simp
        rcases ih with ⟨firstTailBound, secondTailBound⟩
        constructor
        · calc
            eventMass (response agent left) event + eventRateSum rest response event ≤
                eventMass (response agent left) event +
                  (eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event +
                    changedInputMass rest) :=
              Rat.add_le_add_left.mpr firstTailBound
            _ = eventMass (response agent left) event +
                eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event +
                  (0 + changedInputMass rest) := by ac_rfl
        · calc
            eventMass (response agent left) event +
                eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event ≤
                eventMass (response agent left) event +
                  (eventRateSum rest response event + changedInputMass rest) :=
              Rat.add_le_add_left.mpr secondTailBound
            _ = eventMass (response agent left) event + eventRateSum rest response event +
                  (0 + changedInputMass rest) := by ac_rfl
      · have firstProbabilityNonnegative :=
          eventMass_nonnegative (response agent left) event
        have firstProbabilityBounded := eventMass_le_one (response agent left) event
        have secondProbabilityNonnegative :=
          eventMass_nonnegative (response agent right) event
        have secondProbabilityBounded := eventMass_le_one (response agent right) event
        have firstHeadBound : eventMass (response agent left) event ≤
            eventMass (response agent right) event + 1 := by
          calc
            eventMass (response agent left) event ≤ 1 := firstProbabilityBounded
            _ ≤ 1 + eventMass (response agent right) event := by
              calc
                1 = (1 : Rat) + 0 := (Rat.add_zero 1).symm
                _ ≤ 1 + eventMass (response agent right) event := by
                  exact Rat.add_le_add_left.mpr secondProbabilityNonnegative
            _ = eventMass (response agent right) event + 1 := by ac_rfl
        have secondHeadBound : eventMass (response agent right) event ≤
            eventMass (response agent left) event + 1 := by
          calc
            eventMass (response agent right) event ≤ 1 := secondProbabilityBounded
            _ ≤ 1 + eventMass (response agent left) event := by
              calc
                1 = (1 : Rat) + 0 := (Rat.add_zero 1).symm
                _ ≤ 1 + eventMass (response agent left) event := by
                  exact Rat.add_le_add_left.mpr firstProbabilityNonnegative
            _ = eventMass (response agent left) event + 1 := by ac_rfl
        rcases ih with ⟨firstTailBound, secondTailBound⟩
        simp only [eventRateSum, changedInputMass, if_neg sameInput]
        constructor
        · calc
            eventMass (response agent left) event + eventRateSum rest response event ≤
                (eventMass (response agent right) event + 1) +
                  eventRateSum rest response event :=
              Rat.add_le_add_right.mpr firstHeadBound
            _ ≤ (eventMass (response agent right) event + 1) +
                  (eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event +
                    changedInputMass rest) :=
              Rat.add_le_add_left.mpr firstTailBound
            _ = eventMass (response agent right) event +
                  eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event +
                  (1 + changedInputMass rest) := by ac_rfl
        · calc
            eventMass (response agent right) event +
                eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event ≤
                (eventMass (response agent left) event + 1) +
                  eventRateSum (rest.map fun row => (row.1, (row.2.2, row.2.1))) response event :=
              Rat.add_le_add_right.mpr secondHeadBound
            _ ≤ (eventMass (response agent left) event + 1) +
                  (eventRateSum rest response event + changedInputMass rest) :=
              Rat.add_le_add_left.mpr secondTailBound
            _ = eventMass (response agent left) event + eventRateSum rest response event +
                  (1 + changedInputMass rest) := by ac_rfl

/-- The same bound specialized to a fixed autoregressive constitution, parser,
    and context-to-budget rule. A changed context may alter the budget as well
    as the prompt; unchanged complete context preserves both. -/
theorem autoregressive_event_rate_shift_bounded_by_changed_inputs
    {Agent Context Token Proposal : Type} [DecidableEq Token]
    (rows : List (Agent × (AutoregressiveInput Token × AutoregressiveInput Token)))
    (constitution : Agent → AutoregressiveConstitution Context Token Proposal)
    (event : Proposal → Bool) :
    (eventRateSum rows (fun agent => proposalLawFromInput (constitution agent)) event ≤
      eventRateSum (rows.map fun row => (row.1, (row.2.2, row.2.1)))
        (fun agent => proposalLawFromInput (constitution agent)) event +
        changedInputMass rows) ∧
    (eventRateSum (rows.map fun row => (row.1, (row.2.2, row.2.1)))
      (fun agent => proposalLawFromInput (constitution agent)) event ≤
      eventRateSum rows
        (fun agent => proposalLawFromInput (constitution agent)) event +
        changedInputMass rows) :=
  fixed_kernel_event_rate_shift_bounded_by_changed_inputs rows
    (fun agent => proposalLawFromInput (constitution agent)) event

end AgentMicrofoundations.PopulationInputShift
