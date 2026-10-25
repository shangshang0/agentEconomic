import AgentMicrofoundations.AnonymousAllocation
import AgentMicrofoundations.Specialization

/-!
Opportunity-induced role differentiation.

Exclusive, partially filled opportunity allocation creates heterogeneous
exposure even when agents start with the same response rule. If exposure is
encoded in the next context, and the two resulting context regions are
forward-invariant regions on which the same fixed response rule selects
different roles, then every realized allocation produces a persistent
population role split. The result is conditional: it does not derive the
context update or response rule from autoregressive architecture.
-/
namespace AgentMicrofoundations.OpportunitySpecialization

open AgentMicrofoundations.AnonymousAllocation
open AgentMicrofoundations.Ontology
open AgentMicrofoundations.Specialization

theorem eventFold_eq_mass_of_positive_support
    {Outcome : Type} (outcomes : List (Outcome × Rat)) (event : Outcome → Bool)
    (weightsNonnegative : ∀ value weight, (value, weight) ∈ outcomes → 0 ≤ weight)
    (eventOnPositiveSupport : ∀ value weight,
      (value, weight) ∈ outcomes → 0 < weight → event value = true) :
    AgentMicrofoundations.ResponseIdentification.eventFold outcomes event =
      mass outcomes := by
  induction outcomes with
  | nil => rfl
  | cons entry rest ih =>
      rcases entry with ⟨value, weight⟩
      have headNonnegative := weightsNonnegative value weight (by simp)
      have tailNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have tailEvent : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 < candidateWeight →
            event candidate = true := by
        intro candidate candidateWeight member positive
        exact eventOnPositiveSupport candidate candidateWeight (by simp [member]) positive
      have tailIdentity := ih tailNonnegative tailEvent
      cases headEvent : event value with
      | false =>
          have headWeightZero : weight = 0 := by
            apply Rat.le_antisymm
            · apply Rat.not_lt.mp
              intro positive
              have mustBeTrue := eventOnPositiveSupport value weight (by simp) positive
              simp [headEvent] at mustBeTrue
            · exact headNonnegative
          simp only [AgentMicrofoundations.ResponseIdentification.eventFold,
            List.foldr_cons, mass, headEvent, Bool.false_eq_true, ↓reduceIte]
          rw [headWeightZero, Rat.zero_add]
          change AgentMicrofoundations.ResponseIdentification.eventFold rest event = mass rest
          exact tailIdentity
      | true =>
          simp only [AgentMicrofoundations.ResponseIdentification.eventFold,
            List.foldr_cons, mass, headEvent, ↓reduceIte]
          change weight + AgentMicrofoundations.ResponseIdentification.eventFold rest event =
            weight + mass rest
          rw [tailIdentity]

theorem eventMass_eq_one_when_event_holds_on_positive_support
    {Outcome : Type} (lottery : FiniteDistribution Outcome) (event : Outcome → Bool)
    (eventOnPositiveSupport : ∀ value weight,
      (value, weight) ∈ lottery.outcomes → 0 < weight → event value = true) :
    eventMass lottery event = 1 := by
  change AgentMicrofoundations.ResponseIdentification.eventFold lottery.outcomes event = 1
  rw [eventFold_eq_mass_of_positive_support lottery.outcomes event
    lottery.nonnegative eventOnPositiveSupport]
  exact lottery.normalized

theorem positive_selected_count_has_selected_witness
    {Agent : Type} (population : List Agent) (allocation : Allocation Agent)
    (positive : 0 < selectedCount population allocation) :
    ∃ agent, agent ∈ population ∧ allocation agent = true := by
  unfold selectedCount at positive
  have nonempty : (List.filter allocation population).length > 0 := positive
  obtain ⟨agent, member⟩ := List.exists_mem_of_length_pos nonempty
  rcases List.mem_filter.mp member with ⟨member, assigned⟩
  exact ⟨_, member, assigned⟩

theorem selected_count_below_population_has_unselected_witness
    {Agent : Type} (population : List Agent) (allocation : Allocation Agent)
    (below : selectedCount population allocation < population.length) :
    ∃ agent, agent ∈ population ∧ allocation agent = false := by
  induction population with
  | nil => simp [selectedCount] at below
  | cons head tail ih =>
      cases assigned : allocation head
      · exact ⟨head, by simp, assigned⟩
      · have tailBelow : selectedCount tail allocation < tail.length := by
          simp [selectedCount, assigned] at below ⊢
          omega
        obtain ⟨agent, member, unselected⟩ := ih tailBelow
        exact ⟨agent, by simp [member], unselected⟩

/-- Observable population-level outcome: at least one exposed and one
    unexposed agent keep choosing different roles under the same response
    rule at every subsequent period. -/
def PersistentOpportunityRoleSplit
    {Agent Context Role : Type}
    (population : List Agent)
    (allocation : Allocation Agent)
    (initialContext : Context)
    (contextAfterExposure : Context → Agent → Bool → Context)
    (update : Context → Context)
    (choose : Context → Role) : Prop :=
  ∃ selected idle, selected ∈ population ∧ idle ∈ population ∧
    allocation selected = true ∧ allocation idle = false ∧
    ∀ period,
      choose (evolve update period (contextAfterExposure initialContext selected true)) ≠
        choose (evolve update period (contextAfterExposure initialContext idle false))

/-- A realized allocation with at least one recipient and at least one
    nonrecipient, followed by exposure-conditioned contexts in two persistent
    regions, has different roles forever under one shared response function.
    This is a mechanism-to-state-to-response result; the invariant-region
    premises are empirical restrictions to test in a case, not consequences
    of scarcity alone. -/
theorem partial_opportunity_allocation_creates_persistent_role_split
    {Agent Context Role : Type}
    (population : List Agent)
    (allocation : Allocation Agent)
    (selectedRegion idleRegion : Context → Prop)
    (initialContext : Context)
    (contextAfterExposure : Context → Agent → Bool → Context)
    (update : Context → Context)
    (choose : Context → Role)
    (selectedRole idleRole : Role)
    (distinctRoles : selectedRole ≠ idleRole)
    (atLeastOneAssigned : 0 < selectedCount population allocation)
    (atLeastOneUnassigned : selectedCount population allocation < population.length)
    (assignedSeeds : ∀ agent, agent ∈ population → allocation agent = true →
      selectedRegion (contextAfterExposure initialContext agent true))
    (idleSeeds : ∀ agent, agent ∈ population → allocation agent = false →
      idleRegion (contextAfterExposure initialContext agent false))
    (selectedClosed : ∀ context, selectedRegion context → selectedRegion (update context))
    (idleClosed : ∀ context, idleRegion context → idleRegion (update context))
    (choosesSelected : ∀ context, selectedRegion context → choose context = selectedRole)
    (choosesIdle : ∀ context, idleRegion context → choose context = idleRole) :
    PersistentOpportunityRoleSplit population allocation initialContext
      contextAfterExposure update choose := by
  obtain ⟨selected, selectedMember, selectedAssigned⟩ :=
    positive_selected_count_has_selected_witness population allocation atLeastOneAssigned
  obtain ⟨idle, idleMember, idleUnassigned⟩ :=
    selected_count_below_population_has_unselected_witness population allocation
      atLeastOneUnassigned
  refine ⟨selected, idle, selectedMember, idleMember, selectedAssigned,
    idleUnassigned, ?_⟩
  intro period
  have selectedRoleAtEveryPeriod := role_persists_in_forward_invariant_region
    update choose selectedRegion selectedRole selectedClosed choosesSelected
    (contextAfterExposure initialContext selected true)
    (assignedSeeds selected selectedMember selectedAssigned)
    period
  have idleRoleAtEveryPeriod := role_persists_in_forward_invariant_region
    update choose idleRegion idleRole idleClosed choosesIdle
    (contextAfterExposure initialContext idle false)
    (idleSeeds idle idleMember idleUnassigned) period
  rw [selectedRoleAtEveryPeriod, idleRoleAtEveryPeriod]
  exact distinctRoles

/-- If every positive-probability lottery outcome has a strictly partial
    allocation and the same exposure-to-context and invariant-response
    restrictions hold outcome by outcome, the preceding result applies to
    every realized positive-support allocation. This theorem intentionally
    leaves the probability of particular identities unidentified. -/
theorem every_positive_support_outcome_generates_a_role_split
    {Agent Context Role : Type}
    (population : List Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (selectedRegion idleRegion : Context → Prop)
    (initialContext : Context)
    (contextAfterExposure : Context → Agent → Bool → Context)
    (update : Context → Context)
    (choose : Context → Role)
    (selectedRole idleRole : Role)
    (distinctRoles : selectedRole ≠ idleRole)
    (partialAllocation : ∀ allocation weight, (allocation, weight) ∈ lottery.outcomes →
      0 < weight →
        0 < selectedCount population allocation ∧
        selectedCount population allocation < population.length)
    (assignedSeeds : ∀ (allocation : Allocation Agent) agent,
      agent ∈ population → allocation agent = true →
        selectedRegion (contextAfterExposure initialContext agent true))
    (idleSeeds : ∀ (allocation : Allocation Agent) agent,
      agent ∈ population → allocation agent = false →
        idleRegion (contextAfterExposure initialContext agent false))
    (selectedClosed : ∀ context, selectedRegion context → selectedRegion (update context))
    (idleClosed : ∀ context, idleRegion context → idleRegion (update context))
    (choosesSelected : ∀ context, selectedRegion context → choose context = selectedRole)
    (choosesIdle : ∀ context, idleRegion context → choose context = idleRole) :
    ∀ allocation weight, (allocation, weight) ∈ lottery.outcomes → 0 < weight →
      PersistentOpportunityRoleSplit population allocation initialContext
        contextAfterExposure update choose := by
  intro allocation weight member positiveWeight
  obtain ⟨atLeastOneAssigned, atLeastOneUnassigned⟩ :=
    partialAllocation allocation weight member positiveWeight
  exact partial_opportunity_allocation_creates_persistent_role_split
    population allocation selectedRegion idleRegion initialContext contextAfterExposure
    update choose selectedRole idleRole distinctRoles atLeastOneAssigned
    atLeastOneUnassigned
    (assignedSeeds allocation) (idleSeeds allocation) selectedClosed idleClosed
    choosesSelected choosesIdle

/-- Under a lottery whose every positive-mass outcome is partially allocated,
    if common initial context is split by exposure into two invariant response
    regions, then persistent population role differentiation has probability
    exactly one. The lottery may otherwise be arbitrarily dependent and
    non-anonymous; no named agent's role probability is identified. -/
theorem partial_opportunity_lottery_predicts_role_split_probability_one
    {Agent Context Role : Type}
    (population : List Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (isPersistentSplit : Allocation Agent → Bool)
    (selectedRegion idleRegion : Context → Prop)
    (initialContext : Context)
    (contextAfterExposure : Context → Agent → Bool → Context)
    (update : Context → Context)
    (choose : Context → Role)
    (selectedRole idleRole : Role)
    (distinctRoles : selectedRole ≠ idleRole)
    (partialAllocation : ∀ allocation weight, (allocation, weight) ∈ lottery.outcomes →
      0 < weight → 0 < selectedCount population allocation ∧
        selectedCount population allocation < population.length)
    (assignedSeeds : ∀ (allocation : Allocation Agent) agent,
      agent ∈ population → allocation agent = true →
        selectedRegion (contextAfterExposure initialContext agent true))
    (idleSeeds : ∀ (allocation : Allocation Agent) agent,
      agent ∈ population → allocation agent = false →
        idleRegion (contextAfterExposure initialContext agent false))
    (selectedClosed : ∀ context, selectedRegion context → selectedRegion (update context))
    (idleClosed : ∀ context, idleRegion context → idleRegion (update context))
    (choosesSelected : ∀ context, selectedRegion context → choose context = selectedRole)
    (choosesIdle : ∀ context, idleRegion context → choose context = idleRole) :
    (∀ allocation, isPersistentSplit allocation = true ↔
      PersistentOpportunityRoleSplit population allocation initialContext
        contextAfterExposure update choose) →
    eventMass lottery isPersistentSplit = 1 := by
  intro classifierCorrect
  apply eventMass_eq_one_when_event_holds_on_positive_support
  intro allocation weight member positiveWeight
  have split := every_positive_support_outcome_generates_a_role_split
    population lottery selectedRegion idleRegion initialContext contextAfterExposure
    update choose selectedRole idleRole distinctRoles partialAllocation assignedSeeds
    idleSeeds selectedClosed idleClosed choosesSelected choosesIdle
    allocation weight member positiveWeight
  exact (classifierCorrect allocation).2 split

/- A fully explicit reinforcement example. A first assignment exposure moves
   context to +1, no exposure to -1; the same fixed rule selects `true` at
   nonnegative contexts and updates context in the selected role's direction.
   This is a transparent model instance, not an empirical claim about LLMs. -/
def exposureReinforcedContext {Agent : Type}
    (_initialContext : Int) (_agent : Agent) (assigned : Bool) : Int :=
  if assigned then 1 else -1

theorem reinforcing_response_turns_partial_opportunity_into_persistent_split
    {Agent : Type}
    (population : List Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (partialAllocation : ∀ allocation weight, (allocation, weight) ∈ lottery.outcomes →
      0 < weight → 0 < selectedCount population allocation ∧
        selectedCount population allocation < population.length)
    [DecidablePred (fun allocation => PersistentOpportunityRoleSplit population
      allocation 0 exposureReinforcedContext reinforcedUpdate choosesA)] :
    eventMass lottery (fun allocation => decide (PersistentOpportunityRoleSplit
      population allocation 0 exposureReinforcedContext reinforcedUpdate choosesA)) = 1 := by
  classical
  apply partial_opportunity_lottery_predicts_role_split_probability_one
    population lottery
    (fun allocation => decide (PersistentOpportunityRoleSplit population allocation
      0 exposureReinforcedContext reinforcedUpdate choosesA))
    (fun context => 0 < context) (fun context => context < 0)
    0 exposureReinforcedContext reinforcedUpdate choosesA true false
    (by decide) partialAllocation
    (by
      intro allocation agent member assigned
      simp [exposureReinforcedContext])
    (by
      intro allocation agent member unassigned
      simp [exposureReinforcedContext])
    (by
      intro context positive
      have remainsPositive := positive_context_stays_positive context positive 1
      simpa [reinforcedPath] using remainsPositive)
    (by
      intro context negative
      have remainsNegative := negative_context_stays_negative context negative 1
      simpa [reinforcedPath] using remainsNegative)
    (by
      intro context positive
      simp [choosesA]
      omega)
    (by
      intro context negative
      simp [choosesA]
      omega)
    (by
      intro allocation
      simp)

end AgentMicrofoundations.OpportunitySpecialization
