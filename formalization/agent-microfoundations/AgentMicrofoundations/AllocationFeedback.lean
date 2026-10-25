import AgentMicrofoundations.AnonymousAllocation
import AgentMicrofoundations.MechanismFeedback
import AgentMicrofoundations.ResponseIdentification

/-!
This module composes a symmetric random allocation with resource accounting
and a fixed threshold response. It gives a sharp cross-period prediction under
those restrictions; it does not assume that real agents use threshold rules or
that production is deterministic.
-/
namespace AgentMicrofoundations.AllocationFeedback

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AnonymousAllocation
open AgentMicrofoundations.MechanismFeedback

abbrev JointAllocationProduction (Agent : Type) :=
  Allocation Agent × Allocation Agent

/-- Relabel both assignment and production-success profiles together. This
    keeps arbitrary dependence between allocation and production outcomes. -/
def swapJointAllocationProduction {Agent : Type} [DecidableEq Agent]
    (first second : Agent) (outcome : JointAllocationProduction Agent) :
    JointAllocationProduction Agent :=
  (swapAllocation first second outcome.1, swapAllocation first second outcome.2)

def JointSwapInvariantLottery {Agent : Type} [DecidableEq Agent]
    (population : List Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent)) : Prop :=
  ∀ first, first ∈ population → ∀ second, second ∈ population →
    ∀ event : JointAllocationProduction Agent → Bool,
      eventMass (mapDistribution (swapJointAllocationProduction first second) lottery) event =
        eventMass lottery event

def productiveRecipientProfile {Agent : Type}
    (outcome : JointAllocationProduction Agent) : Allocation Agent :=
  fun agent => outcome.1 agent && outcome.2 agent

/-- Case-specific support restriction: every positive-probability production
    success belongs to an agent who received the corresponding opportunity.
    This is not imposed on all economies; it is appropriate only when the
    production outcome is defined as success on an assigned task. -/
def ProductionRequiresAssignment {Agent : Type}
    (lottery : FiniteDistribution (JointAllocationProduction Agent)) : Prop :=
  ∀ outcome weight, (outcome, weight) ∈ lottery.outcomes → 0 < weight →
    ∀ agent, outcome.2 agent = true → outcome.1 agent = true

/-- Under the support restriction, the success marginal equals the successful
    assignment probability. This removes the allocation-success dependence
    ambiguity for that case outcome, without assuming independence. -/
theorem success_marginal_eq_productive_exposure_of_requires_assignment
    {Agent : Type}
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (agent : Agent) (supportRule : ProductionRequiresAssignment lottery) :
    eventMass lottery (fun outcome => outcome.2 agent) =
      eventMass lottery (fun outcome => productiveRecipientProfile outcome agent) := by
  have successBelowProductive :=
    AgentMicrofoundations.ResponseIdentification.eventFold_mono_of_support_inclusion
      lottery.outcomes (fun outcome => outcome.2 agent)
      (fun outcome => productiveRecipientProfile outcome agent) lottery.nonnegative
      (by
        intro outcome weight member positive succeeds
        have assigned := supportRule outcome weight member positive agent succeeds
        simp [productiveRecipientProfile, assigned, succeeds])
  have productiveBelowSuccess :=
    AgentMicrofoundations.ResponseIdentification.eventFold_mono_of_support_inclusion
      lottery.outcomes (fun outcome => productiveRecipientProfile outcome agent)
      (fun outcome => outcome.2 agent) lottery.nonnegative
      (by
        intro outcome weight _ _ productive
        have components : outcome.1 agent = true ∧ outcome.2 agent = true := by
          simpa [productiveRecipientProfile] using productive
        exact components.2)
  apply Rat.le_antisymm
  · simpa [eventMass, AgentMicrofoundations.ResponseIdentification.eventFold]
      using successBelowProductive
  · simpa [eventMass, AgentMicrofoundations.ResponseIdentification.eventFold]
      using productiveBelowSuccess

/-- If a case identifies only the probability of assignment and the marginal
    probability of task success, the probability of successful assignment is
    bounded by the Frechet inequalities. No independence assumption turns the
    two marginals into a product; a full joint trace law can narrow this range. -/
theorem productive_exposure_bounded_by_assignment_and_success_marginals
    {Agent : Type}
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (agent : Agent) :
    eventMass lottery (fun outcome => outcome.1 agent) +
        eventMass lottery (fun outcome => outcome.2 agent) ≤
        1 + eventMass lottery (fun outcome => productiveRecipientProfile outcome agent) ∧
      eventMass lottery (fun outcome => productiveRecipientProfile outcome agent) ≤
        eventMass lottery (fun outcome => outcome.1 agent) ∧
      eventMass lottery (fun outcome => productiveRecipientProfile outcome agent) ≤
        eventMass lottery (fun outcome => outcome.2 agent) := by
  exact AgentMicrofoundations.ResponseIdentification.finite_event_intersection_frechet_bounds lottery
    (fun outcome => outcome.1 agent) (fun outcome => outcome.2 agent)

/-- Group-level partial identification from assignment and success marginals.
    Summing the individual Frechet inequalities bounds the expected number of
    successful recipients without needing the unidentified joint law. The
    lower inequality may be tightened by case-specific support restrictions;
    the upper inequalities hold for every joint law. -/
theorem group_productive_exposure_bounded_by_marginal_masses
    {Agent : Type} (group : FinitePopulation Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent)) :
    ratSumOver group.members (fun agent =>
        eventMass lottery (fun outcome => outcome.1 agent)) +
      ratSumOver group.members (fun agent =>
        eventMass lottery (fun outcome => outcome.2 agent)) ≤
        (group.members.length : Rat) +
          ratSumOver group.members (fun agent =>
            eventMass lottery
              (fun outcome => productiveRecipientProfile outcome agent)) ∧
    ratSumOver group.members (fun agent =>
        eventMass lottery (fun outcome => productiveRecipientProfile outcome agent)) ≤
      ratSumOver group.members (fun agent =>
        eventMass lottery (fun outcome => outcome.1 agent)) ∧
    ratSumOver group.members (fun agent =>
        eventMass lottery (fun outcome => productiveRecipientProfile outcome agent)) ≤
      ratSumOver group.members (fun agent =>
        eventMass lottery (fun outcome => outcome.2 agent)) := by
  have individual agent := productive_exposure_bounded_by_assignment_and_success_marginals
    lottery agent
  have lower := ratSumOver_mono group.members
    (fun agent => eventMass lottery (fun outcome => outcome.1 agent) +
      eventMass lottery (fun outcome => outcome.2 agent))
    (fun agent => 1 + eventMass lottery
      (fun outcome => productiveRecipientProfile outcome agent))
    (by
      intro agent member
      exact (individual agent).1)
  have upperAssignment := ratSumOver_mono group.members
    (fun agent => eventMass lottery
      (fun outcome => productiveRecipientProfile outcome agent))
    (fun agent => eventMass lottery (fun outcome => outcome.1 agent))
    (by
      intro agent member
      exact (individual agent).2.1)
  have upperSuccess := ratSumOver_mono group.members
    (fun agent => eventMass lottery
      (fun outcome => productiveRecipientProfile outcome agent))
    (fun agent => eventMass lottery (fun outcome => outcome.2 agent))
    (by
      intro agent member
      exact (individual agent).2.2)
  have lowerRewritten :
      ratSumOver group.members (fun agent =>
        eventMass lottery (fun outcome => outcome.1 agent)) +
        ratSumOver group.members (fun agent =>
          eventMass lottery (fun outcome => outcome.2 agent)) ≤
        (group.members.length : Rat) +
          ratSumOver group.members (fun agent =>
            eventMass lottery
              (fun outcome => productiveRecipientProfile outcome agent)) := by
    simpa only [ratSumOver_add, ratSumOver_one_eq_length] using lower
  exact ⟨lowerRewritten, upperAssignment, upperSuccess⟩

/-- Simultaneously swapping labels in allocation and production commutes with
    the operation that keeps only successful recipients. -/
theorem productive_profile_respects_joint_swap
    {Agent : Type} [DecidableEq Agent]
    (first second : Agent) (outcome : JointAllocationProduction Agent) :
    productiveRecipientProfile (swapJointAllocationProduction first second outcome) =
      swapAllocation first second (productiveRecipientProfile outcome) := by
  funext agent
  by_cases agentIsFirst : agent = first
  · subst agent
    simp [productiveRecipientProfile, swapJointAllocationProduction, swapAllocation]
  · by_cases agentIsSecond : agent = second
    · subst agent
      simp [productiveRecipientProfile, swapJointAllocationProduction, swapAllocation,
        agentIsFirst]
    · simp [productiveRecipientProfile, swapJointAllocationProduction, swapAllocation,
        agentIsFirst, agentIsSecond]

/-- Joint exchangeability of assignment and production implies exchangeability
    of the productive-recipient lottery, without factorizing the joint law. -/
theorem joint_swap_invariance_implies_productive_lottery_invariance
    {Agent : Type} [DecidableEq Agent]
    (population : List Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (jointInvariant : JointSwapInvariantLottery population lottery) :
    SwapInvariantLottery population
      (mapDistribution productiveRecipientProfile lottery) := by
  intro first firstMember second secondMember event
  calc
    eventMass
        (mapDistribution (swapAllocation first second)
          (mapDistribution productiveRecipientProfile lottery)) event =
      eventMass (mapDistribution productiveRecipientProfile lottery)
        (fun profile => event (swapAllocation first second profile)) :=
          eventMass_mapDistribution (swapAllocation first second)
            (mapDistribution productiveRecipientProfile lottery) event
    _ = eventMass lottery
        (fun outcome => event
          (swapAllocation first second (productiveRecipientProfile outcome))) :=
          eventMass_mapDistribution productiveRecipientProfile lottery
            (fun profile => event (swapAllocation first second profile))
    _ = eventMass lottery
        (fun outcome => event
          (productiveRecipientProfile (swapJointAllocationProduction first second outcome))) := by
            congr 1
            funext outcome
            rw [productive_profile_respects_joint_swap]
    _ = eventMass (mapDistribution
        (swapJointAllocationProduction first second) lottery)
          (fun outcome => event (productiveRecipientProfile outcome)) := by
            symm
            exact eventMass_mapDistribution
              (swapJointAllocationProduction first second) lottery
              (fun outcome => event (productiveRecipientProfile outcome))
    _ = eventMass lottery (fun outcome => event (productiveRecipientProfile outcome)) :=
          jointInvariant first firstMember second secondMember
            (fun outcome => event (productiveRecipientProfile outcome))
    _ = eventMass (mapDistribution productiveRecipientProfile lottery) event := by
          symm
          exact eventMass_mapDistribution productiveRecipientProfile lottery event

/-- The next-period threshold action after an agent either receives one
    opportunity or remains idle. The two balances include their respective
    operating and compute costs and any verified task output. -/
def responseAfterTaskAllocation {Agent : Type}
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (allocation : Allocation Agent) (agent : Agent) : Bool :=
  if allocation agent then
    thresholdResponse threshold
      (resourceAfter resource upkeep taskCost verifiedOutput)
  else
    thresholdResponse threshold (resourceAfter resource upkeep idleCost 0)

/-- A stochastic task outcome has three resource consequences: idle, assigned
    but unsuccessful, and assigned and successful. Production may be correlated
    arbitrarily with assignment and with other agents' outcomes. -/
def responseAfterStochasticTask {Agent : Type}
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (outcome : JointAllocationProduction Agent) (agent : Agent) : Bool :=
  if outcome.1 agent then
    if outcome.2 agent then
      thresholdResponse threshold (resourceAfter resource upkeep taskCost verifiedOutput)
    else thresholdResponse threshold (resourceAfter resource upkeep taskCost 0)
  else thresholdResponse threshold (resourceAfter resource upkeep idleCost 0)

/-- Agent-specific resource and threshold inputs for the cross-period bridge.
    The profile may vary by agent; this structure does not assume identical
    balances, costs, verified output, or response thresholds. -/
structure AgentThresholdResources where
  threshold : Int
  resource : Int
  upkeep : Int
  assignedCost : Int
  idleCost : Int
  verifiedOutput : Int

/-- The empirically testable margin condition under which a task success,
    rather than assignment alone, determines next-period threshold activity
    for one agent. Idle and failed-task balances lie below its threshold;
    successful-task balance reaches or exceeds it. -/
def ThresholdCrossing (parameters : AgentThresholdResources) : Prop :=
  resourceAfter parameters.resource parameters.upkeep parameters.idleCost 0 <
      parameters.threshold ∧
    resourceAfter parameters.resource parameters.upkeep parameters.assignedCost 0 <
      parameters.threshold ∧
    parameters.threshold ≤
      resourceAfter parameters.resource parameters.upkeep parameters.assignedCost
        parameters.verifiedOutput

/-- Next-period activity under an agent-specific resource state, operating
    costs, verified reward, and threshold response. -/
def responseAfterHeterogeneousTask {Agent : Type}
    (parameters : Agent → AgentThresholdResources)
    (outcome : JointAllocationProduction Agent) (agent : Agent) : Bool :=
  if outcome.1 agent then
    if outcome.2 agent then
      thresholdResponse (parameters agent).threshold
        (resourceAfter (parameters agent).resource (parameters agent).upkeep
          (parameters agent).assignedCost (parameters agent).verifiedOutput)
    else
      thresholdResponse (parameters agent).threshold
        (resourceAfter (parameters agent).resource (parameters agent).upkeep
          (parameters agent).assignedCost 0)
  else
    thresholdResponse (parameters agent).threshold
      (resourceAfter (parameters agent).resource (parameters agent).upkeep
        (parameters agent).idleCost 0)

/-- The individual response is exactly its productive-assignment indicator
    when that agent's own three resource margins straddle its threshold. -/
theorem heterogeneous_threshold_response_matches_productive_recipient
    {Agent : Type} (parameters : Agent → AgentThresholdResources)
    (agent : Agent) (conditions : ThresholdCrossing (parameters agent)) :
    (fun outcome => responseAfterHeterogeneousTask parameters outcome agent) =
      (fun outcome => productiveRecipientProfile outcome agent) := by
  funext outcome
  rcases conditions with ⟨idleBelow, failureBelow, successCrosses⟩
  by_cases assigned : outcome.1 agent
  · by_cases succeeds : outcome.2 agent
    · simp [responseAfterHeterogeneousTask, productiveRecipientProfile, assigned,
        succeeds, thresholdResponse, successCrosses]
    · simp [responseAfterHeterogeneousTask, productiveRecipientProfile, assigned,
        succeeds, thresholdResponse, failureBelow]
  · simp [responseAfterHeterogeneousTask, productiveRecipientProfile, assigned,
      thresholdResponse, idleBelow]

theorem heterogeneous_next_action_probability_eq_productive_exposure
    {Agent : Type} (parameters : Agent → AgentThresholdResources)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (agent : Agent) (conditions : ThresholdCrossing (parameters agent)) :
    eventMass lottery
      (fun outcome => responseAfterHeterogeneousTask parameters outcome agent) =
      selectionMass (mapDistribution productiveRecipientProfile lottery).outcomes agent := by
  rw [heterogeneous_threshold_response_matches_productive_recipient
    parameters agent conditions]
  simpa [eventMass, selectionMass] using
    (eventMass_mapDistribution productiveRecipientProfile lottery
      (fun profile => profile agent)).symm

/-- Heterogeneous group prediction: for any duplicate-free group, if each
    member's own resource/cost/output/threshold margins satisfy its crossing
    condition, the sum of their next-period activity probabilities equals the
    expected number of successful recipients in that group. The allocation
    and production lottery may be asymmetric and arbitrarily dependent. -/
theorem heterogeneous_group_next_active_mass_eq_expected_productive_count
    {Agent : Type}
    (group : FinitePopulation Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (parameters : Agent → AgentThresholdResources)
    (conditions : ∀ agent, agent ∈ group.members → ThresholdCrossing (parameters agent)) :
    ratSumOver group.members
      (fun agent => eventMass lottery
        (fun outcome => responseAfterHeterogeneousTask parameters outcome agent)) =
      expectedSelectionMass group.members
        (mapDistribution productiveRecipientProfile lottery).outcomes := by
  calc
    ratSumOver group.members
        (fun agent => eventMass lottery
          (fun outcome => responseAfterHeterogeneousTask parameters outcome agent)) =
      ratSumOver group.members
        (selectionMass (mapDistribution productiveRecipientProfile lottery).outcomes) := by
          apply ratSumOver_congr
          intro agent member
          exact heterogeneous_next_action_probability_eq_productive_exposure
            parameters lottery agent (conditions agent member)
    _ = expectedSelectionMass group.members
        (mapDistribution productiveRecipientProfile lottery).outcomes :=
      aggregate_selection_mass_eq_expected_count group.members
        (mapDistribution productiveRecipientProfile lottery).outcomes

/-- Micro-to-group scale prediction. If the *joint* allocation/production
    law is anonymous under relabeling, exactly `k` population members are
    productive in every listed outcome, and every member of the target group
    crosses its own resource threshold exactly on productive receipt, then
    `N · E[next active members in group] = |G| · k`.

    Thus changing population or group size has a calculable implication without
    simulating each identity. The result predicts an expectation, not who is
    active in a realized round or the probability of any particular active
    count. Anonymity is imposed on the joint law, not merely the allocator;
    heterogeneous success rates can therefore invalidate the prediction.
    Fixed count applies only on the lottery's positive-probability support;
    zero-weight rows impose no restriction. -/
theorem anonymous_fixed_productivity_predicts_group_next_activity
    {Agent : Type} [DecidableEq Agent]
    (population group : FinitePopulation Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (parameters : Agent → AgentThresholdResources)
    (conditions : ∀ agent, agent ∈ group.members → ThresholdCrossing (parameters agent))
    (groupWithinPopulation : ∀ agent, agent ∈ group.members → agent ∈ population.members)
    (productiveCount : Nat)
    (populationReference groupReference : Agent)
    (populationReferencePresent : populationReference ∈ population.members)
    (groupReferencePresent : groupReference ∈ group.members)
    (fixedProductiveCount : ∀ profile weight,
      (profile, weight) ∈ (mapDistribution productiveRecipientProfile lottery).outcomes →
        0 < weight →
        selectedCount population.members profile = productiveCount)
    (jointAnonymity : JointSwapInvariantLottery population.members lottery) :
    (population.members.length : Rat) *
      ratSumOver group.members
        (fun agent => eventMass lottery
          (fun outcome => responseAfterHeterogeneousTask parameters outcome agent)) =
      (group.members.length : Rat) * (productiveCount : Rat) := by
  have productiveAnonymity :=
    joint_swap_invariance_implies_productive_lottery_invariance
      population.members lottery jointAnonymity
  have groupExposure := symmetric_lottery_group_exposure_scales_with_group_size
    population group (mapDistribution productiveRecipientProfile lottery)
    productiveCount populationReference groupReference populationReferencePresent
    groupReferencePresent groupWithinPopulation fixedProductiveCount productiveAnonymity
  rw [heterogeneous_group_next_active_mass_eq_expected_productive_count
    group lottery parameters conditions]
  exact groupExposure

/-- If the case semantics guarantee success only after assignment, the
    threshold-response prediction can be computed from success marginals alone.
    The lottery may remain dependent and asymmetric across agents. -/
theorem heterogeneous_group_next_active_mass_eq_success_marginal_mass
    {Agent : Type}
    (group : FinitePopulation Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (parameters : Agent → AgentThresholdResources)
    (conditions : ∀ agent, agent ∈ group.members → ThresholdCrossing (parameters agent))
    (supportRule : ProductionRequiresAssignment lottery) :
    ratSumOver group.members
      (fun agent => eventMass lottery
        (fun outcome => responseAfterHeterogeneousTask parameters outcome agent)) =
    ratSumOver group.members
      (fun agent => eventMass lottery (fun outcome => outcome.2 agent)) := by
  apply ratSumOver_congr
  intro agent member
  calc
    eventMass lottery
        (fun outcome => responseAfterHeterogeneousTask parameters outcome agent) =
      eventMass lottery
        (fun outcome => productiveRecipientProfile outcome agent) :=
      calc
        eventMass lottery
            (fun outcome => responseAfterHeterogeneousTask parameters outcome agent) =
          selectionMass (mapDistribution productiveRecipientProfile lottery).outcomes agent :=
            heterogeneous_next_action_probability_eq_productive_exposure
              parameters lottery agent (conditions agent member)
        _ = eventMass (mapDistribution productiveRecipientProfile lottery)
              (fun profile => profile agent) := by rfl
        _ = eventMass lottery
              (fun outcome => productiveRecipientProfile outcome agent) :=
                eventMass_mapDistribution productiveRecipientProfile lottery
                  (fun profile => profile agent)
    _ = eventMass lottery (fun outcome => outcome.2 agent) :=
          (success_marginal_eq_productive_exposure_of_requires_assignment
            lottery agent supportRule).symm

/-- Probability that at least one member of a group is active next period.
    Under individual threshold crossing, it is bounded below by each named
    member's activity probability and above by the expected number of
    productive recipients. The upper bound is the finite union bound; no
    cross-agent independence or exchangeability is assumed. -/
theorem heterogeneous_group_any_next_active_probability_bounds
    {Agent : Type}
    (group : FinitePopulation Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (parameters : Agent → AgentThresholdResources)
    (conditions : ∀ agent, agent ∈ group.members → ThresholdCrossing (parameters agent)) :
    (∀ agent, agent ∈ group.members →
      eventMass lottery
        (fun outcome => responseAfterHeterogeneousTask parameters outcome agent) ≤
      eventMass lottery
        (fun outcome => group.members.any
          (fun member => responseAfterHeterogeneousTask parameters outcome member))) ∧
    eventMass lottery
      (fun outcome => group.members.any
        (fun agent => responseAfterHeterogeneousTask parameters outcome agent)) ≤
      expectedSelectionMass group.members
        (mapDistribution productiveRecipientProfile lottery).outcomes := by
  let productiveLottery := mapDistribution productiveRecipientProfile lottery
  have activeAnyEqualsProductiveAny :
      (fun outcome => group.members.any
        (fun agent => responseAfterHeterogeneousTask parameters outcome agent)) =
      (fun outcome => group.members.any
        (fun agent => productiveRecipientProfile outcome agent)) := by
    funext outcome
    apply any_congr_on_members group.members
    intro agent member
    exact congrFun (heterogeneous_threshold_response_matches_productive_recipient
      parameters agent (conditions agent member)) outcome
  constructor
  · intro agent member
    calc
      eventMass lottery
          (fun outcome => responseAfterHeterogeneousTask parameters outcome agent) =
        selectionMass productiveLottery.outcomes agent :=
          heterogeneous_next_action_probability_eq_productive_exposure
            parameters lottery agent (conditions agent member)
      _ ≤ eventMass productiveLottery
          (fun allocation => group.members.any allocation) :=
            individual_selection_mass_le_probability_any_selected group
              productiveLottery agent member
      _ = eventMass lottery
          (fun outcome => group.members.any
            (fun member => productiveRecipientProfile outcome member)) := by
              exact eventMass_mapDistribution productiveRecipientProfile lottery
                (fun allocation => group.members.any allocation)
      _ = eventMass lottery
          (fun outcome => group.members.any
            (fun member => responseAfterHeterogeneousTask parameters outcome member)) := by
              rw [activeAnyEqualsProductiveAny]
  · calc
      eventMass lottery
          (fun outcome => group.members.any
            (fun agent => responseAfterHeterogeneousTask parameters outcome agent)) =
        eventMass productiveLottery (fun allocation => group.members.any allocation) := by
          rw [activeAnyEqualsProductiveAny]
          exact (eventMass_mapDistribution productiveRecipientProfile lottery
            (fun allocation => group.members.any allocation)).symm
      _ ≤ expectedSelectionMass group.members productiveLottery.outcomes :=
        probability_any_selected_le_expected_count group.members productiveLottery

/-- Boundary counterexample: if failure leaves an agent at its threshold,
    a failed assignment can still activate the threshold response, so next
    activity need not equal productive assignment. The crossing hypothesis
    cannot be dropped from the bridge as an unconditional law. -/
theorem failed_task_at_threshold_breaks_productive_response_identity :
    let parameters : Unit → AgentThresholdResources := fun _ =>
      { threshold := 0, resource := 0, upkeep := 0, assignedCost := 0,
        idleCost := 0, verifiedOutput := 0 }
    let outcome : JointAllocationProduction Unit := (fun _ => true, fun _ => false)
    ¬ ThresholdCrossing (parameters ()) ∧
      responseAfterHeterogeneousTask parameters outcome () = true ∧
      productiveRecipientProfile outcome () = false := by
  simp [ThresholdCrossing, responseAfterHeterogeneousTask,
    productiveRecipientProfile, thresholdResponse, resourceAfter]

theorem stochastic_threshold_response_matches_productive_recipient
    {Agent : Type} (agent : Agent)
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (idleBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (failureBelow : resourceAfter resource upkeep taskCost 0 < threshold)
    (successCrosses : threshold ≤
      resourceAfter resource upkeep taskCost verifiedOutput) :
    (fun outcome => responseAfterStochasticTask threshold resource upkeep taskCost
      idleCost verifiedOutput outcome agent) =
      (fun outcome => productiveRecipientProfile outcome agent) := by
  funext outcome
  by_cases assigned : outcome.1 agent
  · by_cases succeeds : outcome.2 agent
    · simp [responseAfterStochasticTask, productiveRecipientProfile, assigned,
        succeeds, thresholdResponse, successCrosses]
    · simp [responseAfterStochasticTask, productiveRecipientProfile, assigned,
        succeeds, thresholdResponse, failureBelow]
  · simp [responseAfterStochasticTask, productiveRecipientProfile, assigned,
      thresholdResponse, idleBelow]

theorem stochastic_next_action_probability_eq_productive_exposure
    {Agent : Type} (agent : Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (idleBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (failureBelow : resourceAfter resource upkeep taskCost 0 < threshold)
    (successCrosses : threshold ≤
      resourceAfter resource upkeep taskCost verifiedOutput) :
    eventMass lottery (fun outcome => responseAfterStochasticTask threshold resource
      upkeep taskCost idleCost verifiedOutput outcome agent) =
      selectionMass (mapDistribution productiveRecipientProfile lottery).outcomes agent := by
  rw [stochastic_threshold_response_matches_productive_recipient agent threshold
    resource upkeep taskCost idleCost verifiedOutput idleBelow failureBelow successCrosses]
  simpa [eventMass, selectionMass] using
    (eventMass_mapDistribution productiveRecipientProfile lottery
      (fun profile => profile agent)).symm

/-- Aggregate cross-period prediction without allocator anonymity: if each
    agent's next-period threshold action is active exactly when that agent was
    both assigned and successful, then summing individual active probabilities
    over the population equals the expected number of successful recipients.
    The allocation-production lottery may be asymmetric and may contain
    arbitrary dependence. Symmetry is needed only to turn this aggregate
    identity into a named-agent prediction. -/
theorem aggregate_next_active_mass_eq_expected_productive_count
    {Agent : Type}
    (population : List Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (idleBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (failureBelow : resourceAfter resource upkeep taskCost 0 < threshold)
    (successCrosses : threshold ≤
      resourceAfter resource upkeep taskCost verifiedOutput) :
    ratSumOver population
      (fun agent => eventMass lottery
        (fun outcome => responseAfterStochasticTask threshold resource upkeep
          taskCost idleCost verifiedOutput outcome agent)) =
      expectedSelectionMass population
        (mapDistribution productiveRecipientProfile lottery).outcomes := by
  calc
    ratSumOver population
        (fun agent => eventMass lottery
          (fun outcome => responseAfterStochasticTask threshold resource upkeep
            taskCost idleCost verifiedOutput outcome agent)) =
      ratSumOver population
        (selectionMass (mapDistribution productiveRecipientProfile lottery).outcomes) := by
          apply ratSumOver_congr
          intro agent _
          exact stochastic_next_action_probability_eq_productive_exposure agent lottery
            threshold resource upkeep taskCost idleCost verifiedOutput idleBelow
            failureBelow successCrosses
    _ = expectedSelectionMass population
        (mapDistribution productiveRecipientProfile lottery).outcomes :=
      aggregate_selection_mass_eq_expected_count population
        (mapDistribution productiveRecipientProfile lottery).outcomes

/-- Stochastic cross-period theorem: when the joint assignment-production law
    is invariant under population-label swaps, the probability that a named
    agent's next threshold action is active satisfies `N · p` equal to the
    expected number of successful recipients. No independence between agents,
    and no independence between assignment and production, is assumed. -/
theorem stochastic_production_and_response_follow_expected_productive_count
    {Agent : Type} [DecidableEq Agent]
    (population : FinitePopulation Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (reference : Agent) (referencePresent : reference ∈ population.members)
    (jointInvariant : JointSwapInvariantLottery population.members lottery)
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (idleBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (failureBelow : resourceAfter resource upkeep taskCost 0 < threshold)
    (successCrosses : threshold ≤
      resourceAfter resource upkeep taskCost verifiedOutput) :
    (population.members.length : Rat) *
      eventMass lottery (fun outcome => responseAfterStochasticTask threshold resource
        upkeep taskCost idleCost verifiedOutput outcome reference) =
      expectedSelectionMass population.members
        (mapDistribution productiveRecipientProfile lottery).outcomes := by
  rw [stochastic_next_action_probability_eq_productive_exposure reference lottery threshold
    resource upkeep taskCost idleCost verifiedOutput idleBelow failureBelow successCrosses]
  exact symmetric_lottery_exposure_eq_expected_count population
    (mapDistribution productiveRecipientProfile lottery) reference referencePresent
    (joint_swap_invariance_implies_productive_lottery_invariance population.members lottery
      jointInvariant)

/-- Opportunity-production bound: under the same symmetric lottery and
    threshold-crossing conditions, an agent's next-period active probability,
    multiplied by population size, cannot exceed the expected number assigned
    an opportunity. The bound needs no independence and no assumption about
    how often production succeeds: successful recipients are pointwise a
    subset of assigned recipients. -/
theorem stochastic_next_action_rate_le_expected_opportunity_count
    {Agent : Type} [DecidableEq Agent]
    (population : FinitePopulation Agent)
    (lottery : FiniteDistribution (JointAllocationProduction Agent))
    (reference : Agent) (referencePresent : reference ∈ population.members)
    (jointInvariant : JointSwapInvariantLottery population.members lottery)
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (idleBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (failureBelow : resourceAfter resource upkeep taskCost 0 < threshold)
    (successCrosses : threshold ≤
      resourceAfter resource upkeep taskCost verifiedOutput) :
    (population.members.length : Rat) *
      eventMass lottery (fun outcome => responseAfterStochasticTask threshold resource
        upkeep taskCost idleCost verifiedOutput outcome reference) ≤
      expectedSelectionMass population.members
        (mapDistribution Prod.fst lottery).outcomes := by
  rw [stochastic_production_and_response_follow_expected_productive_count
    population lottery reference referencePresent jointInvariant threshold resource upkeep
    taskCost idleCost verifiedOutput idleBelow failureBelow successCrosses]
  have subsetBound := expectedProfileCount_mono population.members
    productiveRecipientProfile (fun outcome => outcome.1) lottery.outcomes
    lottery.nonnegative (fun outcome => by
      exact selectedCount_intersection_le population.members outcome.1 outcome.2)
  change expectedSelectionMass population.members
      (mapEntries productiveRecipientProfile lottery.outcomes) ≤
    expectedSelectionMass population.members
      (mapEntries (fun outcome => outcome.1) lottery.outcomes)
  rw [expectedSelectionMass_mapEntries, expectedSelectionMass_mapEntries]
  exact subsetBound

/-- When the idle balance is below the response threshold and the assigned
    balance is at or above it, the next-period action is exactly the assignment
    indicator. Its probability therefore equals the agent's exposure mass. -/
theorem threshold_crossing_makes_next_action_equal_assignment
    {Agent : Type} (agent : Agent)
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (idleBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (taskCrosses : threshold ≤
      resourceAfter resource upkeep taskCost verifiedOutput) :
    (fun allocation => responseAfterTaskAllocation threshold resource upkeep
      taskCost idleCost verifiedOutput allocation agent) =
      (fun allocation => allocation agent) := by
  funext allocation
  by_cases assigned : allocation agent
  · simp [responseAfterTaskAllocation, assigned, thresholdResponse, taskCrosses]
  · simp [responseAfterTaskAllocation, assigned, thresholdResponse, idleBelow]

theorem next_action_probability_equals_exposure
    {Agent : Type} (agent : Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (idleBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (taskCrosses : threshold ≤
      resourceAfter resource upkeep taskCost verifiedOutput) :
    eventMass lottery
      (fun allocation => responseAfterTaskAllocation threshold resource upkeep
        taskCost idleCost verifiedOutput allocation agent) =
      selectionMass lottery.outcomes agent := by
  rw [threshold_crossing_makes_next_action_equal_assignment agent threshold resource
    upkeep taskCost idleCost verifiedOutput idleBelow taskCrosses]
  rfl

/-- Integrated micro-to-population prediction: under a duplicate-free finite
    population, a fixed number of assignments, a lottery invariant under every
    pairwise population-label swap, and a fixed threshold response crossed by
    the assigned resource balance, each member's next-action probability obeys
    `N · p = m`. Randomness here comes from allocation; production and the
    response rule are fixed in this theorem. -/
theorem symmetric_assignment_crossing_predicts_next_action_rate
    {Agent : Type} [DecidableEq Agent]
    (population : FinitePopulation Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (assignments : Nat) (reference : Agent)
    (referencePresent : reference ∈ population.members)
    (fixedCount : ∀ allocation weight,
      (allocation, weight) ∈ lottery.outcomes → 0 < weight →
        selectedCount population.members allocation = assignments)
    (swapInvariant : SwapInvariantLottery population.members lottery)
    (threshold resource upkeep taskCost idleCost verifiedOutput : Int)
    (idleBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (taskCrosses : threshold ≤
      resourceAfter resource upkeep taskCost verifiedOutput) :
    (population.members.length : Rat) *
      eventMass lottery
        (fun allocation => responseAfterTaskAllocation threshold resource upkeep
          taskCost idleCost verifiedOutput allocation reference) =
      (assignments : Rat) := by
  rw [next_action_probability_equals_exposure reference lottery threshold resource
    upkeep taskCost idleCost verifiedOutput idleBelow taskCrosses]
  exact anonymous_fixed_assignments_imply_individual_exposure population lottery
    assignments reference referencePresent fixedCount swapInvariant

end AgentMicrofoundations.AllocationFeedback
