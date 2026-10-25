import Std

/-!
Finite population probability results for group production.

An outcome list is a finite empirical probability space: repeated rows encode
probability mass. No independence assumption is built into the representation.
-/
namespace AgentMicrofoundations.GroupProbability

abbrev PairOutcomes := List (Bool × Bool)

def firstSuccessCount (outcomes : PairOutcomes) : Nat :=
  (outcomes.filter (fun outcome => outcome.1)).length

def secondSuccessCount (outcomes : PairOutcomes) : Nat :=
  (outcomes.filter (fun outcome => outcome.2)).length

def anySuccessCount (outcomes : PairOutcomes) : Nat :=
  (outcomes.filter (fun outcome => outcome.1 || outcome.2)).length

/- The union event contains each member's success event, and its count is no
   larger than the sum of the two marginal counts. This is the finite-sample
   form of max(p₁,p₂) ≤ p(any) ≤ min(1,p₁+p₂), without independence. -/
theorem team_success_frechet_bounds (outcomes : PairOutcomes) :
    firstSuccessCount outcomes ≤ anySuccessCount outcomes ∧
      secondSuccessCount outcomes ≤ anySuccessCount outcomes ∧
      anySuccessCount outcomes ≤ firstSuccessCount outcomes + secondSuccessCount outcomes ∧
      anySuccessCount outcomes ≤ outcomes.length := by
  induction outcomes with
  | nil => simp [firstSuccessCount, secondSuccessCount, anySuccessCount]
  | cons outcome rest ih =>
      rcases outcome with ⟨first, second⟩
      cases first <;> cases second <;>
        simp [firstSuccessCount, secondSuccessCount, anySuccessCount] at * <;>
        omega

end AgentMicrofoundations.GroupProbability
