import AgentMicrofoundations.ComputationalEconomy
import AgentMicrofoundations.FiniteDynamics
import AgentMicrofoundations.AnonymousAllocation

/-!
Controlled finite-horizon mechanism counterfactuals.

This interface varies the institution while sharing one model, computational
response representation, agent identity type, initial law, production and
resource rules, and context transition. A setting may change mechanism
disclosure as well as execution; disclosure is therefore an explicit input
channel rather than being folded into the execution effect. For comparisons
with identical disclosure, Ontology.equal_disclosure_implies_equal_proposal_law
gives the exact within-period invariance result. Subsequent periods may differ
through mechanism-induced execution, production, resources, and context.
-/
namespace AgentMicrofoundations.MechanismCounterfactual

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.ComputationalEconomy
open AgentMicrofoundations.FiniteDynamics
open AgentMicrofoundations.AnonymousAllocation
open AgentMicrofoundations.AutoregressiveResponse

/-- A controlled mechanism family. Across settings only the admitted
    institution varies; the model, its autoregressive representation, agent
    identity type, initial condition/state law, production/resource technology,
    and next-condition rule are shared. -/
structure MechanismInterventionFamily
    (Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type)
    [DecidableEq Agent] [DecidableEq Proposal] where
  model : AgentEconomyModel Agent InternalState ResourceState Condition Observation
    InstitutionalSignal Opportunity Proposal Production
  constitution : ResponseKernelRepresentation model
  population : FinitePopulation Agent
  populationComplete : ∀ agent, agent ∈ population.members
  institution : Settings → AdmissibleInstitution model
  contextKernel : Condition → StateProfile Agent InternalState ResourceState →
    PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production →
      FiniteDistribution Condition
  initial : FiniteDistribution
    (Condition × StateProfile Agent InternalState ResourceState)

/-- The complete named proposal lottery under one mechanism setting. -/
def proposalLaw
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : MechanismInterventionFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (setting : Settings) (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState) :
    FiniteDistribution (ProposalProfile Agent Proposal) :=
  proposalDistribution family.model (family.institution setting).rule condition states

/-- One-round exclusion restriction for a controlled institution comparison:
if the intervention changes only how proposals are executed and discloses the
same signal to every agent at the same complete state, it cannot change the
joint proposal lottery. This is directly rejectable from proposal traces. A
violation means at least one maintained comparison condition failed (for
example, the prompt, menu, model, parser, or state was not actually held fixed);
it is not repaired by appealing to downstream execution. -/
theorem same_disclosure_preserves_first_round_proposal_law
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : MechanismInterventionFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (firstSetting secondSetting : Settings)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState)
    (sameDisclosure : ∀ agent,
      (family.institution firstSetting).rule.institutionalSignal condition states agent =
        (family.institution secondSetting).rule.institutionalSignal condition states agent) :
    proposalLaw family firstSetting condition states =
      proposalLaw family secondSetting condition states := by
  unfold proposalLaw
  exact equal_disclosure_implies_equal_proposal_law family.model
    (family.institution firstSetting).rule
    (family.institution secondSetting).rule condition states sameDisclosure

/-- Event-level form used by a CTF case model: for any predeclared proposal
event (e.g. opening a task, voting, or transferring resources), its first-
round probability is invariant under a disclosure-preserving execution-rule
intervention. The theorem places no restriction on the later execution,
production, or resource distributions. -/
theorem same_disclosure_preserves_first_round_proposal_probability
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : MechanismInterventionFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (firstSetting secondSetting : Settings)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState)
    (sameDisclosure : ∀ agent,
      (family.institution firstSetting).rule.institutionalSignal condition states agent =
        (family.institution secondSetting).rule.institutionalSignal condition states agent)
    (proposalEvent : ProposalProfile Agent Proposal → Bool) :
    eventMass (proposalLaw family firstSetting condition states) proposalEvent =
      eventMass (proposalLaw family secondSetting condition states) proposalEvent := by
  rw [same_disclosure_preserves_first_round_proposal_law family
    firstSetting secondSetting condition states sameDisclosure]

/-- Exact within-period law under one mechanism setting. All non-institutional
    kernels are shared by construction across the family. -/
def periodLaw
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : MechanismInterventionFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (setting : Settings) (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState) :=
  admissibleOnePeriodDistribution family.model (family.institution setting) condition states

/-- One transition with a selected mechanism; the common context transition
    sees the complete within-period proposal/execution/production/state tuple. -/
def transition
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : MechanismInterventionFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (setting : Settings) :
    (Condition × StateProfile Agent InternalState ResourceState) →
      FiniteDistribution
        (PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production ×
          (Condition × StateProfile Agent InternalState ResourceState)) :=
  contextConditionedTransition family.model (family.institution setting)
    family.contextKernel

/-- Exact finite-horizon counterfactual path law from the shared initial law.
    No new model or response kernel is fitted when the mechanism setting
    changes. -/
def forecast
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : MechanismInterventionFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (setting : Settings) (periods : Nat) :
    FiniteDistribution
      (List (PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production) ×
        (Condition × StateProfile Agent InternalState ResourceState)) :=
  trajectoryFromInitial (transition family setting) family.initial periods

/-- Probability of a finite-horizon event under a selected mechanism. -/
def eventProbability
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : MechanismInterventionFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (setting : Settings) (periods : Nat)
    (event : List (PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Bool) : Rat :=
  eventMass (forecast family setting periods) event

/-- Expected value of a rational-valued path statistic under a mechanism. -/
def expectedStatistic
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : MechanismInterventionFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (setting : Settings) (periods : Nat)
    (statistic : List (PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Rat) : Rat :=
  (forecast family setting periods).outcomes.foldr
    (fun outcome total => outcome.2 * statistic outcome.1 + total) 0

end AgentMicrofoundations.MechanismCounterfactual
