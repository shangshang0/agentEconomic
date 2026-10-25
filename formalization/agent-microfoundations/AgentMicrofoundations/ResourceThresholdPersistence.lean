import AgentMicrofoundations.MechanismFeedback
import AgentMicrofoundations.OpportunitySpecialization

/-!
Finite-horizon persistence derived from resource flows.

This module replaces an abstract invariant-context premise with an explicit
resource ledger specialization. A verified productive exposure and a
nonproductive exposure create different post-event balances. If later periods
apply a common nonnegative depletion, the productive balance can stay above a
fixed response threshold only for as long as its measurable resource margin
covers that depletion. The result is finite-horizon and makes no claim that
real agents use threshold responses.
-/
namespace AgentMicrofoundations.ResourceThresholdPersistence

open AgentMicrofoundations.AnonymousAllocation
open AgentMicrofoundations.MechanismFeedback
open AgentMicrofoundations.Ontology
open AgentMicrofoundations.OpportunitySpecialization

/-- Post-event balance after a productive assigned task. -/
def productivePostEventBalance (initial upkeep taskCost verifiedOutput : Int) : Int :=
  resourceAfter initial upkeep taskCost verifiedOutput

/-- Post-event balance after a nonproductive period (idle or failed outcome
    abstracted into its recorded cost). -/
def nonproductivePostEventBalance (initial upkeep nonproductiveCost : Int) : Int :=
  resourceAfter initial upkeep nonproductiveCost 0

/-- A common per-period depletion applied after the initial event. -/
def balanceAfterDepletion (balance : Int) (period depletion : Nat) : Int :=
  balance - (period * depletion : Nat)

/-- With an exact initial margin `m` above the response threshold and a
    common depletion `d` per period, threshold activity at period `t` holds
    exactly when `t*d ≤ m`. This identifies the finite resource horizon rather
    than assuming an invariant context region. -/
theorem productive_threshold_action_iff_margin_covers_depletion
    (threshold : Int) (resourceMargin period depletion : Nat) :
    thresholdResponse threshold (balanceAfterDepletion
      (threshold + (resourceMargin : Int)) period depletion) =
        decide (period * depletion ≤ resourceMargin) := by
  change decide (threshold ≤ threshold + (resourceMargin : Int) -
      (period * depletion : Nat)) = decide (period * depletion ≤ resourceMargin)
  let periodCost : Int := (period * depletion : Nat)
  have resourceIff :
      threshold ≤ threshold + (resourceMargin : Int) - periodCost ↔
        periodCost ≤ (resourceMargin : Int) := by
    dsimp [periodCost]
    omega
  have castIff : periodCost ≤ (resourceMargin : Int) ↔
      period * depletion ≤ resourceMargin := by
    dsimp [periodCost]
    exact Int.ofNat_le
  apply Bool.eq_iff_iff.mpr
  simp only [decide_eq_true_eq]
  exact resourceIff.trans castIff

/-- Sharp boundary: once cumulative depletion exceeds the initial margin,
    the productive agent's threshold action must turn off in this model. -/
theorem productive_resource_margin_exhaustion_ends_active_role
    (threshold : Int) (resourceMargin period depletion : Nat)
    (marginExhausted : resourceMargin < period * depletion) :
    thresholdResponse threshold (balanceAfterDepletion
      (threshold + (resourceMargin : Int)) period depletion) = false := by
  rw [productive_threshold_action_iff_margin_covers_depletion]
  simp [Nat.not_le.mpr marginExhausted]

/-- If the productive agent's end-of-horizon balance still covers the
    threshold, every earlier balance does too; a nonproductive balance that
    begins below threshold stays below under nonnegative depletion. -/
theorem resource_threshold_split_persists_through_horizon
    (threshold productiveStart nonproductiveStart : Int)
    (resourceMargin : Nat)
    (horizon period depletion : Nat)
    (productiveStartMatchesThresholdMargin :
      productiveStart = threshold + (resourceMargin : Int))
    (depletionCoveredByMargin : horizon * depletion ≤ resourceMargin)
    (nonproductiveInitiallyBelow : nonproductiveStart < threshold)
    (periodWithinHorizon : period ≤ horizon) :
    thresholdResponse threshold (balanceAfterDepletion productiveStart period depletion) = true ∧
      thresholdResponse threshold
        (balanceAfterDepletion nonproductiveStart period depletion) = false := by
  have depletionOrdered : period * depletion ≤ horizon * depletion :=
    Nat.mul_le_mul_right depletion periodWithinHorizon
  have castOrdered :
      (period * depletion : Nat) ≤ (horizon * depletion : Nat) := by
    exact_mod_cast depletionOrdered
  have marginCast : (horizon * depletion : Nat) ≤ (resourceMargin : Int) := by
    exact_mod_cast depletionCoveredByMargin
  have productiveMarginAtHorizon :
      threshold ≤ balanceAfterDepletion productiveStart horizon depletion := by
    rw [productiveStartMatchesThresholdMargin]
    unfold balanceAfterDepletion
    omega
  have productiveAtPeriod :
      threshold ≤ balanceAfterDepletion productiveStart period depletion := by
    unfold balanceAfterDepletion at productiveMarginAtHorizon ⊢
    omega
  have nonproductiveAtPeriod :
      balanceAfterDepletion nonproductiveStart period depletion < threshold := by
    unfold balanceAfterDepletion
    omega
  simp [thresholdResponse, productiveAtPeriod, nonproductiveAtPeriod]

/-- One verified task can seed a resource gap that yields different threshold
    responses through a computable horizon. Costs, output, and the horizon's
    common depletion are explicit case inputs. -/
theorem productive_exposure_creates_finite_horizon_role_split
    (threshold initial upkeep taskCost nonproductiveCost verifiedOutput : Int)
    (resourceMargin horizon period depletion : Nat)
    (productiveStartMatchesThresholdMargin :
      productivePostEventBalance initial upkeep taskCost verifiedOutput =
        threshold + (resourceMargin : Int))
    (depletionCoveredByMargin : horizon * depletion ≤ resourceMargin)
    (nonproductiveBelowInitially :
      nonproductivePostEventBalance initial upkeep nonproductiveCost < threshold)
    (periodWithinHorizon : period ≤ horizon) :
    thresholdResponse threshold (balanceAfterDepletion
      (productivePostEventBalance initial upkeep taskCost verifiedOutput)
      period depletion) = true ∧
    thresholdResponse threshold (balanceAfterDepletion
      (nonproductivePostEventBalance initial upkeep nonproductiveCost)
      period depletion) = false := by
  exact resource_threshold_split_persists_through_horizon threshold
    (productivePostEventBalance initial upkeep taskCost verifiedOutput)
    (nonproductivePostEventBalance initial upkeep nonproductiveCost)
    resourceMargin horizon period depletion productiveStartMatchesThresholdMargin
    depletionCoveredByMargin
    nonproductiveBelowInitially periodWithinHorizon

/-- Case event: a verified productive recipient and a nonproductive agent
    continue to exhibit different resource-threshold actions through the
    stated finite horizon. -/
def PersistentResourceRoleSplit
    {Agent : Type}
    (population : List Agent)
    (productiveProfile : Allocation Agent)
    (threshold initial upkeep taskCost nonproductiveCost verifiedOutput : Int)
    (horizon depletion : Nat) : Prop :=
  ∃ productiveAgent nonproductiveAgent,
    productiveAgent ∈ population ∧ nonproductiveAgent ∈ population ∧
    productiveProfile productiveAgent = true ∧ productiveProfile nonproductiveAgent = false ∧
    ∀ period, period ≤ horizon →
      thresholdResponse threshold (balanceAfterDepletion
        (productivePostEventBalance initial upkeep taskCost verifiedOutput)
        period depletion) ≠
      thresholdResponse threshold (balanceAfterDepletion
        (nonproductivePostEventBalance initial upkeep nonproductiveCost)
        period depletion)

/-- If every positive-mass outcome contains at least one productive recipient
    and one nonproductive agent, and the observed resource margins straddle
    the response threshold through horizon `H`, then persistent role split has
    probability one under the finite lottery. No independence or anonymity is
    required; the theorem does not identify the recipient. -/
theorem productive_lottery_predicts_finite_horizon_split_probability_one
    {Agent : Type}
    (population : List Agent)
    (lottery : FiniteDistribution (Allocation Agent))
    (isSplit : Allocation Agent → Bool)
    (threshold initial upkeep taskCost nonproductiveCost verifiedOutput : Int)
    (resourceMargin horizon depletion : Nat)
    (productiveStartMatchesThresholdMargin :
      productivePostEventBalance initial upkeep taskCost verifiedOutput =
        threshold + (resourceMargin : Int))
    (depletionCoveredByMargin : horizon * depletion ≤ resourceMargin)
    (nonproductiveBelowInitially :
      nonproductivePostEventBalance initial upkeep nonproductiveCost < threshold)
    (partialProductivity : ∀ profile weight, (profile, weight) ∈ lottery.outcomes →
      0 < weight → 0 < selectedCount population profile ∧
        selectedCount population profile < population.length)
    (classifierCorrect : ∀ profile, isSplit profile = true ↔
      PersistentResourceRoleSplit population profile threshold initial upkeep
        taskCost nonproductiveCost verifiedOutput horizon depletion) :
    eventMass lottery isSplit = 1 := by
  apply eventMass_eq_one_when_event_holds_on_positive_support
  intro profile weight member positiveWeight
  obtain ⟨productiveAgent, productiveMember, productive⟩ :=
    positive_selected_count_has_selected_witness population profile
      ((partialProductivity profile weight member positiveWeight).1)
  obtain ⟨nonproductiveAgent, nonproductiveMember, nonproductive⟩ :=
    selected_count_below_population_has_unselected_witness population profile
      ((partialProductivity profile weight member positiveWeight).2)
  have split : PersistentResourceRoleSplit population profile threshold initial upkeep
      taskCost nonproductiveCost verifiedOutput horizon depletion := by
    refine ⟨productiveAgent, nonproductiveAgent, productiveMember, nonproductiveMember,
      productive, nonproductive, ?_⟩
    intro period periodWithinHorizon
    have responsePair := productive_exposure_creates_finite_horizon_role_split
      threshold initial upkeep taskCost nonproductiveCost verifiedOutput
      resourceMargin horizon period depletion productiveStartMatchesThresholdMargin
      depletionCoveredByMargin nonproductiveBelowInitially periodWithinHorizon
    rw [responsePair.1, responsePair.2]
    decide
  exact (classifierCorrect profile).2 split

end AgentMicrofoundations.ResourceThresholdPersistence
