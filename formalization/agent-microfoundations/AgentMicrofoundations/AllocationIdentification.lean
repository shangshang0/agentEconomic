import Std

/-!
Sharp, assumption-light bounds on who can receive scarce opportunities.

Capacity identifies the number of assignments only when the mechanism fills
all feasible slots. Conditional on an observed assignment count `m`, group
exposure is bounded by the group's size and by the capacity outside it. These
bounds do not assume rationality, random selection, or independent choices.
-/
namespace AgentMicrofoundations.AllocationIdentification

/-- `q` assignments go to a group of `groupSize` agents. The remaining
    `m - q` assignments must fit outside the group. -/
def FeasibleGroupExposure (population groupSize assignments groupAssignments : Nat) : Prop :=
  groupSize ≤ population ∧
  assignments ≤ population ∧
  groupAssignments ≤ groupSize ∧
  groupAssignments ≤ assignments ∧
  assignments - groupAssignments ≤ population - groupSize

/-- Sharp finite-population bounds on the number of opportunities received by
    a group, conditional on exactly `assignments` distinct recipients. -/
theorem sharp_group_exposure_bounds
    (population groupSize assignments groupAssignments : Nat)
    (feasible : FeasibleGroupExposure population groupSize assignments groupAssignments) :
    max 0 (assignments - (population - groupSize)) ≤ groupAssignments ∧
      groupAssignments ≤ min assignments groupSize := by
  rcases feasible with ⟨groupWithin, assignmentsWithin, groupCap, assignmentCap, outsideCap⟩
  constructor
  · omega
  · exact Nat.le_min.mpr ⟨assignmentCap, groupCap⟩

/-- Both endpoints of the group-exposure interval are feasible: the bounds are
    sharp for the finite allocation constraints, not merely conservative. -/
theorem lower_group_exposure_bound_is_feasible
    (population groupSize assignments : Nat)
    (groupWithin : groupSize ≤ population)
    (assignmentsWithin : assignments ≤ population) :
    FeasibleGroupExposure population groupSize assignments
      (max 0 (assignments - (population - groupSize))) := by
  refine ⟨groupWithin, assignmentsWithin, ?_, ?_, ?_⟩ <;> omega

theorem upper_group_exposure_bound_is_feasible
    (population groupSize assignments : Nat)
    (groupWithin : groupSize ≤ population)
    (assignmentsWithin : assignments ≤ population) :
    FeasibleGroupExposure population groupSize assignments
      (min assignments groupSize) := by
  refine ⟨groupWithin, assignmentsWithin, ?_, ?_, ?_⟩ <;> omega

/-- Under strict scarcity, both zero and positive exposure for a named agent
    are feasible. Opportunity capacity alone cannot identify the recipient. -/
theorem individual_exposure_endpoints_unidentified_under_scarcity
    (population assignments : Nat)
    (populationAtLeastTwo : 2 ≤ population)
    (atLeastOne : 1 ≤ assignments)
    (strictScarcity : assignments < population) :
    FeasibleGroupExposure population 1 assignments 0 ∧
      FeasibleGroupExposure population 1 assignments 1 := by
  constructor
  · refine ⟨by omega, by omega, by omega, by omega, ?_⟩
    omega
  · refine ⟨by omega, by omega, by omega, by omega, ?_⟩
    omega

/-- Capacity upper bounds do not imply group exposure. If all realized
    assignments can fit among the agents outside a group, the group may receive
    zero even if the nominal capacity could have reached it. -/
theorem nominal_capacity_can_reach_group_but_actual_assignment_exposes_none
    (population groupSize capacity actualAssignments : Nat)
    (groupWithin : groupSize ≤ population)
    (actualWithinCapacity : actualAssignments ≤ capacity)
    (actualWithinPopulation : actualAssignments ≤ population)
    (outsideCanFillAll : actualAssignments ≤ population - groupSize)
    (capacityCanReachGroup : 0 < min capacity groupSize) :
    actualAssignments ≤ capacity ∧
      0 < min capacity groupSize ∧
      FeasibleGroupExposure population groupSize actualAssignments 0 := by
  refine ⟨actualWithinCapacity, capacityCanReachGroup,
    groupWithin, actualWithinPopulation, Nat.zero_le _, Nat.zero_le _, ?_⟩
  exact outsideCanFillAll

/-!
Finite stochastic outcomes. A list is an empirical lottery: repeated entries
carry repeated mass. The next result lifts the one-period sharp bounds to any
finite collection of realized allocations, without assuming how the outcomes
were sampled, whether agents are independent, or whether the allocator is
uniform. It is a support bound, not a probability model.
-/

def EveryWorldFeasible
    (population groupSize assignments : Nat) (worlds : List Nat) : Prop :=
  ∀ exposure, exposure ∈ worlds →
    FeasibleGroupExposure population groupSize assignments exposure

/-- Across any finite empirical lottery supported on feasible allocations,
    the average group exposure remains within the sharp per-world interval.
    No equal-probability assumption is needed beyond interpreting repeated
    rows as empirical mass. -/
theorem empirical_group_exposure_bounds
    (population groupSize assignments : Nat) (worlds : List Nat)
    (feasibleWorlds : EveryWorldFeasible population groupSize assignments worlds) :
    worlds.length * max 0 (assignments - (population - groupSize)) ≤ worlds.sum ∧
      worlds.sum ≤ worlds.length * min assignments groupSize := by
  induction worlds with
  | nil => simp
  | cons exposure rest ih =>
      have hExposure := feasibleWorlds exposure (by simp)
      have hRest : EveryWorldFeasible population groupSize assignments rest := by
        intro q hq
        exact feasibleWorlds q (by simp [hq])
      have hTail := ih hRest
      have hBounds := sharp_group_exposure_bounds population groupSize assignments exposure hExposure
      simp only [List.length_cons, List.sum_cons]
      constructor
      · calc
          (rest.length + 1) * max 0 (assignments - (population - groupSize)) =
              rest.length * max 0 (assignments - (population - groupSize)) +
                max 0 (assignments - (population - groupSize)) := by simp [Nat.add_mul]
          _ ≤ rest.sum + exposure := Nat.add_le_add hTail.1 hBounds.1
          _ = exposure + rest.sum := Nat.add_comm _ _
      · calc
          exposure + rest.sum ≤
              min assignments groupSize + rest.length * min assignments groupSize :=
            Nat.add_le_add hBounds.2 hTail.2
          _ = (rest.length + 1) * min assignments groupSize := by
            rw [Nat.add_mul, Nat.one_mul, Nat.add_comm]

/-- If every world assigns exactly `assignments` distinct opportunities, the
    population's total exposure over the finite trace is exactly the number of
    worlds times that assignment count. This fixes the population mean while
    leaving the identity-level distribution unrestricted. -/
theorem population_exposure_conservation
    (population assignments : Nat) (worlds : List Nat)
    (assignmentsWithinPopulation : assignments ≤ population)
    (feasibleWorlds : EveryWorldFeasible population population assignments worlds) :
    worlds.sum = worlds.length * assignments := by
  have h := empirical_group_exposure_bounds population population assignments worlds feasibleWorlds
  have hLower :
      worlds.length * max 0 (assignments - (population - population)) =
        worlds.length * assignments := by
    simp
  have hUpper :
      worlds.length * min assignments population = worlds.length * assignments := by
    rw [Nat.min_eq_left assignmentsWithinPopulation]
  omega

/-!
Weighted finite lotteries. The weight is unnormalized rational probability
mass; normalizing by `totalExposureMass` gives a finite rational lottery. This
representation permits nonuniform mechanisms and does not impose independence.
-/

def totalExposureMass : List (Nat × Nat) → Nat
  | [] => 0
  | (_, weight) :: rest => weight + totalExposureMass rest

def weightedExposureTotal : List (Nat × Nat) → Nat
  | [] => 0
  | (exposure, weight) :: rest => weight * exposure + weightedExposureTotal rest

def EveryWeightedWorldFeasible
    (population groupSize assignments : Nat) (lottery : List (Nat × Nat)) : Prop :=
  ∀ exposure weight, (exposure, weight) ∈ lottery →
    FeasibleGroupExposure population groupSize assignments exposure

/-- For every finite rational lottery supported on feasible allocations,
    expected group exposure is in the same sharp interval as one-period
    exposure. Weights need not be equal and outcomes need not be independent. -/
theorem weighted_group_exposure_bounds
    (population groupSize assignments : Nat) (lottery : List (Nat × Nat))
    (feasibleLottery :
      EveryWeightedWorldFeasible population groupSize assignments lottery) :
    totalExposureMass lottery * max 0 (assignments - (population - groupSize)) ≤
        weightedExposureTotal lottery ∧
      weightedExposureTotal lottery ≤
        totalExposureMass lottery * min assignments groupSize := by
  induction lottery with
  | nil => simp [totalExposureMass, weightedExposureTotal]
  | cons entry rest ih =>
      rcases entry with ⟨exposure, weight⟩
      have hExposure := feasibleLottery exposure weight (by simp)
      have hRest : EveryWeightedWorldFeasible population groupSize assignments rest := by
        intro q w hq
        exact feasibleLottery q w (by simp [hq])
      have hTail := ih hRest
      have hBounds := sharp_group_exposure_bounds population groupSize assignments exposure hExposure
      simp only [totalExposureMass, weightedExposureTotal]
      constructor
      · calc
          (weight + totalExposureMass rest) *
              max 0 (assignments - (population - groupSize)) =
              weight * max 0 (assignments - (population - groupSize)) +
                totalExposureMass rest * max 0 (assignments - (population - groupSize)) :=
            Nat.add_mul _ _ _
          _ ≤ weight * exposure + weightedExposureTotal rest :=
            Nat.add_le_add (Nat.mul_le_mul_left weight hBounds.1) hTail.1
      · calc
          weight * exposure + weightedExposureTotal rest ≤
              weight * min assignments groupSize +
                totalExposureMass rest * min assignments groupSize :=
            Nat.add_le_add (Nat.mul_le_mul_left weight hBounds.2) hTail.2
          _ = (weight + totalExposureMass rest) * min assignments groupSize :=
            (Nat.add_mul _ _ _).symm

/-- The weighted expectation lower bound is sharp: a unit-mass lottery can
    concentrate on a feasible lower-endpoint allocation. -/
theorem weighted_group_lower_expectation_is_sharp
    (population groupSize assignments : Nat)
    (groupWithin : groupSize ≤ population)
    (assignmentsWithin : assignments ≤ population) :
    ∃ lottery : List (Nat × Nat),
      totalExposureMass lottery = 1 ∧
      weightedExposureTotal lottery =
        max 0 (assignments - (population - groupSize)) ∧
      EveryWeightedWorldFeasible population groupSize assignments lottery := by
  let lower := max 0 (assignments - (population - groupSize))
  refine ⟨[(lower, 1)], ?_, ?_, ?_⟩
  · simp [totalExposureMass]
  · simp [weightedExposureTotal, lower]
  · intro exposure weight hmem
    simp only [List.mem_singleton] at hmem
    rcases hmem with ⟨rfl, rfl⟩
    exact lower_group_exposure_bound_is_feasible population groupSize assignments
      groupWithin assignmentsWithin

/-- The weighted expectation upper bound is sharp by concentrating all mass
    on a feasible upper-endpoint allocation. -/
theorem weighted_group_upper_expectation_is_sharp
    (population groupSize assignments : Nat)
    (groupWithin : groupSize ≤ population)
    (assignmentsWithin : assignments ≤ population) :
    ∃ lottery : List (Nat × Nat),
      totalExposureMass lottery = 1 ∧
      weightedExposureTotal lottery = min assignments groupSize ∧
      EveryWeightedWorldFeasible population groupSize assignments lottery := by
  let upper := min assignments groupSize
  refine ⟨[(upper, 1)], ?_, ?_, ?_⟩
  · simp [totalExposureMass]
  · simp [weightedExposureTotal, upper]
  · intro exposure weight hmem
    simp only [List.mem_singleton] at hmem
    rcases hmem with ⟨rfl, rfl⟩
    exact upper_group_exposure_bound_is_feasible population groupSize assignments
      groupWithin assignmentsWithin

end AgentMicrofoundations.AllocationIdentification
