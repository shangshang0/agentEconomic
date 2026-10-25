import AgentMicrofoundations.Ontology
import AgentMicrofoundations.ResponseIdentification

/-!
Ex ante resource feasibility for stochastic agent populations with fractional
balances. The result places no restrictions on the allocation, production,
response, or dependence law that generated the next-state resource profile.
Only the operational meaning of a positive continuation reserve and
nonnegative balances are needed for the case application.
-/
namespace AgentMicrofoundations.ResourceSurvivalBound

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.ResponseIdentification

/-- Number of accounts whose rational balance meets a common continuation
    reserve. The list supplies the accounts in one realized state. -/
def viableRatCount (reserve : Rat) (balances : List Rat) : Nat :=
  (balances.filter (fun balance => decide (reserve ≤ balance))).length

/-- Resource stock currently held by viable accounts, measured at their
    common continuation reserve. -/
def viableRatLoad (reserve : Rat) (balances : List Rat) : Rat :=
  match balances with
  | [] => 0
  | balance :: rest =>
      if reserve ≤ balance then reserve + viableRatLoad reserve rest
      else viableRatLoad reserve rest

/-- Total rational resource stock in a realized state. -/
def totalRatStock (balances : List Rat) : Rat := balances.sum

theorem totalRatStock_nonnegative (balances : List Rat)
    (balancesNonnegative : ∀ balance, balance ∈ balances → 0 ≤ balance) :
    0 ≤ totalRatStock balances := by
  induction balances with
  | nil => simp [totalRatStock]
  | cons balance rest ih =>
      have balanceNonnegative := balancesNonnegative balance (by simp)
      have restNonnegative : ∀ current, current ∈ rest → 0 ≤ current := by
        intro current member
        exact balancesNonnegative current (by simp [member])
      have tail := ih restNonnegative
      simp [totalRatStock]
      exact Rat.add_nonneg balanceNonnegative tail

/-- Expected total stock under a finite joint lottery over rational balance
    profiles. -/
def expectedRatStock (outcomes : List (List Rat × Rat)) : Rat :=
  outcomes.foldr
    (fun outcome total => outcome.2 * totalRatStock outcome.1 + total) 0

/-- Weighted requirement cost of an event under a finite outcome list. -/
def weightedEventRequirement {Outcome : Type}
    (outcomes : List (Outcome × Rat)) (event : Outcome → Bool) (amount : Rat) : Rat :=
  outcomes.foldr
    (fun outcome total =>
      if event outcome.1 then outcome.2 * amount + total else total) 0

theorem weightedEventRequirement_eq_amount_mul_eventFold
    {Outcome : Type} (outcomes : List (Outcome × Rat))
    (event : Outcome → Bool) (amount : Rat) :
    weightedEventRequirement outcomes event amount =
      amount * eventFold outcomes event := by
  induction outcomes with
  | nil => simp [weightedEventRequirement, eventFold]
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      change (if event value then
          weight * amount + weightedEventRequirement rest event amount
        else weightedEventRequirement rest event amount) =
        amount * (if event value then weight + eventFold rest event
          else eventFold rest event)
      cases eventValue : event value
      · exact ih
      · simp only [↓reduceIte]
        rw [ih, Rat.mul_add, Rat.mul_comm weight amount]

theorem viableRatLoad_eq_count_mul_reserve
    (reserve : Rat) (balances : List Rat) :
    viableRatLoad reserve balances =
      (viableRatCount reserve balances : Rat) * reserve := by
  induction balances with
  | nil => simp [viableRatLoad, viableRatCount]
  | cons balance rest ih =>
      by_cases meets : reserve ≤ balance
      · have countEq : viableRatCount reserve (balance :: rest) =
            viableRatCount reserve rest + 1 := by
          simp [viableRatCount, meets]
        simp only [viableRatLoad, if_pos meets]
        rw [ih, countEq]
        rw [Rat.natCast_add, Rat.add_mul]
        simp only [Rat.natCast_ofNat, Rat.one_mul]
        exact Rat.add_comm reserve
          ((viableRatCount reserve rest : Rat) * reserve)
      · have countEq : viableRatCount reserve (balance :: rest) =
            viableRatCount reserve rest := by
          simp [viableRatCount, meets]
        simp only [viableRatLoad, if_neg meets]
        rw [ih, countEq]

/-- The reserve assigned to viable accounts cannot exceed total stock. This
    holds with heterogeneous balances and fractional resource units. -/
theorem viableRatLoad_le_totalStock
    (reserve : Rat) (balances : List Rat)
    (balancesNonnegative : ∀ balance, balance ∈ balances → 0 ≤ balance) :
    viableRatLoad reserve balances ≤ totalRatStock balances := by
  induction balances with
  | nil => simp [viableRatLoad, totalRatStock]
  | cons balance rest ih =>
      have balanceNonnegative : 0 ≤ balance := balancesNonnegative balance (by simp)
      have restNonnegative : ∀ current, current ∈ rest → 0 ≤ current := by
        intro current member
        exact balancesNonnegative current (by simp [member])
      have tail := ih restNonnegative
      by_cases meets : reserve ≤ balance
      · simp [viableRatLoad, totalRatStock, meets]
        calc
          reserve + viableRatLoad reserve rest ≤ balance + viableRatLoad reserve rest :=
            Rat.add_le_add_right.mpr meets
          _ ≤ balance + totalRatStock rest := Rat.add_le_add_left.mpr tail
      · simp [viableRatLoad, totalRatStock, meets]
        calc
          viableRatLoad reserve rest ≤ totalRatStock rest := tail
          _ = 0 + totalRatStock rest := (Rat.zero_add _).symm
          _ ≤ balance + totalRatStock rest := by
            exact Rat.add_le_add_right.mpr balanceNonnegative

/-- Expected resource cost of attaining `target` viable accounts is bounded
    by expected total stock. The event may have any correlation with balances
    and with other agents' outcomes. -/
theorem expectedViabilityRequirement_le_expectedStock_aux
    (reserve target : Rat) (outcomes : List (List Rat × Rat))
    (reserveNonnegative : 0 ≤ reserve)
    (balancesNonnegative : ∀ balances weight, (balances, weight) ∈ outcomes →
      ∀ balance, balance ∈ balances → 0 ≤ balance)
    (weightsNonnegative : ∀ balances weight, (balances, weight) ∈ outcomes →
      0 ≤ weight) :
    weightedEventRequirement outcomes
      (fun balances => decide (target ≤ (viableRatCount reserve balances : Rat)))
      (target * reserve) ≤ expectedRatStock outcomes := by
  induction outcomes with
  | nil => simp [weightedEventRequirement, expectedRatStock]
  | cons head rest ih =>
      rcases head with ⟨balances, weight⟩
      have headWeight : 0 ≤ weight := weightsNonnegative balances weight (by simp)
      have headBalancesNonnegative : ∀ balance, balance ∈ balances → 0 ≤ balance :=
        balancesNonnegative balances weight (by simp)
      have restWeights : ∀ current currentWeight, (current, currentWeight) ∈ rest →
          0 ≤ currentWeight := by
        intro current currentWeight member
        exact weightsNonnegative current currentWeight (by simp [member])
      have restBalancesNonnegative : ∀ current currentWeight,
          (current, currentWeight) ∈ rest →
            ∀ balance, balance ∈ current → 0 ≤ balance := by
        intro current currentWeight member balance balanceMember
        exact balancesNonnegative current currentWeight (by simp [member]) balance balanceMember
      have tail := ih restBalancesNonnegative restWeights
      change (if decide (target ≤ (viableRatCount reserve balances : Rat)) then
          weight * (target * reserve) +
            weightedEventRequirement rest
              (fun current => decide (target ≤ (viableRatCount reserve current : Rat)))
              (target * reserve)
        else
          weightedEventRequirement rest
            (fun current => decide (target ≤ (viableRatCount reserve current : Rat)))
            (target * reserve)) ≤
        weight * totalRatStock balances + expectedRatStock rest
      by_cases enough : target ≤ (viableRatCount reserve balances : Rat)
      ·
        have decisionTrue : decide (target ≤ (viableRatCount reserve balances : Rat)) = true :=
          decide_eq_true enough
        simp only [decisionTrue, ↓reduceIte]
        have loadEq := viableRatLoad_eq_count_mul_reserve reserve balances
        have countCost : target * reserve ≤ viableRatLoad reserve balances := by
          calc
            target * reserve ≤
                (viableRatCount reserve balances : Rat) * reserve :=
                  Rat.mul_le_mul_of_nonneg_right enough reserveNonnegative
            _ = viableRatLoad reserve balances := loadEq.symm
        have loadBound := viableRatLoad_le_totalStock reserve balances
          headBalancesNonnegative
        have costBound := Rat.le_trans countCost loadBound
        have headBound : weight * (target * reserve) ≤
            weight * totalRatStock balances :=
          Rat.mul_le_mul_of_nonneg_left costBound headWeight
        calc
          weight * (target * reserve) +
              weightedEventRequirement rest
                (fun current => decide (target ≤ (viableRatCount reserve current : Rat)))
                (target * reserve) ≤
            weight * totalRatStock balances +
              weightedEventRequirement rest
                (fun current => decide (target ≤ (viableRatCount reserve current : Rat)))
                (target * reserve) := Rat.add_le_add_right.mpr headBound
          _ ≤ weight * totalRatStock balances + expectedRatStock rest :=
            Rat.add_le_add_left.mpr tail
      · have decisionFalse : decide (target ≤ (viableRatCount reserve balances : Rat)) = false :=
          decide_eq_false enough
        simp only [decisionFalse]
        have stockNonnegative := totalRatStock_nonnegative balances headBalancesNonnegative
        have headStockNonnegative : 0 ≤ weight * totalRatStock balances :=
          Rat.mul_nonneg headWeight stockNonnegative
        calc
          weightedEventRequirement rest
              (fun current => decide (target ≤ (viableRatCount reserve current : Rat)))
              (target * reserve) ≤ expectedRatStock rest := tail
          _ ≤ weight * totalRatStock balances + expectedRatStock rest := by
            have h : 0 + expectedRatStock rest ≤
                weight * totalRatStock balances + expectedRatStock rest :=
              Rat.add_le_add_right.mpr headStockNonnegative
            simpa only [Rat.zero_add] using h

/-- **Stochastic viability resource bound.** For any finite joint lottery over
    nonnegative rational balance profiles, `k` accounts each requiring `d`
    units can be simultaneously viable with probability at most
    `E[total stock] / (k*d)`. The division-free statement is
    `k*d · P(N_viable ≥ k) ≤ E[stock]`.

    No independence, anonymity, fixed success count, or response rule is
    assumed. It is a sharp feasibility ceiling, not a claim that a particular
    mechanism attains the bound. The nonnegative-balance and common-reserve
    conditions are explicit and directly auditable in a case. -/
theorem probability_at_least_target_viable_bounded_by_expected_stock
    (reserve target : Rat) (lottery : FiniteDistribution (List Rat))
    (reserveNonnegative : 0 ≤ reserve)
    (balancesNonnegative : ∀ balances weight, (balances, weight) ∈ lottery.outcomes →
      ∀ balance, balance ∈ balances → 0 ≤ balance) :
    (target * reserve) *
        eventMass lottery
          (fun balances => decide (target ≤ (viableRatCount reserve balances : Rat))) ≤
      expectedRatStock lottery.outcomes := by
  change (target * reserve) *
      eventFold lottery.outcomes
        (fun balances => decide (target ≤ (viableRatCount reserve balances : Rat))) ≤
    expectedRatStock lottery.outcomes
  rw [← weightedEventRequirement_eq_amount_mul_eventFold]
  exact expectedViabilityRequirement_le_expectedStock_aux reserve target
    lottery.outcomes reserveNonnegative balancesNonnegative lottery.nonnegative

theorem sum_replicate_rat_eq_count_mul_value (count : Nat) (value : Rat) :
    (List.replicate count value).sum = (count : Rat) * value := by
  induction count with
  | zero => simp
  | succ count ih =>
      simp only [List.replicate_succ, List.sum_cons]
      rw [ih, Rat.natCast_add]
      simp only [Rat.natCast_ofNat, Rat.add_mul, Rat.one_mul]
      exact Rat.add_comm value ((count : Rat) * value)

/-- The stochastic bound is sharp: a deterministic state with exactly `k`
    accounts each holding the common reserve attains equality. This is a
    feasibility witness, not a choice or equilibrium prediction. -/
theorem rational_resource_survival_bound_is_sharp
    (reserve : Rat) (target : Nat) :
    let lottery : FiniteDistribution (List Rat) :=
      pureDistribution (List.replicate target reserve)
    ((target : Rat) * reserve) *
        eventMass lottery
          (fun balances => decide ((target : Rat) ≤ (viableRatCount reserve balances : Rat))) =
      expectedRatStock lottery.outcomes := by
  simp [pureDistribution, eventMass, expectedRatStock, totalRatStock,
    viableRatCount, sum_replicate_rat_eq_count_mul_value]
  <;> simp [Rat.add_zero, Rat.mul_one]

end AgentMicrofoundations.ResourceSurvivalBound
