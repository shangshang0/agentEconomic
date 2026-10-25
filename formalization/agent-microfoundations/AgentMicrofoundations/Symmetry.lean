import Std

/-!
Symmetry boundary for endogenous role differentiation.

The result is deliberately narrow: with a deterministic response rule, equal
complete inputs imply equal actions. It does not say that a shared system
prompt is a complete input, nor does it cover stochastic decoding.
-/
namespace AgentMicrofoundations.Symmetry

structure CompleteInput (State Context Opportunity : Type) where
  state : State
  context : Context
  opportunity : Opportunity
  deriving DecidableEq, Repr

theorem equal_complete_input_same_action
    {State Context Opportunity Action : Type}
    (response : CompleteInput State Context Opportunity → Action)
    (left right : CompleteInput State Context Opportunity)
    (sameInput : left = right) :
    response left = response right := by
  rw [sameInput]

theorem divergent_actions_require_input_difference
    {State Context Opportunity Action : Type}
    (response : CompleteInput State Context Opportunity → Action)
    (left right : CompleteInput State Context Opportunity)
    (differentActions : response left ≠ response right) :
    left ≠ right := by
  intro sameInput
  exact differentActions (equal_complete_input_same_action response left right sameInput)

theorem same_policy_allows_context_conditioned_role_split
    (leftAction rightAction : Bool) :
    (fun context : Bool => context) false = leftAction →
    (fun context : Bool => context) true = rightAction →
    leftAction ≠ rightAction := by
  intro leftRule rightRule sameAction
  have hleft : leftAction = false := by simpa using leftRule
  have hright : rightAction = true := by simpa using rightRule
  rw [hleft, hright] at sameAction
  cases sameAction

end AgentMicrofoundations.Symmetry
