import AgentMicrofoundations.AllocationFeedback

/-!
Composition of a resource-gated computational choice set with arbitrary
finite opportunity allocation, production, and next-period threshold response.
The result is a population-level feasibility forecast; it imposes no symmetry
or independence on the joint lottery.
-/
namespace AgentMicrofoundations.ResourceOpportunityCascade

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AnonymousAllocation
open AgentMicrofoundations.AllocationFeedback

/-- One realized round records proposal eligibility, assignment, verified
    production success, and the resulting threshold response. The proposal
    profile is the action event whose computational feasibility is governed by
    the token-budget threshold. -/
abbrev ChoiceAllocationProductionRound (Agent : Type) :=
  Allocation Agent × JointAllocationProduction Agent

def proposedProfile {Agent : Type}
    (round : ChoiceAllocationProductionRound Agent) : Allocation Agent :=
  round.1

def assignmentProfile {Agent : Type}
    (round : ChoiceAllocationProductionRound Agent) : Allocation Agent :=
  round.2.1

def nextActiveProfile {Agent : Type}
    (parameters : Agent → AgentThresholdResources)
    (round : ChoiceAllocationProductionRound Agent) : Allocation Agent :=
  fun agent => responseAfterHeterogeneousTask parameters round.2 agent

def productiveProfile {Agent : Type}
    (round : ChoiceAllocationProductionRound Agent) : Allocation Agent :=
  productiveRecipientProfile round.2

/-- Proposal, assignment, and production are ordered as executable events.
    Eligibility is an agent-specific resource-account condition derived from
    the minimum decision-prefix cost `tokenPrice * decisionPrefix agent`.
    This permits heterogeneous response protocols and action serialization
    lengths within the same population. Restrictions apply
    only to positive-mass support; zero-mass rows are irrelevant. -/
def RoundCausalOrder {Agent : Type}
    (group : FinitePopulation Agent)
    (lottery : FiniteDistribution (ChoiceAllocationProductionRound Agent))
    (spendableBalance decisionPrefix : Agent → Nat) (tokenPrice : Nat) : Prop :=
  ∀ round weight, (round, weight) ∈ lottery.outcomes → 0 < weight →
    (∀ agent, agent ∈ group.members →
      assignmentProfile round agent = true → proposedProfile round agent = true) ∧
    (∀ agent, agent ∈ group.members →
      proposedProfile round agent = true →
        tokenPrice * decisionPrefix agent ≤ spendableBalance agent)

theorem selectedCount_mono_of_profile_inclusion
    {Agent : Type} (population : List Agent)
    (smaller larger : Allocation Agent)
    (included : ∀ agent, agent ∈ population →
      smaller agent = true → larger agent = true) :
    selectedCount population smaller ≤ selectedCount population larger := by
  induction population with
  | nil => simp [selectedCount]
  | cons agent rest ih =>
      have tailIncluded : ∀ current, current ∈ rest →
          smaller current = true → larger current = true := by
        intro current member value
        exact included current (by simp [member]) value
      have tailBound := ih tailIncluded
      by_cases smallSelected : smaller agent = true
      · have largeSelected := included agent (by simp) smallSelected
        have tailCount := tailBound
        simp only [selectedCount] at tailCount ⊢
        simp only [List.filter_cons, smallSelected, largeSelected] at tailCount ⊢
        exact Nat.add_le_add_right tailCount 1
      · by_cases largeSelected : larger agent = true
        · have tailCount := tailBound
          simp only [selectedCount] at tailCount ⊢
          simp only [List.filter_cons, smallSelected, largeSelected] at tailCount ⊢
          exact Nat.le_trans tailCount (Nat.le_add_right _ _)
        · simp only [selectedCount, List.filter_cons, smallSelected, largeSelected]
          exact tailBound

/-- Expected profile counts preserve event inclusion on every positive-mass
    row. Zero-weight rows do not affect the forecast. -/
theorem expectedProfileCount_mono_on_support
    {Agent Outcome : Type} (population : List Agent)
    (smaller larger : Outcome → Allocation Agent)
    (outcomes : List (Outcome × Rat))
    (weightsNonnegative : ∀ value weight, (value, weight) ∈ outcomes → 0 ≤ weight)
    (supportInclusion : ∀ value weight, (value, weight) ∈ outcomes → 0 < weight →
      ∀ agent, agent ∈ population →
        smaller value agent = true → larger value agent = true) :
    expectedProfileCount population smaller outcomes ≤
      expectedProfileCount population larger outcomes := by
  induction outcomes with
  | nil => simp [expectedProfileCount]
  | cons outcome rest ih =>
      rcases outcome with ⟨value, weight⟩
      have headNonnegative : 0 ≤ weight := weightsNonnegative value weight (by simp)
      have restNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restInclusion : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 < candidateWeight →
          ∀ agent, agent ∈ population →
            smaller candidate agent = true → larger candidate agent = true := by
        intro candidate candidateWeight member positive agent inPopulation smallTrue
        exact supportInclusion candidate candidateWeight (by simp [member]) positive
          agent inPopulation smallTrue
      have tailBound := ih restNonnegative restInclusion
      by_cases weightZero : weight = 0
      · simpa [expectedProfileCount, weightZero, Rat.zero_add] using tailBound
      · have weightPositive : 0 < weight :=
          Rat.lt_of_le_of_ne headNonnegative (Ne.symm weightZero)
        have headInclusion : ∀ agent, agent ∈ population →
            smaller value agent = true → larger value agent = true := by
          intro agent inPopulation smallTrue
          exact supportInclusion value weight (by simp) weightPositive
            agent inPopulation smallTrue
        have countBound := selectedCount_mono_of_profile_inclusion population
          (smaller value) (larger value) headInclusion
        have weightedHeadBound :
            weight * (selectedCount population (smaller value) : Rat) ≤
              weight * (selectedCount population (larger value) : Rat) :=
          Rat.mul_le_mul_of_nonneg_left
            (Rat.natCast_le_natCast.mpr countBound) headNonnegative
        simp only [expectedProfileCount, List.foldr_cons]
        calc
          weight * (selectedCount population (smaller value) : Rat) +
              expectedProfileCount population smaller rest ≤
            weight * (selectedCount population (larger value) : Rat) +
              expectedProfileCount population smaller rest :=
                Rat.add_le_add_right.mpr weightedHeadBound
          _ ≤ weight * (selectedCount population (larger value) : Rat) +
              expectedProfileCount population larger rest :=
                Rat.add_le_add_left.mpr tailBound

theorem expectedProfileCount_constant
    {Agent Outcome : Type} (population : List Agent)
    (profile : Allocation Agent) (outcomes : List (Outcome × Rat)) :
    expectedProfileCount population (fun _ => profile) outcomes =
      mass outcomes * (selectedCount population profile : Rat) := by
  induction outcomes with
  | nil => simp [expectedProfileCount, mass]
  | cons outcome rest ih =>
      rcases outcome with ⟨value, weight⟩
      change weight * (selectedCount population profile : Rat) +
          expectedProfileCount population (fun _ => profile) rest =
        (weight + mass rest) * (selectedCount population profile : Rat)
      rw [ih, Rat.add_mul]

/-- **Resource–opportunity–production cascade.** For every finite subgroup,
    next-period active mass under an individual threshold response equals the
    expected successful-assignment count and is bounded successively by
    assigned opportunities, submitted proposals, and the number of members
    whose balances can fund the protocol's decision prefix.

    The allocation/production lottery may be asymmetric and arbitrarily
    dependent across agents. No anonymity, fixed number of assignments,
    independent production, or utility-maximizing choice is assumed. The
    restrictions are local and auditable: threshold-crossing margins,
    execution of assignments only after proposals, and the balance-derived
    proposal-feasibility threshold. No assumption about unrelated production
    events is needed because activity follows productive assignment, not
    production alone. -/
theorem resource_opportunity_production_cascade
    {Agent : Type}
    (group : FinitePopulation Agent)
    (lottery : FiniteDistribution (ChoiceAllocationProductionRound Agent))
    (parameters : Agent → AgentThresholdResources)
    (thresholdConditions : ∀ agent, agent ∈ group.members →
      ThresholdCrossing (parameters agent))
    (spendableBalance decisionPrefix : Agent → Nat) (tokenPrice : Nat)
    (causalOrder : RoundCausalOrder group lottery spendableBalance decisionPrefix tokenPrice) :
    expectedProfileCount group.members (nextActiveProfile parameters) lottery.outcomes =
        expectedProfileCount group.members productiveProfile lottery.outcomes ∧
      expectedProfileCount group.members (nextActiveProfile parameters) lottery.outcomes ≤
        expectedProfileCount group.members assignmentProfile lottery.outcomes ∧
      expectedProfileCount group.members assignmentProfile lottery.outcomes ≤
        expectedProfileCount group.members proposedProfile lottery.outcomes ∧
      expectedProfileCount group.members proposedProfile lottery.outcomes ≤
        (selectedCount group.members
          (fun agent => decide
            (tokenPrice * decisionPrefix agent ≤ spendableBalance agent)) : Rat) := by
  unfold RoundCausalOrder at causalOrder
  have assignmentRequiresProposal : ∀ round weight,
      (round, weight) ∈ lottery.outcomes → 0 < weight →
      ∀ agent, agent ∈ group.members →
        assignmentProfile round agent = true → proposedProfile round agent = true := by
    intro round weight member positive
    exact (causalOrder round weight member positive).1
  have proposalRequiresFunds : ∀ round weight,
      (round, weight) ∈ lottery.outcomes → 0 < weight →
      ∀ agent, agent ∈ group.members →
        proposedProfile round agent = true →
          tokenPrice * decisionPrefix agent ≤ spendableBalance agent := by
    intro round weight member positive
    exact (causalOrder round weight member positive).2
  have activeLeAssignment := expectedProfileCount_mono_on_support group.members
    (nextActiveProfile parameters) assignmentProfile lottery.outcomes lottery.nonnegative
    (by
      intro round weight member positive agent inGroup active
      change responseAfterHeterogeneousTask parameters round.2 agent = true at active
      have responseEq := congrFun
        (heterogeneous_threshold_response_matches_productive_recipient parameters agent
          (thresholdConditions agent inGroup)) round.2
      rw [responseEq] at active
      change productiveRecipientProfile round.2 agent = true at active
      have both : assignmentProfile round agent = true ∧ round.2.2 agent = true := by
        simpa [productiveRecipientProfile, assignmentProfile] using active
      exact both.1)
  have activeProductiveUpper := expectedProfileCount_mono_on_support group.members
    (nextActiveProfile parameters) productiveProfile lottery.outcomes lottery.nonnegative
    (by
      intro round weight member positive agent inGroup active
      change responseAfterHeterogeneousTask parameters round.2 agent = true at active
      have responseEq := congrFun
        (heterogeneous_threshold_response_matches_productive_recipient parameters agent
          (thresholdConditions agent inGroup)) round.2
      rw [responseEq] at active
      change productiveRecipientProfile round.2 agent = true at active
      exact active)
  have productiveActiveUpper := expectedProfileCount_mono_on_support group.members
    productiveProfile (nextActiveProfile parameters) lottery.outcomes lottery.nonnegative
    (by
      intro round weight member positive agent inGroup productive
      change productiveRecipientProfile round.2 agent = true at productive
      have responseEq := congrFun
        (heterogeneous_threshold_response_matches_productive_recipient parameters agent
          (thresholdConditions agent inGroup)) round.2
      change responseAfterHeterogeneousTask parameters round.2 agent = true
      rw [responseEq]
      exact productive)
  have activeProductiveEq :
      expectedProfileCount group.members (nextActiveProfile parameters) lottery.outcomes =
        expectedProfileCount group.members productiveProfile lottery.outcomes :=
    Rat.le_antisymm activeProductiveUpper productiveActiveUpper
  have assignmentLeProposal := expectedProfileCount_mono_on_support group.members
    assignmentProfile proposedProfile lottery.outcomes lottery.nonnegative
    (by
      intro round weight member positive agent inGroup assigned
      exact assignmentRequiresProposal round weight member positive agent inGroup assigned)
  let eligible : Allocation Agent :=
    fun agent => decide (tokenPrice * decisionPrefix agent ≤ spendableBalance agent)
  have proposalLeEligible := expectedProfileCount_mono_on_support group.members
    proposedProfile (fun _ => eligible) lottery.outcomes lottery.nonnegative
    (by
      intro round weight member positive agent inGroup proposed
      unfold eligible
      simpa using proposalRequiresFunds round weight member positive agent inGroup proposed)
  have eligibleExpectation :
      expectedProfileCount group.members (fun _ => eligible) lottery.outcomes =
        (selectedCount group.members eligible : Rat) := by
    rw [expectedProfileCount_constant, lottery.normalized, Rat.one_mul]
  refine ⟨?_, activeLeAssignment, assignmentLeProposal, ?_⟩
  · exact activeProductiveEq
  · rw [eligibleExpectation] at proposalLeEligible
    exact proposalLeEligible

end AgentMicrofoundations.ResourceOpportunityCascade
