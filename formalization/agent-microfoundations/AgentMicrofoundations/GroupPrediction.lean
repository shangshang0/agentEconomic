import AgentMicrofoundations.AllocationFeedback

/-!
Reusable finite-population prediction interface.

The target group is an arbitrary finite subset of a population. Its size,
complement, and relationship to other queries are not fixed by the theory.
The period allocation-production law is joint: it may encode arbitrary
heterogeneity and dependence. A group-level activity forecast follows only
when each member's measured resource margins satisfy the explicit
success-threshold bridge. This separates the general prediction interface
from optional restrictions such as anonymity or fixed successful headcount.
-/
namespace AgentMicrofoundations.GroupPrediction

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AnonymousAllocation
open AgentMicrofoundations.AllocationFeedback

/-- A case query over any finite population and any selected identity set.
    `groupContained` is a data integrity condition; it does not require the
    selected identities to form a preassigned experimental arm or partition. -/
structure GroupCase (Agent : Type) where
  population : FinitePopulation Agent
  group : FinitePopulation Agent
  groupContained : ∀ agent, agent ∈ group.members → agent ∈ population.members
  periodLaw : FiniteDistribution (JointAllocationProduction Agent)
  margins : Agent → AgentThresholdResources
  thresholdBridge : ∀ agent, agent ∈ group.members →
    ThresholdCrossing (margins agent)

/-- Expected successful recipients in the queried group. -/
def expectedGroupProduction {Agent : Type} (case : GroupCase Agent) : Rat :=
  expectedSelectionMass case.group.members
    (mapDistribution productiveRecipientProfile case.periodLaw).outcomes

/-- Expected next-period active members in the queried group, under the
    explicitly stated agent-specific threshold response. -/
def expectedGroupActivity {Agent : Type} (case : GroupCase Agent) : Rat :=
  ratSumOver case.group.members
    (fun agent => eventMass case.periodLaw
      (fun outcome => responseAfterHeterogeneousTask case.margins outcome agent))

/-- Arbitrary-group micro-to-aggregate prediction. For any population size,
    any finite queried group, any heterogeneous resource profile, and any
    dependent/asymmetric allocation-production lottery, expected group
    activity equals expected verified productive exposure whenever the
    member-specific threshold bridge holds. No 4+2 split, exchangeability,
    independence, or rational choice is assumed. -/
theorem arbitrary_group_activity_equals_productive_exposure
    {Agent : Type} (case : GroupCase Agent) :
    expectedGroupActivity case = expectedGroupProduction case := by
  exact heterogeneous_group_next_active_mass_eq_expected_productive_count
    case.group case.periodLaw case.margins case.thresholdBridge

/-- A necessary implication of the bridge: if its predicted group activity
    mass is positive, then the same case law assigns positive expected
    successful exposure to that group. -/
theorem positive_group_activity_requires_positive_productive_exposure
    {Agent : Type} (case : GroupCase Agent)
    (positiveActivity : 0 < expectedGroupActivity case) :
    0 < expectedGroupProduction case := by
  rw [← arbitrary_group_activity_equals_productive_exposure case]
  exact positiveActivity

/-- The model makes no group prediction when a member-specific threshold
    margin is not established. This refusal predicate is intentionally
    observable: it prevents substituting a homogeneous threshold or an
    anonymous lottery merely to obtain a point forecast. -/
def groupBridgeSupported {Agent : Type} (case : GroupCase Agent) : Prop :=
  ∀ agent, agent ∈ case.group.members → ThresholdCrossing (case.margins agent)

theorem group_case_bridge_is_supported {Agent : Type} (case : GroupCase Agent) :
    groupBridgeSupported case := case.thresholdBridge

end AgentMicrofoundations.GroupPrediction
