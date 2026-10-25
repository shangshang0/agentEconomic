import AgentMicrofoundations.AllocationFeedback
import AgentMicrofoundations.CaseAnalysis

/-!
The optional CTF subgroup model. The trace archive is now instantiated
separately in `CTFArchive` from task-level assignments and checker outcomes;
`CTFTraceModel` stores the reusable day-level joint record for arbitrary
populations and group queries. This file studies an additional threshold-based
prediction for a selected subgroup. Its threshold-crossing, anonymity, and
fixed-productivity conditions remain separate, testable restrictions and are
not implied by the archive's finite slot frequencies.
-/
namespace AgentMicrofoundations.CaseStudies.CTFModel

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AnonymousAllocation
open AgentMicrofoundations.AllocationFeedback

/-- A CTF world model is a case-specific instantiation of the reusable
    allocation-production-response foundation. The group lists are persistent
    identities, the joint lottery is the case's fitted/posited law, and every
    threshold condition is checked separately for the corresponding agent. -/
structure CTFGroupWorldModel (Agent : Type) where
  population : FinitePopulation Agent
  fourBloc : FinitePopulation Agent
  twoBloc : FinitePopulation Agent
  populationSize : population.members.length = 6
  fourBlocSize : fourBloc.members.length = 4
  twoBlocSize : twoBloc.members.length = 2
  fourBlocContained : ∀ agent, agent ∈ fourBloc.members →
    agent ∈ population.members
  twoBlocContained : ∀ agent, agent ∈ twoBloc.members →
    agent ∈ population.members
  groupPartition : ∀ agent, agent ∈ population.members →
    (agent ∈ fourBloc.members ∧ agent ∉ twoBloc.members) ∨
      (agent ∈ twoBloc.members ∧ agent ∉ fourBloc.members)
  allocationProductionLaw : FiniteDistribution (JointAllocationProduction Agent)
  successRequiresAssignment : ProductionRequiresAssignment allocationProductionLaw
  agentResources : Agent → AgentThresholdResources
  fourBlocThresholds : ∀ agent, agent ∈ fourBloc.members →
    ThresholdCrossing (agentResources agent)
  twoBlocThresholds : ∀ agent, agent ∈ twoBloc.members →
    ThresholdCrossing (agentResources agent)
  atMostThreeRecipients : ∀ outcome weight,
    (outcome, weight) ∈ allocationProductionLaw.outcomes →
      selectedCount population.members outcome.1 ≤ 3

def expectedSuccessfulFourBlocCount {Agent : Type}
    (model : CTFGroupWorldModel Agent) : Rat :=
  expectedSelectionMass model.fourBloc.members
    (mapDistribution productiveRecipientProfile model.allocationProductionLaw).outcomes

def expectedSuccessfulTwoBlocCount {Agent : Type}
    (model : CTFGroupWorldModel Agent) : Rat :=
  expectedSelectionMass model.twoBloc.members
    (mapDistribution productiveRecipientProfile model.allocationProductionLaw).outcomes

/-- Case prediction derived from the general microfoundation. Given a fitted
    CTF allocation-production law and individually checked threshold margins,
    the four-agent bloc's total next-period activity probability equals its
    expected successful assignments. -/
theorem fourBlocActivityPrediction {Agent : Type}
    (model : CTFGroupWorldModel Agent) :
    ratSumOver model.fourBloc.members
      (fun agent => eventMass model.allocationProductionLaw
        (fun outcome => responseAfterHeterogeneousTask model.agentResources
          outcome agent)) =
      expectedSuccessfulFourBlocCount model := by
  exact heterogeneous_group_next_active_mass_eq_expected_productive_count
    model.fourBloc model.allocationProductionLaw model.agentResources
    model.fourBlocThresholds

/-- The parallel two-agent bloc prediction, with no exchangeability or
    independence assumption. -/
theorem twoBlocActivityPrediction {Agent : Type}
    (model : CTFGroupWorldModel Agent) :
    ratSumOver model.twoBloc.members
      (fun agent => eventMass model.allocationProductionLaw
        (fun outcome => responseAfterHeterogeneousTask model.agentResources
          outcome agent)) =
      expectedSuccessfulTwoBlocCount model := by
  exact heterogeneous_group_next_active_mass_eq_expected_productive_count
    model.twoBloc model.allocationProductionLaw model.agentResources
    model.twoBlocThresholds

/-- CTF case-level implication of the anonymous fixed-productivity law.
    If the joint assignment/production lottery is label-anonymous and every
    positive-mass outcome has exactly `productiveCount` productive agents,
    then the expected number of next-period active agents in the four-member
    bloc is exactly twice that in the two-member bloc. This is a prediction
    about group totals, not realized membership or individual identities. The
    anonymity and fixed-count restrictions are case hypotheses to test; they
    are not inferred from the 4+2 partition itself. -/
theorem fourBlocActivityIsTwiceTwoBlocActivity {Agent : Type} [DecidableEq Agent]
    (model : CTFGroupWorldModel Agent)
    (productiveCount : Nat)
    (fourReference : Agent) (fourReferencePresent : fourReference ∈ model.fourBloc.members)
    (twoReference : Agent) (twoReferencePresent : twoReference ∈ model.twoBloc.members)
    (fixedProductiveCount : ∀ profile weight,
      (profile, weight) ∈
        (mapDistribution productiveRecipientProfile model.allocationProductionLaw).outcomes →
        0 < weight →
        selectedCount model.population.members profile = productiveCount)
    (jointAnonymity : JointSwapInvariantLottery model.population.members
      model.allocationProductionLaw) :
    ((6 : Rat) * ratSumOver model.fourBloc.members
        (fun agent => eventMass model.allocationProductionLaw
          (fun outcome => responseAfterHeterogeneousTask model.agentResources outcome agent)) =
        4 * (productiveCount : Rat)) ∧
    ((6 : Rat) * ratSumOver model.twoBloc.members
        (fun agent => eventMass model.allocationProductionLaw
          (fun outcome => responseAfterHeterogeneousTask model.agentResources outcome agent)) =
        2 * (productiveCount : Rat)) := by
  have fourPrediction := anonymous_fixed_productivity_predicts_group_next_activity
    model.population model.fourBloc model.allocationProductionLaw model.agentResources
    model.fourBlocThresholds model.fourBlocContained productiveCount
    fourReference fourReference
    (model.fourBlocContained fourReference fourReferencePresent)
    fourReferencePresent fixedProductiveCount jointAnonymity
  have twoPrediction := anonymous_fixed_productivity_predicts_group_next_activity
    model.population model.twoBloc model.allocationProductionLaw model.agentResources
    model.twoBlocThresholds model.twoBlocContained productiveCount
    twoReference twoReference
    (model.twoBlocContained twoReference twoReferencePresent)
    twoReferencePresent fixedProductiveCount jointAnonymity
  have populationSize : (model.population.members.length : Rat) = 6 := by
    exact_mod_cast model.populationSize
  have fourSize : (model.fourBloc.members.length : Rat) = 4 := by
    exact_mod_cast model.fourBlocSize
  have twoSize : (model.twoBloc.members.length : Rat) = 2 := by
    exact_mod_cast model.twoBlocSize
  rw [populationSize, fourSize] at fourPrediction
  rw [populationSize, twoSize] at twoPrediction
  exact ⟨fourPrediction, twoPrediction⟩

/-- When task success is defined only for assigned agents, four-bloc next
    activity mass is also identified by the group's success marginals. -/
theorem fourBlocActivityFromSuccessMarginals {Agent : Type}
    (model : CTFGroupWorldModel Agent) :
    ratSumOver model.fourBloc.members
      (fun agent => eventMass model.allocationProductionLaw
        (fun outcome => responseAfterHeterogeneousTask model.agentResources
          outcome agent)) =
      ratSumOver model.fourBloc.members
        (fun agent => eventMass model.allocationProductionLaw
          (fun outcome => outcome.2 agent)) := by
  exact heterogeneous_group_next_active_mass_eq_success_marginal_mass
    model.fourBloc model.allocationProductionLaw model.agentResources
    model.fourBlocThresholds model.successRequiresAssignment

/-- The corresponding two-bloc prediction from success marginals. -/
theorem twoBlocActivityFromSuccessMarginals {Agent : Type}
    (model : CTFGroupWorldModel Agent) :
    ratSumOver model.twoBloc.members
      (fun agent => eventMass model.allocationProductionLaw
        (fun outcome => responseAfterHeterogeneousTask model.agentResources
          outcome agent)) =
      ratSumOver model.twoBloc.members
        (fun agent => eventMass model.allocationProductionLaw
          (fun outcome => outcome.2 agent)) := by
  exact heterogeneous_group_next_active_mass_eq_success_marginal_mass
    model.twoBloc model.allocationProductionLaw model.agentResources
    model.twoBlocThresholds model.successRequiresAssignment

/-- The probability of at least one active agent in the four-agent bloc is
    bounded by each member's marginal and by the bloc's expected active count.
    This does not identify the full count distribution. -/
theorem fourBlocAnyActivityBounds {Agent : Type}
    (model : CTFGroupWorldModel Agent) :
    (∀ agent, agent ∈ model.fourBloc.members →
      eventMass model.allocationProductionLaw
        (fun outcome => responseAfterHeterogeneousTask model.agentResources outcome agent) ≤
      eventMass model.allocationProductionLaw
        (fun outcome => model.fourBloc.members.any
          (fun member => responseAfterHeterogeneousTask model.agentResources outcome member))) ∧
    eventMass model.allocationProductionLaw
      (fun outcome => model.fourBloc.members.any
        (fun agent => responseAfterHeterogeneousTask model.agentResources outcome agent)) ≤
      expectedSelectionMass model.fourBloc.members
        (mapDistribution productiveRecipientProfile model.allocationProductionLaw).outcomes := by
  exact heterogeneous_group_any_next_active_probability_bounds
    model.fourBloc model.allocationProductionLaw model.agentResources
    model.fourBlocThresholds

/-- The same any-active probability bounds for the two-agent bloc. -/
theorem twoBlocAnyActivityBounds {Agent : Type}
    (model : CTFGroupWorldModel Agent) :
    (∀ agent, agent ∈ model.twoBloc.members →
      eventMass model.allocationProductionLaw
        (fun outcome => responseAfterHeterogeneousTask model.agentResources outcome agent) ≤
      eventMass model.allocationProductionLaw
        (fun outcome => model.twoBloc.members.any
          (fun member => responseAfterHeterogeneousTask model.agentResources outcome member))) ∧
    eventMass model.allocationProductionLaw
      (fun outcome => model.twoBloc.members.any
        (fun agent => responseAfterHeterogeneousTask model.agentResources outcome agent)) ≤
      expectedSelectionMass model.twoBloc.members
        (mapDistribution productiveRecipientProfile model.allocationProductionLaw).outcomes := by
  exact heterogeneous_group_any_next_active_probability_bounds
    model.twoBloc model.allocationProductionLaw model.agentResources
    model.twoBlocThresholds

end AgentMicrofoundations.CaseStudies.CTFModel
