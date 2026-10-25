import Std

/-!
Finite-sample bounds for coalition production under arbitrary dependence.
Each row is one trial and each Boolean entry is one member's verified result.
No independence or exchangeability assumption is imposed.
-/
namespace AgentMicrofoundations.FiniteCoalitions

def memberSucceeds (member : Nat) (trial : List Bool) : Bool :=
  (trial[member]?).getD false

def coalitionSucceeds (trial : List Bool) : Bool := trial.any id

def countTrials (trials : List (List Bool)) (predicate : List Bool → Bool) : Nat :=
  (trials.filter predicate).length

theorem countTrials_mono (trials : List (List Bool)) (p q : List Bool → Bool)
    (implication : ∀ trial, p trial = true → q trial = true) :
    countTrials trials p ≤ countTrials trials q := by
  induction trials with
  | nil => simp [countTrials]
  | cons trial rest ih =>
      have ihRaw : (rest.filter p).length ≤ (rest.filter q).length := by
        simpa [countTrials] using ih
      by_cases hp : p trial = true
      · have hq := implication trial hp
        simp [countTrials, hp, hq]
        omega
      · by_cases hq : q trial = true
        · simp [countTrials, hp, hq]
          omega
        · simpa [countTrials, hp, hq] using ihRaw

theorem countTrials_le_sample_count
    (predicate : List Bool → Bool) (trials : List (List Bool)) :
    countTrials trials predicate ≤ trials.length := by
  induction trials with
  | nil => simp [countTrials]
  | cons trial rest ih =>
      have ihRaw : (rest.filter predicate).length ≤ rest.length := by
        simpa [countTrials] using ih
      by_cases h : predicate trial = true
      · simp [countTrials, h]
        omega
      · simp [countTrials, h]
        omega

def memberSuccessCount (member : Nat) (trials : List (List Bool)) : Nat :=
  countTrials trials (memberSucceeds member)

def coalitionSuccessCount (trials : List (List Bool)) : Nat :=
  countTrials trials coalitionSucceeds

def totalMemberSuccessCount (trials : List (List Bool)) : Nat :=
  (trials.map (fun trial => (trial.filter id).length)).sum

theorem member_success_implies_coalition_success
    (member : Nat) (trial : List Bool)
    (success : memberSucceeds member trial = true) :
    coalitionSucceeds trial = true := by
  induction trial generalizing member with
  | nil => simp [memberSucceeds] at success
  | cons head rest ih =>
      cases member with
      | zero =>
          change head = true at success
          simp [coalitionSucceeds, success]
      | succ member =>
          change memberSucceeds member rest = true at success
          have h := ih member success
          simp only [coalitionSucceeds, List.any_cons, Bool.or_eq_true]
          exact Or.inr h

theorem member_success_count_le_coalition_success_count
    (member : Nat) (trials : List (List Bool)) :
    memberSuccessCount member trials ≤ coalitionSuccessCount trials := by
  apply countTrials_mono
  intro trial h
  exact member_success_implies_coalition_success member trial h

theorem any_success_implies_positive_member_count
    (trial : List Bool)
    (success : coalitionSucceeds trial = true) :
    1 ≤ (trial.filter id).length := by
  induction trial with
  | nil => simp [coalitionSucceeds] at success
  | cons head rest ih =>
      cases head with
      | false =>
          have hmem : true ∈ rest := by
            simpa [coalitionSucceeds] using success
          have hrest : coalitionSucceeds rest = true := by
            simpa [coalitionSucceeds] using hmem
          have h := ih hrest
          simp
          omega
      | true => simp

theorem coalition_success_count_le_total_member_success_count
    (trials : List (List Bool)) :
    coalitionSuccessCount trials ≤ totalMemberSuccessCount trials := by
  induction trials with
  | nil => simp [coalitionSuccessCount, countTrials, totalMemberSuccessCount]
  | cons trial rest ih =>
      have ihRaw :
          (rest.filter coalitionSucceeds).length ≤
            (rest.map (fun trial => (trial.filter id).length)).sum := by
        simpa [coalitionSuccessCount, countTrials, totalMemberSuccessCount] using ih
      by_cases hc : coalitionSucceeds trial = true
      · have hpositive := any_success_implies_positive_member_count trial hc
        simp [coalitionSuccessCount, countTrials, totalMemberSuccessCount, hc]
        omega
      · simp [coalitionSuccessCount, countTrials, totalMemberSuccessCount, hc]
        omega

theorem coalition_success_count_le_sample_count
    (trials : List (List Bool)) :
    coalitionSuccessCount trials ≤ trials.length := by
  exact countTrials_le_sample_count coalitionSucceeds trials

theorem coalition_success_finite_sample_bounds
    (member : Nat) (trials : List (List Bool)) :
    memberSuccessCount member trials ≤ coalitionSuccessCount trials ∧
      coalitionSuccessCount trials ≤ totalMemberSuccessCount trials ∧
      coalitionSuccessCount trials ≤ trials.length := by
  exact ⟨member_success_count_le_coalition_success_count member trials,
    coalition_success_count_le_total_member_success_count trials,
    coalition_success_count_le_sample_count trials⟩

/- The same one-half individual marginal can yield very different coalition
   success rates when dependence changes: perfectly aligned outcomes versus
   mutually exclusive successes. -/
def alignedPairTrials : List (List Bool) :=
  [[true, true], [false, false]]

def disjointPairTrials : List (List Bool) :=
  [[true, false], [false, true]]

theorem equal_marginals_do_not_identify_coalition_output :
    memberSuccessCount 0 alignedPairTrials = 1 ∧
      memberSuccessCount 1 alignedPairTrials = 1 ∧
      memberSuccessCount 0 disjointPairTrials = 1 ∧
      memberSuccessCount 1 disjointPairTrials = 1 ∧
      coalitionSuccessCount alignedPairTrials = 1 ∧
      coalitionSuccessCount disjointPairTrials = 2 := by
  decide

end AgentMicrofoundations.FiniteCoalitions
