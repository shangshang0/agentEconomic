import AgentMicrofoundations.ComputationalEconomy
import AgentMicrofoundations.FiniteDynamics
import AgentMicrofoundations.AnonymousAllocation

/-!
Finite scenario simulator for parameterized agent-economy case studies.

An instance can encode arbitrary tracked populations and settings. Static design
choices (for example vote rule, task supply, time window, token price, energy
costs, or a resource regime) are recorded in `settings` and compiled into the
model, response, mechanism, production, accounting, and context-transition
kernels. Nothing here assumes rational choice, independent agents, anonymity,
or a fixed population partition. Numerical forecasts are exact rational laws
once those kernels are supplied; the simulator does not infer a missing
behavioral response law from a list of environment parameters.
-/
namespace AgentMicrofoundations.ScenarioSimulation

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.ComputationalEconomy
open AgentMicrofoundations.FiniteDynamics
open AgentMicrofoundations.AnonymousAllocation

/-- A parameterized family of finite-horizon scenarios. Every setting selects
    a fully specified agent economy, context transition, and initial law.
    `Settings` is application specific: a CTF instance may include population
    size, vote rule, task supply, time windows, energy costs, and production
    rules; another platform may use a different record. The type does not
    impose restrictions on these parameters or require every parameter to
    affect every law. -/
structure FiniteScenarioFamily
    (Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type)
    [DecidableEq Agent] [DecidableEq Proposal] where
  economy : Settings → ComputationalAgentEconomy Agent InternalState ResourceState Condition
    Observation InstitutionalSignal Opportunity Proposal Production
  population : Settings → FinitePopulation Agent
  /-- Every member of the agent identity type is in the explicit finite
      population list, so the list defines the actual simulation boundary. -/
  populationComplete : ∀ settings agent, agent ∈ (population settings).members
  contextKernel : Settings → Condition → StateProfile Agent InternalState ResourceState →
    PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production →
      FiniteDistribution Condition
  initial : Settings → FiniteDistribution
    (Condition × StateProfile Agent InternalState ResourceState)

/-- The number of modeled subjects is the cardinality of the agent identity
    type. This keeps the population control connected to the simulated domain. -/
def populationSize
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (_family : FiniteScenarioFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (settings : Settings) : Nat :=
  (_family.population settings).members.length

/-- One transition of the configured scenario, including proposals, mechanism
    execution, production, resource/internal-state updates, and the next
    condition. -/
def transition
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : FiniteScenarioFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production) :
    Settings →
    (Condition × StateProfile Agent InternalState ResourceState) →
      FiniteDistribution
        (PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production ×
          (Condition × StateProfile Agent InternalState ResourceState)) :=
  fun settings => contextConditionedTransition
    (family.economy settings).model (family.economy settings).institution
    (family.contextKernel settings)

/-- Exact joint law over the ordered period outcomes and terminal condition /
    population state after `periods` transitions. This is the numeric scenario
    calculation: finite support and rational weights are preserved throughout. -/
def forecast
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : FiniteScenarioFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (settings : Settings) (periods : Nat) :
    FiniteDistribution
      (List (PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production) ×
        (Condition × StateProfile Agent InternalState ResourceState)) :=
  trajectoryFromInitial (transition family settings) (family.initial settings) periods

/-- Probability of any finite-horizon economic event under the scenario's
    exact forecast law. The event can refer to trajectories, named agents,
    group totals, resource thresholds, verified production, or terminal states. -/
def eventProbability
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : FiniteScenarioFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (settings : Settings) (periods : Nat)
    (event : List (PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Bool) : Rat :=
  eventMass (forecast family settings periods) event

/-- Exact expected value of any rational-valued trajectory statistic. -/
def expectedStatistic
    {Settings Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : FiniteScenarioFamily Settings Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production)
    (settings : Settings) (periods : Nat)
    (statistic : List (PeriodOutcome Agent InternalState ResourceState Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Rat) : Rat :=
  (forecast family settings periods).outcomes.foldr
    (fun outcome total => outcome.2 * statistic outcome.1 + total) 0

/-- A setting-indexed family in which the agent type itself may vary with the
    design. This is the interface for genuine population-size sweeps: a setting
    chooses the complete tracked population as `Agent setting := Fin n`, rather
    than encoding a smaller society as inactive members of one fixed
    super-population. Opportunity, proposal,
    resource, condition, and production types may also vary across settings. -/
structure IndexedFiniteScenarioFamily (Settings : Type) where
  Agent : Settings → Type
  agentDecidable : ∀ setting, DecidableEq (Agent setting)
  population : ∀ setting, letI := agentDecidable setting; FinitePopulation (Agent setting)
  populationComplete : ∀ setting agent,
    letI := agentDecidable setting
    agent ∈ (population setting).members
  InternalState : Settings → Type
  ResourceState : Settings → Type
  Condition : Settings → Type
  Observation : Settings → Type
  InstitutionalSignal : Settings → Type
  Opportunity : Settings → Type
  Proposal : Settings → Type
  Production : Settings → Type
  proposalDecidable : ∀ setting, DecidableEq (Proposal setting)
  economy : ∀ setting,
    letI := proposalDecidable setting
    ComputationalAgentEconomy (Agent setting) (InternalState setting)
      (ResourceState setting) (Condition setting) (Observation setting)
      (InstitutionalSignal setting) (Opportunity setting) (Proposal setting)
      (Production setting)
  contextKernel : ∀ setting,
    Condition setting →
      StateProfile (Agent setting) (InternalState setting) (ResourceState setting) →
      PeriodOutcome (Agent setting) (InternalState setting) (ResourceState setting)
        (Opportunity setting) (Proposal setting) (Production setting) →
        FiniteDistribution (Condition setting)
  initial : ∀ setting,
    FiniteDistribution
      (Condition setting ×
        StateProfile (Agent setting) (InternalState setting) (ResourceState setting))

/-- The modeled population size at one design point. -/
def indexedPopulationSize
    {Settings : Type}
    (family : IndexedFiniteScenarioFamily Settings)
    (setting : Settings) : Nat :=
  (family.population setting).members.length

/-- One setting-specific transition for an indexed family. -/
def indexedTransition
    {Settings : Type}
    (family : IndexedFiniteScenarioFamily Settings)
    (setting : Settings) :
    (family.Condition setting ×
      StateProfile (family.Agent setting) (family.InternalState setting)
        (family.ResourceState setting)) →
      FiniteDistribution
        (PeriodOutcome (family.Agent setting) (family.InternalState setting)
            (family.ResourceState setting) (family.Opportunity setting)
            (family.Proposal setting) (family.Production setting) ×
          (family.Condition setting ×
            StateProfile (family.Agent setting) (family.InternalState setting)
              (family.ResourceState setting))) := by
  letI := family.proposalDecidable setting
  exact contextConditionedTransition
    (family.economy setting).model (family.economy setting).institution
    (family.contextKernel setting)

/-- Finite-horizon exact law for a setting whose population size and outcome
    types may differ from every other setting in the family. -/
def indexedForecast
    {Settings : Type}
    (family : IndexedFiniteScenarioFamily Settings)
    (setting : Settings) (periods : Nat) :=
  trajectoryFromInitial (indexedTransition family setting)
    (family.initial setting) periods

/-- Event probability in one setting of an indexed sweep. -/
def indexedEventProbability
    {Settings : Type}
    (family : IndexedFiniteScenarioFamily Settings)
    (setting : Settings) (periods : Nat)
    (event : List (PeriodOutcome (family.Agent setting) (family.InternalState setting)
        (family.ResourceState setting) (family.Opportunity setting)
        (family.Proposal setting) (family.Production setting)) ×
      (family.Condition setting ×
        StateProfile (family.Agent setting) (family.InternalState setting)
          (family.ResourceState setting)) → Bool) : Rat :=
  eventMass (indexedForecast family setting periods) event

/-- Exact expected value of a rational-valued trajectory statistic in one
    setting of an indexed sweep. This supports direct comparisons of expected
    production, resource levels, concentration, survival, or role counts even
    when the population type changes with the setting. -/
def indexedExpectedStatistic
    {Settings : Type}
    (family : IndexedFiniteScenarioFamily Settings)
    (setting : Settings) (periods : Nat)
    (statistic : List (PeriodOutcome (family.Agent setting)
        (family.InternalState setting) (family.ResourceState setting)
        (family.Opportunity setting) (family.Proposal setting)
        (family.Production setting)) ×
      (family.Condition setting × StateProfile (family.Agent setting)
        (family.InternalState setting) (family.ResourceState setting)) → Rat) : Rat :=
  (indexedForecast family setting periods).outcomes.foldr
    (fun outcome total => outcome.2 * statistic outcome.1 + total) 0

end AgentMicrofoundations.ScenarioSimulation
