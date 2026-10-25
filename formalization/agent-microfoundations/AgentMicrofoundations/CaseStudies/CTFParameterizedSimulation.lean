import AgentMicrofoundations.ScenarioSimulation

/-!
Explicit design surface for zero-API CTF counterfactual simulation.

The design record contains controllable environment and institution settings.
The scenario family supplies the computational response, execution,
production, resource-update, and context-transition laws conditional on each
design. The separation is intentional: changing a vote rule or energy price
does not, by itself, imply a direction for an agent's proposal probability.
Once a family is supplied, the existing exact finite-horizon simulator
calculates outcome probabilities and expectations using rational arithmetic.

This is a front-end for a case model, not a behavioral law. A forecast is a
point prediction only when the supplied response and production laws are
identified or frozen. A family of admissible laws can instead be evaluated
one by one to produce an identified range. No agent-world execution or API
call is needed for either calculation.
-/
namespace AgentMicrofoundations.CaseStudies.CTFParameterizedSimulation

open AgentMicrofoundations.AnonymousAllocation
open AgentMicrofoundations.FiniteDynamics
open AgentMicrofoundations.Ontology
open AgentMicrofoundations.ScenarioSimulation

inductive CTFVoteRule where
  | absent
  | plurality
  | majority
  deriving DecidableEq, Repr

/-- Whether energy is an enforceable survival constraint or a symbolic balance.
    This is a backend rule, not an agent preference. -/
inductive CTFEnergySemantics where
  | operational
  | symbolic
  deriving DecidableEq, Repr

/-- Some Authority World designs meter model requests with a hard quota;
    Authority World v2 CTF instead has no quota. Keeping this switch explicit
    prevents importing the v1 resource rule into a v2 case. -/
inductive CTFQuotaSemantics where
  | unmetered
  | finite
  deriving DecidableEq, Repr

/-- When the executable backend enforces the survival threshold. The setting
    is distinct from the accounting identity: event-time and settlement-time
    enforcement can produce different path laws under the same net energy. -/
inductive CTFDeathCheck where
  | authorityWorldV2
  | eachEvent
  | periodSettlement
  | disabled
  deriving DecidableEq, Repr

/-- Whether institutional wording frames the office as human-like,
    institution-neutral, or explicitly encoded. This is an input condition and
    must not be silently merged with the executable allocation rule. -/
inductive CTFInstitutionSemantics where
  | humanFramed
  | neutral
  | encoded
  deriving DecidableEq, Repr

/-- Versioned goal text used by the experiment. -/
inductive CTFObjectivePrompt where
  | survival
  | none
  deriving DecidableEq, Repr

/-- How the office-holder is selected. Office selection and task allocation
    are separate institutional choices in the experimental backend. -/
inductive CTFOfficeSelection where
  | none
  | elected
  | random
  deriving DecidableEq, Repr

/-- Assignment may be made by the office-holder or by executable platform
    code. The platform-random case still has an explicit, seed-conditioned
    kernel in the scenario family. -/
inductive CTFAllocationRule where
  | agentDiscretion
  | platformRandom
  | platformRule
  deriving DecidableEq, Repr

/-- Governance changes which institutional stage is active. The stage is a
    design control; agent participation in that stage remains a response law. -/
inductive CTFGovernanceMode where
  | resourcePack
  | taskAssignment
  deriving DecidableEq, Repr

/-- Optional allocation audit rule. An audit can constrain execution, but does
    not by itself imply how an agent proposes or votes. -/
inductive CTFAuditMode where
  | none
  | allocationFairnessAttestation
  deriving DecidableEq, Repr

structure CTFResourcePack where
  id : Nat
  totalEnergy : Rat
  leaderTake : Rat
  deriving DecidableEq, Repr

/-- Per-task operational controls, kept distinct from the agent's probability
    of attempting or solving that task. `workTicks` is a required duration
    proxy; a case can refine it to a richer time-and-tool model. -/
structure CTFTaskControl (Task : Type) where
  task : Task
  reward : Rat
  openCost : Rat
  workTicks : Nat
  tier : Nat

/-- Controls observed or intervened on in CTF-style agent-economy experiments.
    Time is in the experiment's chosen integer tick; energy and costs use
    exact rationals. Task values may carry tier, difficulty, and reward
    attributes. The finite identity list is explicit and is not pre-partitioned
    into groups. -/
structure CTFDesign (Agent Task : Type) where
  population : FinitePopulation Agent
  officeSelection : CTFOfficeSelection
  allocationRule : CTFAllocationRule
  voteRule : CTFVoteRule
  governanceMode : CTFGovernanceMode
  auditMode : CTFAuditMode
  offeredTasks : List (CTFTaskControl Task)
  /-- Wall-clock horizon and phase boundaries in integer ticks. Keeping units
      explicit avoids silently treating API latency as agent cognition. -/
  dayTicks : Nat
  prestartTicks : Nat
  campaignOpensAt : Nat
  campaignClosesAt : Nat
  votingOpensAt : Nat
  votingClosesAt : Nat
  assignmentOpensAt : Nat
  assignmentClosesAt : Nat
  productionOpensAt : Nat
  productionClosesAt : Nat
  registrationOpensAt : Nat
  idleCognitionTicks : Nat
  maxSleepTicks : Nat
  /-- Backend execution limits. These may affect whether a proposal can be
      executed or verified; they do not specify the agent's proposal law. -/
  taskTimeoutTicks : Nat
  taskOutputLimit : Nat
  taskPrewarmTicks : Nat
  taskLifetimePeriods : Nat
  horizonPeriods : Nat
  seedId : Nat
  maxAssignments : Nat
  maxDistinctRecipients : Nat
  correctWinnerLimit : Nat
  initialEnergy : Agent → Rat
  quotaSemantics : CTFQuotaSemantics
  initialApiQuota : Agent → Nat
  modelRequestEnergyCost : Rat
  basalEnergyDrain : Rat
  taxRate : Rat
  resourcePacks : List CTFResourcePack
  energySemantics : CTFEnergySemantics
  deathCheck : CTFDeathCheck
  transfersEnabled : Bool
  transferFee : Rat
  /-- Versioned condition identifier for prompt, objective, or task protocol.
      It is an input label, not a preference or behavioral assumption. Protocol
      and runtime identifiers retain the associated implementation versions. -/
  conditionId : Nat
  protocolVersion : Nat
  runtimeVersion : Nat
  institutionSemantics : CTFInstitutionSemantics
  objectivePrompt : CTFObjectivePrompt
  taskSuiteId : Nat

/-- The configuration validator's temporal ordering, expressed as a
    falsifiable applicability condition instead of a hidden constructor
    restriction. Different platforms may use another validator. -/
def validCTFClock {Agent TaskType : Type}
    (design : CTFDesign Agent TaskType) : Prop :=
  design.prestartTicks ≤ design.campaignOpensAt ∧
    design.campaignOpensAt < design.campaignClosesAt ∧
    design.campaignClosesAt ≤ design.votingOpensAt ∧
    design.votingOpensAt < design.votingClosesAt ∧
    design.votingClosesAt ≤ design.assignmentOpensAt ∧
    design.assignmentOpensAt < design.assignmentClosesAt ∧
    design.assignmentClosesAt ≤ design.productionOpensAt ∧
    design.productionOpensAt < design.productionClosesAt ∧
    design.productionClosesAt ≤ design.registrationOpensAt ∧
    design.registrationOpensAt < design.dayTicks ∧
    design.votingOpensAt < design.registrationOpensAt

/-- All economically relevant non-behavioral controls that can be varied in
    the Authority World v2 design are exposed here. A concrete scenario family
    must connect each field to the response input, execution, production,
    accounting, or state-transition law it actually changes. -/
def designTaskCount {Agent TaskType : Type}
    (design : CTFDesign Agent TaskType) : Nat :=
  design.offeredTasks.length

/-- A response family is an explicit conditional law over the complete agent
    input signature. This prevents the interface from treating unobserved
    proposal behavior as if it were implied by environment controls. A case
    may construct this signature from archived requests, or specify a frozen
    counterfactual input generator before collecting a new trace. -/
structure CTFInputSignature (Agent InternalState Condition : Type) where
  agent : Agent
  state : InternalState
  condition : Condition
  day : Nat
  elapsedTicks : Nat
  /-- The action/tool interface actually exposed in the assembled model
      request. This is distinct from the opportunity menu (which task handles
      are visible) and from the institution's execution rule (which submitted
      action is accepted). An intervention that changes this list changes the
      response input even if its downstream allocator code is untouched. -/
  visibleToolIds : List Nat
  visibleTaskIds : List Nat
  visibleTaskStates : List Nat
  visibleEnergy : Rat
  tokenBudget : Nat
  /-- Stable fingerprints for the exact assembled prompt, parser, tool schema,
      and backend-visible observation. A case can reconstruct these from the
      archived request plus versioned runtime sources. -/
  assembledInputId : Nat
  parserVersion : Nat
  toolSchemaVersion : Nat
  protocolVersion : Nat
  runtimeVersion : Nat

/-- A CTF family is the existing general scenario simulator indexed directly
    by this explicit design record. The population equality prevents the
    design surface and the simulated identity boundary from silently diverging.
    The scenario's economy and transition kernels remain supplied, inspectable
    case objects and may use every design field. -/
structure CTFScenarioFamily
    (Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type)
    [DecidableEq Agent] [DecidableEq Proposal] where
  scenario : FiniteScenarioFamily (CTFDesign Agent Task) Agent InternalState
    ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production
  populationMatchesDesign : ∀ design,
    (scenario.population design).members = design.population.members

/-- Exact finite-horizon trajectory law for one CTF design, including the
    sequence of per-period proposal, execution, production, resource, and state
    outcomes encoded by the scenario. -/
def forecast
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : CTFScenarioFamily Agent InternalState ResourceState Condition Observation
      InstitutionalSignal Opportunity Proposal Production Task)
    (design : CTFDesign Agent Task) (periods : Nat) :=
  ScenarioSimulation.forecast family.scenario design periods

/-- Numeric probability for any declared finite-horizon CTF outcome event. -/
def eventProbability
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : CTFScenarioFamily Agent InternalState ResourceState Condition Observation
      InstitutionalSignal Opportunity Proposal Production Task)
    (design : CTFDesign Agent Task) (periods : Nat)
    (event : List (FiniteDynamics.PeriodOutcome Agent InternalState ResourceState
        Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Bool) : Rat :=
  ScenarioSimulation.eventProbability family.scenario design periods event

/-- Candidate-law envelope for one design. Each entry is a complete, explicit
    response/execution/production/context law, not a sample draw. The range is
    a model-uncertainty envelope, not a statistical confidence interval. An
    empty candidate set returns `none`, forcing the caller to reject a point
    forecast instead of silently inventing a behavioral law. -/
def candidateEventProbabilityRange
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (families : List (CTFScenarioFamily Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production Task))
    (design : CTFDesign Agent Task) (periods : Nat)
    (event : List (FiniteDynamics.PeriodOutcome Agent InternalState ResourceState
        Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Bool) :
    Option (Rat × Rat) :=
  let probabilities := families.map fun family =>
    eventProbability family design periods event
  match probabilities with
  | [] => none
  | first :: rest =>
      some (rest.foldl min first, rest.foldl max first)

/-- Numeric expectation for any rational-valued trajectory statistic. This is
    the API-free parameter scan entry point after the case laws are frozen. -/
def expectedStatistic
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : CTFScenarioFamily Agent InternalState ResourceState Condition Observation
      InstitutionalSignal Opportunity Proposal Production Task)
    (design : CTFDesign Agent Task) (periods : Nat)
    (statistic : List (FiniteDynamics.PeriodOutcome Agent InternalState ResourceState
        Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Rat) : Rat :=
  ScenarioSimulation.expectedStatistic family.scenario design periods statistic

/-- Evaluate an explicit finite counterfactual design grid in one pass. The
    returned rational values are exact under the supplied scenario kernels;
    no Monte Carlo approximation or model API call is used. -/
def sweepEventProbability
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : CTFScenarioFamily Agent InternalState ResourceState Condition Observation
      InstitutionalSignal Opportunity Proposal Production Task)
    (designs : List (CTFDesign Agent Task)) (periods : Nat)
    (event : List (FiniteDynamics.PeriodOutcome Agent InternalState ResourceState
        Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Bool) :
    List (CTFDesign Agent Task × Rat) :=
  designs.map fun design =>
    (design, eventProbability family design periods event)

/-- Exact expected-statistic counterpart to `sweepEventProbability`. A caller
    can return any statistic of the full trajectory, including production,
    survival, transfers, active-role counts, or resource inequality. -/
def sweepExpectedStatistic
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : CTFScenarioFamily Agent InternalState ResourceState Condition Observation
      InstitutionalSignal Opportunity Proposal Production Task)
    (designs : List (CTFDesign Agent Task)) (periods : Nat)
    (statistic : List (FiniteDynamics.PeriodOutcome Agent InternalState ResourceState
        Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Rat) :
    List (CTFDesign Agent Task × Rat) :=
  designs.map fun design =>
    (design, expectedStatistic family design periods statistic)

/-- Candidate-law envelope for a rational-valued outcome statistic. The laws
    may be dependent across agents and periods; each candidate is evaluated by
    the exact finite-horizon path sum before the lower/upper envelope is taken.
    The caller must state which laws are admissible and why. -/
def candidateExpectedStatisticRange
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (families : List (CTFScenarioFamily Agent InternalState ResourceState Condition
      Observation InstitutionalSignal Opportunity Proposal Production Task))
    (design : CTFDesign Agent Task) (periods : Nat)
    (statistic : List (FiniteDynamics.PeriodOutcome Agent InternalState ResourceState
        Opportunity Proposal Production) ×
      (Condition × StateProfile Agent InternalState ResourceState) → Rat) :
    Option (Rat × Rat) :=
  let expectations := families.map fun family =>
    expectedStatistic family design periods statistic
  match expectations with
  | [] => none
  | first :: rest =>
      some (rest.foldl min first, rest.foldl max first)

/-- The explicit design population is exactly the one used in the simulation. -/
theorem simulated_population_is_design_population
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal
      Opportunity Proposal Production Task : Type}
    [DecidableEq Agent] [DecidableEq Proposal]
    (family : CTFScenarioFamily Agent InternalState ResourceState Condition Observation
      InstitutionalSignal Opportunity Proposal Production Task)
    (design : CTFDesign Agent Task) :
    (family.scenario.population design).members = design.population.members :=
  family.populationMatchesDesign design

/-- Parameter scan with population and task types allowed to vary by setting.
    This is the CTF front-end for comparing, for example, 3-, 4-, 5-, or
    6-agent designs without padding one fixed population. -/
structure IndexedCTFScenarioFamily (Settings : Type) where
  Task : Settings → Type
  scenario : IndexedFiniteScenarioFamily Settings
  controls : ∀ setting, CTFDesign (scenario.Agent setting) (Task setting)
  populationMatchesDesign : ∀ setting,
    letI := scenario.agentDecidable setting
    (scenario.population setting).members = (controls setting).population.members

/-- Exact setting-specific path law when population size or task type changes
    across the parameter sweep. -/
def indexedForecast
    {Settings : Type} (family : IndexedCTFScenarioFamily Settings)
    (setting : Settings) (periods : Nat) :=
  ScenarioSimulation.indexedForecast family.scenario setting periods

/-- Setting-specific event probability in a population-varying CTF sweep. -/
def indexedEventProbability
    {Settings : Type} (family : IndexedCTFScenarioFamily Settings)
    (setting : Settings) (periods : Nat)
    (event : List (FiniteDynamics.PeriodOutcome (family.scenario.Agent setting)
        (family.scenario.InternalState setting) (family.scenario.ResourceState setting)
        (family.scenario.Opportunity setting) (family.scenario.Proposal setting)
        (family.scenario.Production setting)) ×
      (family.scenario.Condition setting ×
        StateProfile (family.scenario.Agent setting)
          (family.scenario.InternalState setting)
          (family.scenario.ResourceState setting)) → Bool) : Rat :=
  ScenarioSimulation.indexedEventProbability family.scenario setting periods event

/-- Expected statistic in one population-varying design point. -/
def indexedExpectedStatistic
    {Settings : Type} (family : IndexedCTFScenarioFamily Settings)
    (setting : Settings) (periods : Nat)
    (statistic : List (FiniteDynamics.PeriodOutcome (family.scenario.Agent setting)
        (family.scenario.InternalState setting) (family.scenario.ResourceState setting)
        (family.scenario.Opportunity setting) (family.scenario.Proposal setting)
        (family.scenario.Production setting)) ×
      (family.scenario.Condition setting ×
        StateProfile (family.scenario.Agent setting)
          (family.scenario.InternalState setting)
          (family.scenario.ResourceState setting)) → Rat) : Rat :=
  ScenarioSimulation.indexedExpectedStatistic family.scenario setting periods statistic

/-- The parameter record and simulated population stay aligned at every point
    of a cross-population parameter scan. -/
theorem indexed_simulated_population_is_design_population
    {Settings : Type} (family : IndexedCTFScenarioFamily Settings)
    (setting : Settings) :
    letI := family.scenario.agentDecidable setting
    (family.scenario.population setting).members =
      (family.controls setting).population.members :=
  family.populationMatchesDesign setting

end AgentMicrofoundations.CaseStudies.CTFParameterizedSimulation
