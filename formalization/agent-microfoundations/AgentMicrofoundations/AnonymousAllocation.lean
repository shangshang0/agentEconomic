import AgentMicrofoundations.Ontology
import AgentMicrofoundations.ResponseIdentification

/-!
Anonymity turns a finite-population accounting identity into an individual
exposure prediction. The result is conditional on an exactly-sized allocation
lottery and equal marginal treatment of population labels. It assumes neither
agent rationality nor independence, and does not claim that a discretionary
allocator is anonymous.
-/
namespace AgentMicrofoundations.AnonymousAllocation

open AgentMicrofoundations.Ontology

/-- A realized allocation marks which agents receive an opportunity. -/
abbrev Allocation (Agent : Type) := Agent → Bool

/-- A finite population is an explicit, duplicate-free list of persistent
    agent identities. -/
structure FinitePopulation (Agent : Type) where
  members : List Agent
  noDuplicates : members.Nodup

/-- `List.any` depends only on values taken by its predicate on the listed
    members. -/
theorem any_congr_on_members {Agent : Type} (members : List Agent)
    (first second : Agent → Bool)
    (sameOnMembers : ∀ agent, agent ∈ members → first agent = second agent) :
    members.any first = members.any second := by
  induction members with
  | nil => rfl
  | cons agent rest ih =>
      have headEqual := sameOnMembers agent (by simp)
      have tailEqual : ∀ current, current ∈ rest → first current = second current := by
        intro current member
        exact sameOnMembers current (by simp [member])
      simp [headEqual, ih tailEqual]

/-- Number of selected agents inside an explicitly listed population. -/
def selectedCount {Agent : Type} (population : List Agent)
    (allocation : Allocation Agent) : Nat :=
  (population.filter allocation).length

/-- Unnormalized marginal probability mass that an agent is selected in a
    finite allocation lottery. For a `FiniteDistribution`, this is a
    probability because the distribution has total mass one. -/
def selectionMass {Agent : Type} (outcomes : List (Allocation Agent × Rat))
    (agent : Agent) : Rat :=
  outcomes.foldr
    (fun outcome total => if outcome.1 agent then outcome.2 + total else total) 0

/-- Unnormalized expected number selected from a finite population. -/
def expectedSelectionMass {Agent : Type}
    (population : List Agent) (outcomes : List (Allocation Agent × Rat)) : Rat :=
  outcomes.foldr
    (fun outcome total =>
      outcome.2 * (selectedCount population outcome.1 : Rat) + total) 0

/-- Expected selected count when outcomes are mapped to allocation profiles.
    Keeping the outcome type separate lets us state bounds for joint events
    (such as assignment together with production) without factorizing them. -/
def expectedProfileCount {Agent α : Type} (population : List Agent)
    (profile : α → Allocation Agent) (outcomes : List (α × Rat)) : Rat :=
  outcomes.foldr
    (fun outcome total =>
      outcome.2 * (selectedCount population (profile outcome.1) : Rat) + total) 0

theorem expectedSelectionMass_mapEntries {Agent α : Type}
    (population : List Agent) (profile : α → Allocation Agent)
    (outcomes : List (α × Rat)) :
    expectedSelectionMass population (mapEntries profile outcomes) =
      expectedProfileCount population profile outcomes := by
  induction outcomes with
  | nil => rfl
  | cons outcome rest ih =>
      rcases outcome with ⟨value, weight⟩
      change weight * (selectedCount population (profile value) : Rat) +
          expectedSelectionMass population (mapEntries profile rest) =
        weight * (selectedCount population (profile value) : Rat) +
          expectedProfileCount population profile rest
      rw [ih]

/-- Expected counts preserve pointwise inclusion under any finite lottery with
    nonnegative weights. This is a pure accounting result: it places no
    behavioral or independence restriction on the outcome law. -/
theorem expectedProfileCount_mono
    {Agent α : Type} (population : List Agent)
    (smallProfile largeProfile : α → Allocation Agent)
    (outcomes : List (α × Rat))
    (weightsNonnegative : ∀ value weight, (value, weight) ∈ outcomes → 0 ≤ weight)
    (pointwiseInclusion : ∀ value,
      selectedCount population (smallProfile value) ≤
        selectedCount population (largeProfile value)) :
    expectedProfileCount population smallProfile outcomes ≤
      expectedProfileCount population largeProfile outcomes := by
  induction outcomes with
  | nil => simp [expectedProfileCount]
  | cons outcome rest ih =>
      rcases outcome with ⟨value, weight⟩
      have headBound :
          weight * (selectedCount population (smallProfile value) : Rat) ≤
            weight * (selectedCount population (largeProfile value) : Rat) :=
        Rat.mul_le_mul_of_nonneg_left
          (Rat.natCast_le_natCast.mpr (pointwiseInclusion value))
          (weightsNonnegative value weight (by simp))
      have restNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restBound := ih restNonnegative
      simp only [expectedProfileCount, List.foldr_cons]
      calc
        weight * (selectedCount population (smallProfile value) : Rat) +
            expectedProfileCount population smallProfile rest ≤
          weight * (selectedCount population (largeProfile value) : Rat) +
            expectedProfileCount population smallProfile rest :=
              Rat.add_le_add_right.mpr headBound
        _ ≤ weight * (selectedCount population (largeProfile value) : Rat) +
            expectedProfileCount population largeProfile rest :=
              Rat.add_le_add_left.mpr restBound

/-- Intersecting an allocation with a success indicator can only reduce the
    number of selected agents. -/
theorem selectedCount_intersection_le {Agent : Type}
    (population : List Agent) (allocation success : Allocation Agent) :
    selectedCount population (fun agent => allocation agent && success agent) ≤
      selectedCount population allocation := by
  induction population with
  | nil => simp [selectedCount]
  | cons agent rest ih =>
      cases assigned : allocation agent <;> cases succeeded : success agent
      · simpa [selectedCount, assigned, succeeded] using ih
      · simpa [selectedCount, assigned, succeeded] using ih
      · simp [selectedCount, assigned, succeeded]
        have ih' :
            (List.filter (fun current => allocation current && success current) rest).length ≤
              (List.filter allocation rest).length := by
          simpa [selectedCount] using ih
        omega
      · simpa [selectedCount, assigned, succeeded] using ih

def ratSumOver {Agent : Type} (population : List Agent)
    (value : Agent → Rat) : Rat :=
  population.foldr (fun agent total => value agent + total) 0

theorem ratSumOver_zero {Agent : Type} (population : List Agent) :
    ratSumOver population (fun _ => 0) = 0 := by
  induction population with
  | nil => rfl
  | cons agent rest ih =>
      change 0 + ratSumOver rest (fun _ => 0) = 0
      rw [ih]
      exact Rat.zero_add _

theorem ratSumOver_congr {Agent : Type} (population : List Agent)
    (left right : Agent → Rat)
    (sameOnPopulation : ∀ agent, agent ∈ population → left agent = right agent) :
    ratSumOver population left = ratSumOver population right := by
  induction population with
  | nil => rfl
  | cons agent rest ih =>
      change left agent + ratSumOver rest left = right agent + ratSumOver rest right
      have headEqual := sameOnPopulation agent (by simp)
      have tailEqual : ∀ current, current ∈ rest → left current = right current := by
        intro current member
        exact sameOnPopulation current (by simp [member])
      rw [headEqual, ih tailEqual]

/-- Pointwise inequalities remain valid after summing over a finite list. -/
theorem ratSumOver_mono {Agent : Type} (population : List Agent)
    (lower upper : Agent → Rat)
    (pointwise : ∀ agent, agent ∈ population → lower agent ≤ upper agent) :
    ratSumOver population lower ≤ ratSumOver population upper := by
  induction population with
  | nil => simp [ratSumOver]
  | cons agent rest ih =>
      have headBound := pointwise agent (by simp)
      have tailBound : ∀ current, current ∈ rest → lower current ≤ upper current := by
        intro current member
        exact pointwise current (by simp [member])
      have restBound := ih tailBound
      change lower agent + ratSumOver rest lower ≤
        upper agent + ratSumOver rest upper
      calc
        lower agent + ratSumOver rest lower ≤
            upper agent + ratSumOver rest lower :=
              Rat.add_le_add_right.mpr headBound
        _ ≤ upper agent + ratSumOver rest upper :=
              Rat.add_le_add_left.mpr restBound

/-- Summing a unit weight once per listed member gives the population size. -/
theorem ratSumOver_one_eq_length {Agent : Type} (population : List Agent) :
    ratSumOver population (fun _ => 1) = (population.length : Rat) := by
  induction population with
  | nil => rfl
  | cons agent rest ih =>
      change 1 + ratSumOver rest (fun _ => 1) = ((rest.length + 1 : Nat) : Rat)
      rw [ih, Rat.natCast_add]
      simp [Rat.add_comm]

theorem ratSumOver_add {Agent : Type} (population : List Agent)
    (left right : Agent → Rat) :
    ratSumOver population (fun agent => left agent + right agent) =
      ratSumOver population left + ratSumOver population right := by
  induction population with
  | nil => exact (Rat.zero_add 0).symm
  | cons agent rest ih =>
      change left agent + right agent +
          ratSumOver rest (fun current => left current + right current) =
        (left agent + ratSumOver rest left) +
          (right agent + ratSumOver rest right)
      rw [ih]
      calc
        (left agent + right agent) +
            (ratSumOver rest left + ratSumOver rest right) =
          left agent + (right agent +
            (ratSumOver rest left + ratSumOver rest right)) := Rat.add_assoc _ _ _
        _ = left agent + (ratSumOver rest left +
            (right agent + ratSumOver rest right)) := by
              congr 1
              calc
                right agent + (ratSumOver rest left + ratSumOver rest right) =
                    (right agent + ratSumOver rest left) + ratSumOver rest right :=
                      (Rat.add_assoc _ _ _).symm
                _ = (ratSumOver rest left + right agent) + ratSumOver rest right := by
                      rw [Rat.add_comm (right agent) (ratSumOver rest left)]
                _ = ratSumOver rest left +
                    (right agent + ratSumOver rest right) := Rat.add_assoc _ _ _
        _ = (left agent + ratSumOver rest left) +
            (right agent + ratSumOver rest right) := (Rat.add_assoc _ _ _).symm

theorem ratSumOver_indicator_eq_weighted_count
    {Agent : Type} (population : List Agent)
    (allocation : Allocation Agent) (weight : Rat) :
    ratSumOver population (fun agent => if allocation agent then weight else 0) =
      weight * (selectedCount population allocation : Rat) := by
  induction population with
  | nil => simp [ratSumOver, selectedCount]
  | cons agent rest ih =>
      cases selected : allocation agent
      · simp only [ratSumOver, List.foldr_cons, selected, selectedCount,
          List.filter_cons, Bool.false_eq_true, ↓reduceIte]
        simp only [Rat.zero_add]
        change ratSumOver rest (fun current => if allocation current then weight else 0) =
          weight * (selectedCount rest allocation : Rat)
        exact ih
      · simp only [ratSumOver, List.foldr_cons, selected, selectedCount,
          List.filter_cons, ↓reduceIte, List.length_cons]
        rw [Rat.natCast_add]
        simp only [Rat.natCast_ofNat]
        change weight + ratSumOver rest
            (fun current => if allocation current then weight else 0) =
          weight * ((selectedCount rest allocation : Rat) + 1)
        rw [ih]
        calc
          weight + weight * (selectedCount rest allocation : Rat) =
              weight * (selectedCount rest allocation : Rat) + weight :=
                Rat.add_comm _ _
          _ = weight * (selectedCount rest allocation : Rat) + weight * 1 := by simp
          _ = weight * ((selectedCount rest allocation : Rat) + 1) :=
                (Rat.mul_add _ _ _).symm

theorem expectedSelectionMass_eq_fixed_count_mul_mass
    {Agent : Type} (population : List Agent)
    (outcomes : List (Allocation Agent × Rat)) (assignments : Nat)
    (weightsNonnegative : ∀ allocation weight, (allocation, weight) ∈ outcomes →
      0 ≤ weight)
    (fixedCount : ∀ allocation weight, (allocation, weight) ∈ outcomes →
      0 < weight → selectedCount population allocation = assignments) :
    expectedSelectionMass population outcomes =
      (assignments : Rat) * mass outcomes := by
  induction outcomes with
  | nil => simp [expectedSelectionMass, mass]
  | cons outcome rest ih =>
      rcases outcome with ⟨allocation, weight⟩
      have headNonnegative := weightsNonnegative allocation weight (by simp)
      have headZeroOrCount : weight = 0 ∨
          selectedCount population allocation = assignments := by
        by_cases positive : 0 < weight
        · exact Or.inr (fixedCount allocation weight (by simp) positive)
        · left
          exact Rat.le_antisymm (Rat.not_lt.mp positive) headNonnegative
      have restNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restFixed : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 < candidateWeight →
            selectedCount population candidate = assignments := by
        intro candidate candidateWeight member positive
        exact fixedCount candidate candidateWeight (by simp [member]) positive
      have tailIdentity := ih restNonnegative restFixed
      rcases headZeroOrCount with headZero | headCount
      · simp only [expectedSelectionMass, List.foldr_cons, mass, headZero,
          Rat.zero_mul, Rat.zero_add]
        exact tailIdentity
      · simp only [expectedSelectionMass, List.foldr_cons, mass, headCount]
        change weight * (assignments : Rat) + expectedSelectionMass population rest =
          (assignments : Rat) * (weight + mass rest)
        rw [tailIdentity]
        calc
          weight * (assignments : Rat) +
              (assignments : Rat) * mass rest =
            (assignments : Rat) * weight +
              (assignments : Rat) * mass rest := by
                rw [Rat.mul_comm weight (assignments : Rat)]
          _ = (assignments : Rat) * (weight + mass rest) :=
                (Rat.mul_add _ _ _).symm

/-- Incidence identity: summing each agent's inclusion mass recovers the
    expected number assigned. This is true for arbitrary dependence between
    agents and arbitrary (including nonuniform) lottery weights. -/
theorem aggregate_selection_mass_eq_expected_count
    {Agent : Type} (population : List Agent)
    (outcomes : List (Allocation Agent × Rat)) :
    ratSumOver population (selectionMass outcomes) =
      expectedSelectionMass population outcomes := by
  induction outcomes with
  | nil =>
      change ratSumOver population (fun _ => 0) = 0
      exact ratSumOver_zero population
  | cons outcome rest ih =>
      rcases outcome with ⟨allocation, weight⟩
      calc
        ratSumOver population (selectionMass ((allocation, weight) :: rest)) =
            ratSumOver population (fun agent =>
              (if allocation agent then weight else 0) + selectionMass rest agent) := by
                apply ratSumOver_congr
                intro agent _
                cases selected : allocation agent <;>
                  simp [selectionMass, selected, Rat.zero_add]
        _ = ratSumOver population (fun agent => if allocation agent then weight else 0) +
              ratSumOver population (selectionMass rest) :=
                ratSumOver_add population _ _
        _ = weight * (selectedCount population allocation : Rat) +
              expectedSelectionMass population rest := by
                rw [ratSumOver_indicator_eq_weighted_count, ih]
        _ = expectedSelectionMass population ((allocation, weight) :: rest) := rfl

/-- Finite union bound for an allocation lottery: the probability that a
    nonempty group receives at least one opportunity is no greater than its
    expected recipient count. The derivation is outcome-wise and assumes no
    independence across agents. -/
theorem eventFold_any_selected_le_expected_count {Agent : Type}
    (population : List Agent) (outcomes : List (Allocation Agent × Rat))
    (weightsNonnegative : ∀ allocation weight, (allocation, weight) ∈ outcomes →
      0 ≤ weight) :
    AgentMicrofoundations.ResponseIdentification.eventFold outcomes
      (fun allocation => population.any allocation) ≤
      expectedSelectionMass population outcomes := by
  induction outcomes with
  | nil => simp [AgentMicrofoundations.ResponseIdentification.eventFold,
      expectedSelectionMass]
  | cons head rest ih =>
      rcases head with ⟨allocation, weight⟩
      have headNonnegative : 0 ≤ weight := weightsNonnegative allocation weight (by simp)
      have restNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have tailBound := ih restNonnegative
      change (if population.any allocation then
          weight + AgentMicrofoundations.ResponseIdentification.eventFold rest
            (fun profile => population.any profile) else
          AgentMicrofoundations.ResponseIdentification.eventFold rest
            (fun profile => population.any profile)) ≤
        weight * (selectedCount population allocation : Rat) +
          expectedSelectionMass population rest
      cases anySelected : population.any allocation with
      | false =>
          have headOutputNonnegative :
              0 ≤ weight * (selectedCount population allocation : Rat) :=
            Rat.mul_nonneg headNonnegative Rat.natCast_nonneg
          calc
            AgentMicrofoundations.ResponseIdentification.eventFold rest
                (fun profile => population.any profile) =
              0 + AgentMicrofoundations.ResponseIdentification.eventFold rest
                (fun profile => population.any profile) := by
                  exact (Rat.zero_add _).symm
            _ ≤ weight * (selectedCount population allocation : Rat) +
                AgentMicrofoundations.ResponseIdentification.eventFold rest
                  (fun profile => population.any profile) :=
                    Rat.add_le_add_right.mpr headOutputNonnegative
            _ ≤ weight * (selectedCount population allocation : Rat) +
                expectedSelectionMass population rest :=
                  Rat.add_le_add_left.mpr tailBound
      | true =>
          rcases List.any_eq_true.mp anySelected with ⟨agent, agentMember, agentSelected⟩
          have filteredMember : agent ∈ List.filter allocation population :=
            List.mem_filter.mpr ⟨agentMember, agentSelected⟩
          have positiveCount : 0 < selectedCount population allocation := by
            unfold selectedCount
            exact List.length_pos_iff.mpr (List.ne_nil_of_mem filteredMember)
          have countAtLeastOne :
              1 ≤ (selectedCount population allocation : Rat) :=
            Rat.natCast_le_natCast.mpr (Nat.succ_le_of_lt positiveCount)
          have headOutputBound : weight ≤
              weight * (selectedCount population allocation : Rat) := by
            calc
              weight = weight * 1 := by rw [Rat.mul_one]
              _ ≤ weight * (selectedCount population allocation : Rat) :=
                Rat.mul_le_mul_of_nonneg_left countAtLeastOne headNonnegative
          calc
            weight + AgentMicrofoundations.ResponseIdentification.eventFold rest
                (fun profile => population.any profile) ≤
              weight * (selectedCount population allocation : Rat) +
                AgentMicrofoundations.ResponseIdentification.eventFold rest
                  (fun profile => population.any profile) :=
                    Rat.add_le_add_right.mpr headOutputBound
            _ ≤ weight * (selectedCount population allocation : Rat) +
                expectedSelectionMass population rest :=
                  Rat.add_le_add_left.mpr tailBound

theorem probability_any_selected_le_expected_count {Agent : Type}
    (population : List Agent) (lottery : FiniteDistribution (Allocation Agent)) :
    eventMass lottery (fun allocation => population.any allocation) ≤
      expectedSelectionMass population lottery.outcomes := by
  simpa [eventMass, AgentMicrofoundations.ResponseIdentification.eventFold] using
    eventFold_any_selected_le_expected_count population lottery.outcomes lottery.nonnegative

/-- Every listed member's exposure is a lower bound on the probability that
    the group receives at least one opportunity. -/
theorem individual_selection_mass_le_probability_any_selected {Agent : Type}
    (population : FinitePopulation Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (agent : Agent) (member : agent ∈ population.members) :
    selectionMass lottery.outcomes agent ≤
      eventMass lottery (fun allocation => population.members.any allocation) := by
  have inclusion :=
    AgentMicrofoundations.ResponseIdentification.eventFold_mono_of_support_inclusion
      lottery.outcomes (fun allocation => allocation agent)
      (fun allocation => population.members.any allocation) lottery.nonnegative
      (by
        intro allocation weight _ _ selected
        exact List.any_eq_true.mpr ⟨agent, member, selected⟩)
  simpa [selectionMass, eventMass,
    AgentMicrofoundations.ResponseIdentification.eventFold] using inclusion

/-- Equal marginal treatment: every pair of listed agents has the same
    inclusion mass under the allocation lottery. This is the exact anonymity
    restriction needed for an individual exposure prediction; it is weaker
    than independence or uniform probability over complete allocations. -/
def EqualMarginalExposure {Agent : Type} (population : List Agent)
    (outcomes : List (Allocation Agent × Rat)) : Prop :=
  ∀ first, first ∈ population → ∀ second, second ∈ population →
    selectionMass outcomes first = selectionMass outcomes second

def swapAllocation {Agent : Type} [DecidableEq Agent]
    (first second : Agent) (allocation : Allocation Agent) : Allocation Agent :=
  fun agent =>
    if agent = first then allocation second
    else if agent = second then allocation first
    else allocation agent

def SwapInvariantLottery {Agent : Type} [DecidableEq Agent]
    (population : List Agent) (lottery : FiniteDistribution (Allocation Agent)) : Prop :=
  ∀ first, first ∈ population → ∀ second, second ∈ population →
    ∀ event : Allocation Agent → Bool,
      eventMass (mapDistribution (swapAllocation first second) lottery) event =
        eventMass lottery event

/-- Invariance of the complete allocation lottery under every pairwise label
    swap implies equal individual exposure probabilities. This is the formal
    route from an anonymous mechanism restriction to the marginal premise used
    in the `m/N` prediction. -/
theorem swap_invariant_lottery_implies_equal_marginal_exposure
    {Agent : Type} [DecidableEq Agent]
    (population : List Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (invariant : SwapInvariantLottery population lottery) :
    EqualMarginalExposure population lottery.outcomes := by
  intro first firstMember second secondMember
  have mappedProbability := eventMass_mapDistribution
    (swapAllocation first second) lottery (fun allocation => allocation first)
  have swapEvaluatesToSecond :
      (fun allocation => swapAllocation first second allocation first) =
        (fun allocation => allocation second) := by
    funext allocation
    simp [swapAllocation]
  rw [swapEvaluatesToSecond] at mappedProbability
  have invariantProbability := invariant first firstMember second secondMember
    (fun allocation => allocation first)
  have firstEqualsSecond :
      eventMass lottery (fun allocation => allocation first) =
        eventMass lottery (fun allocation => allocation second) := by
    calc
      eventMass lottery (fun allocation => allocation first) =
          eventMass (mapDistribution (swapAllocation first second) lottery)
            (fun allocation => allocation first) := invariantProbability.symm
      _ = eventMass lottery (fun allocation => allocation second) := mappedProbability
  simpa [eventMass, selectionMass] using firstEqualsSecond

theorem ratSumOver_eq_card_mul_reference_of_equal
    {Agent : Type} (population : List Agent) (value : Agent → Rat)
    (reference : Agent)
    (equalOnPopulation : ∀ agent, agent ∈ population → value agent = value reference) :
    ratSumOver population value = (population.length : Rat) * value reference := by
  have sumConstant : ∀ (agents : List Agent) (constant : Rat),
      (∀ agent, agent ∈ agents → value agent = constant) →
        ratSumOver agents value = (agents.length : Rat) * constant := by
    intro agents
    induction agents with
    | nil => intro constant _; simp [ratSumOver]
    | cons agent rest ih =>
        intro constant same
        have headEqual := same agent (by simp)
        have tailEqual : ∀ current, current ∈ rest → value current = constant := by
          intro current member
          exact same current (by simp [member])
        have tailSum := ih constant tailEqual
        change value agent + ratSumOver rest value =
          ((rest.length + 1 : Nat) : Rat) * constant
        rw [headEqual, tailSum, Rat.natCast_add]
        simp only [Rat.natCast_ofNat]
        calc
          constant + (rest.length : Rat) * constant =
              (rest.length : Rat) * constant + constant := Rat.add_comm _ _
          _ = ((rest.length : Rat) * constant) + 1 * constant := by simp
          _ = ((rest.length : Rat) + 1) * constant :=
                (Rat.add_mul _ _ _).symm
  have allEqual : ∀ agent, agent ∈ population → value agent = value reference :=
    equalOnPopulation
  exact sumConstant population (value reference) allEqual

/-- Under label-swap symmetry, an agent's inclusion probability equals the
    expected total number selected divided by population size. Unlike the
    fixed-capacity corollary, the number of assignments may vary across lottery
    outcomes. -/
theorem symmetric_lottery_exposure_eq_expected_count
    {Agent : Type} [DecidableEq Agent]
    (population : FinitePopulation Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (reference : Agent)
    (referencePresent : reference ∈ population.members)
    (swapInvariant : SwapInvariantLottery population.members lottery) :
    (population.members.length : Rat) * selectionMass lottery.outcomes reference =
      expectedSelectionMass population.members lottery.outcomes := by
  have equalReference : ∀ agent, agent ∈ population.members →
      selectionMass lottery.outcomes agent = selectionMass lottery.outcomes reference := by
    intro agent member
    have equalExposure := swap_invariant_lottery_implies_equal_marginal_exposure
      population.members lottery swapInvariant
    exact equalExposure agent member reference referencePresent
  calc
    (population.members.length : Rat) * selectionMass lottery.outcomes reference =
        ratSumOver population.members (selectionMass lottery.outcomes) := by
          symm
          exact ratSumOver_eq_card_mul_reference_of_equal population.members
            (selectionMass lottery.outcomes) reference equalReference
    _ = expectedSelectionMass population.members lottery.outcomes :=
          aggregate_selection_mass_eq_expected_count population.members lottery.outcomes

/-- If a lottery assigns exactly `m` distinct agents in every positive-mass
    outcome and its full event law is invariant under pairwise swaps of population
    labels, then every named member's assignment probability satisfies
    `N · p = m`. Pairwise swap invariance first implies equal marginal exposure;
    the incidence identity then fixes the marginal. No response rationality or
    cross-agent independence is used. Zero-mass rows impose no restriction. -/
theorem anonymous_fixed_assignments_imply_individual_exposure
    {Agent : Type} [DecidableEq Agent] (population : FinitePopulation Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (assignments : Nat) (reference : Agent)
    (referencePresent : reference ∈ population.members)
    (fixedCount : ∀ allocation weight,
      (allocation, weight) ∈ lottery.outcomes → 0 < weight →
        selectedCount population.members allocation = assignments)
    (swapInvariant : SwapInvariantLottery population.members lottery) :
    (population.members.length : Rat) * selectionMass lottery.outcomes reference =
      (assignments : Rat) := by
  calc
    (population.members.length : Rat) * selectionMass lottery.outcomes reference =
        expectedSelectionMass population.members lottery.outcomes :=
          symmetric_lottery_exposure_eq_expected_count population lottery reference
            referencePresent swapInvariant
    _ = (assignments : Rat) * mass lottery.outcomes :=
          expectedSelectionMass_eq_fixed_count_mul_mass population.members lottery.outcomes
            assignments lottery.nonnegative fixedCount
    _ = (assignments : Rat) := by
          rw [lottery.normalized, Rat.mul_one]

/-- Under the same anonymous fixed-size lottery on its positive support, expected exposure of any
    nonempty subgroup scales with subgroup size. This does not say which
    members receive opportunities in a realized round, and it allows arbitrary
    dependence among their assignment indicators. -/
theorem symmetric_lottery_group_exposure_scales_with_group_size
    {Agent : Type} [DecidableEq Agent]
    (population group : FinitePopulation Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (assignments : Nat) (populationReference groupReference : Agent)
    (populationReferencePresent : populationReference ∈ population.members)
    (groupReferencePresent : groupReference ∈ group.members)
    (groupWithinPopulation : ∀ agent, agent ∈ group.members → agent ∈ population.members)
    (fixedCount : ∀ allocation weight,
      (allocation, weight) ∈ lottery.outcomes → 0 < weight →
        selectedCount population.members allocation = assignments)
    (swapInvariant : SwapInvariantLottery population.members lottery) :
    (population.members.length : Rat) *
      expectedSelectionMass group.members lottery.outcomes =
        (group.members.length : Rat) * (assignments : Rat) := by
  have populationProbability := anonymous_fixed_assignments_imply_individual_exposure
    population lottery assignments populationReference populationReferencePresent
    fixedCount swapInvariant
  have groupEqual : ∀ agent, agent ∈ group.members →
      selectionMass lottery.outcomes agent =
        selectionMass lottery.outcomes groupReference := by
    intro agent member
    have equalExposure := swap_invariant_lottery_implies_equal_marginal_exposure
      population.members lottery swapInvariant
    exact equalExposure agent (groupWithinPopulation agent member)
      groupReference (groupWithinPopulation groupReference groupReferencePresent)
  have groupExpectation : expectedSelectionMass group.members lottery.outcomes =
      (group.members.length : Rat) * selectionMass lottery.outcomes groupReference := by
    calc
      expectedSelectionMass group.members lottery.outcomes =
          ratSumOver group.members (selectionMass lottery.outcomes) :=
            (aggregate_selection_mass_eq_expected_count group.members lottery.outcomes).symm
      _ = (group.members.length : Rat) * selectionMass lottery.outcomes groupReference :=
            ratSumOver_eq_card_mul_reference_of_equal group.members
              (selectionMass lottery.outcomes) groupReference groupEqual
  have populationReferenceProbability := swap_invariant_lottery_implies_equal_marginal_exposure
    population.members lottery swapInvariant groupReference
    (groupWithinPopulation groupReference groupReferencePresent)
    populationReference populationReferencePresent
  calc
    (population.members.length : Rat) *
        expectedSelectionMass group.members lottery.outcomes =
      (population.members.length : Rat) *
        ((group.members.length : Rat) * selectionMass lottery.outcomes groupReference) := by
          rw [groupExpectation]
    _ = (group.members.length : Rat) *
        ((population.members.length : Rat) * selectionMass lottery.outcomes groupReference) := by
          calc
            (population.members.length : Rat) *
                ((group.members.length : Rat) * selectionMass lottery.outcomes groupReference) =
              ((population.members.length : Rat) * (group.members.length : Rat)) *
                selectionMass lottery.outcomes groupReference :=
                  (Rat.mul_assoc _ _ _).symm
            _ = ((group.members.length : Rat) * (population.members.length : Rat)) *
                selectionMass lottery.outcomes groupReference := by
                  rw [Rat.mul_comm (population.members.length : Rat)
                    (group.members.length : Rat)]
            _ = (group.members.length : Rat) *
                ((population.members.length : Rat) *
                  selectionMass lottery.outcomes groupReference) := Rat.mul_assoc _ _ _
    _ = (group.members.length : Rat) * (assignments : Rat) := by
          rw [populationReferenceProbability, populationProbability]

end AgentMicrofoundations.AnonymousAllocation
