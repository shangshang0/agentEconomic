import Std

/-!
Core ontology for agent-centered economics.

Foundational separation (definitions, not empirical laws): `Agent` indexes
the tracked computational subjects; `AgentState` separates dynamic internal
state from resources; `Condition` is an input/state of the model; response, production, and state-update kernels are model objects; `MechanismRule` is a
separately defined institutional rule. Compatibility is a relation on a model-rule
pair, not part of either object's identity. Mechanism disclosure can enter the
response input without identifying response with execution. This interface
does not derive a response law from model weights, assume rationality, or
assert that resources bind in every application.

Finite distributions use exact rational weights summing to one. Their
conditional composition is normalized by the chain rule; dependence across
agents is represented by joint kernels rather than ruled out by product
assumptions. These probability structures are formal tools: their application
to a concrete agent economy still requires identified or explicitly posited
conditional laws.
-/
namespace AgentMicrofoundations.Ontology

def mass {α : Type} : List (α × Rat) → Rat
  | [] => 0
  | (_, weight) :: rest => weight + mass rest

def scaleEntries {α : Type} (factor : Rat) (xs : List (α × Rat)) :
    List (α × Rat) :=
  xs.map fun outcome => (outcome.1, factor * outcome.2)

def mapEntries {α β : Type} (f : α → β) (xs : List (α × Rat)) :
    List (β × Rat) :=
  xs.map fun outcome => (f outcome.1, outcome.2)

def bindEntries {α β : Type} : List (α × Rat) →
    (α → List (β × Rat)) → List (β × Rat)
  | [], _ => []
  | (value, weight) :: rest, kernel =>
      scaleEntries weight (kernel value) ++ bindEntries rest kernel

def bindMass {α β : Type} : List (α × Rat) →
    (α → List (β × Rat)) → Rat
  | [], _ => 0
  | (value, weight) :: rest, kernel =>
      weight * mass (kernel value) + bindMass rest kernel

theorem mass_append {α : Type} (xs ys : List (α × Rat)) :
    mass (xs ++ ys) = mass xs + mass ys := by
  induction xs with
  | nil =>
      change mass ys = 0 + mass ys
      exact (Rat.zero_add _).symm
  | cons x xs ih =>
      rcases x with ⟨a, w⟩
      change w + mass (xs ++ ys) = (w + mass xs) + mass ys
      rw [ih]
      exact (Rat.add_assoc _ _ _).symm

theorem mass_scaleEntries {α : Type} (factor : Rat) (xs : List (α × Rat)) :
    mass (scaleEntries factor xs) = factor * mass xs := by
  induction xs with
  | nil => simp [mass, scaleEntries]
  | cons outcome rest ih =>
      rcases outcome with ⟨value, weight⟩
      change factor * weight + mass (scaleEntries factor rest) =
        factor * (weight + mass rest)
      rw [ih, Rat.mul_add]

theorem mass_mapEntries {α β : Type} (f : α → β) (xs : List (α × Rat)) :
    mass (mapEntries f xs) = mass xs := by
  induction xs with
  | nil => rfl
  | cons outcome rest ih =>
      rcases outcome with ⟨value, weight⟩
      exact congrArg (fun total : Rat => weight + total) ih

theorem mass_bindEntries {α β : Type} (xs : List (α × Rat))
    (kernel : α → List (β × Rat)) :
    mass (bindEntries xs kernel) = bindMass xs kernel := by
  induction xs with
  | nil => rfl
  | cons first rest ih =>
      rcases first with ⟨value, weight⟩
      change mass (scaleEntries weight (kernel value) ++ bindEntries rest kernel) =
        weight * mass (kernel value) + bindMass rest kernel
      rw [mass_append, mass_scaleEntries, ih]

theorem bindMass_eq_mass {α β : Type} (xs : List (α × Rat))
    (kernel : α → List (β × Rat))
    (kernelNormalized : ∀ value, mass (kernel value) = 1) :
    bindMass xs kernel = mass xs := by
  induction xs with
  | nil => rfl
  | cons first rest ih =>
      rcases first with ⟨value, weight⟩
      change weight * mass (kernel value) + bindMass rest kernel =
        weight + mass rest
      rw [kernelNormalized value, Rat.mul_one, ih]

theorem bindEntries_nonnegative {α β : Type}
    (xs : List (α × Rat)) (kernel : α → List (β × Rat))
    (inputNonnegative : ∀ value weight, (value, weight) ∈ xs → 0 ≤ weight)
    (kernelNonnegative : ∀ input value weight,
      (value, weight) ∈ kernel input → 0 ≤ weight) :
    ∀ value weight, (value, weight) ∈ bindEntries xs kernel → 0 ≤ weight := by
  induction xs with
  | nil => simp [bindEntries]
  | cons first rest ih =>
      rcases first with ⟨input, inputWeight⟩
      intro value weight member
      change (value, weight) ∈
        scaleEntries inputWeight (kernel input) ++ bindEntries rest kernel at member
      rcases List.mem_append.mp member with left | right
      · unfold scaleEntries at left
        rcases List.mem_map.mp left with ⟨outcome, inKernel, equal⟩
        rcases outcome with ⟨outValue, outWeight⟩
        have hPair := Prod.mk.inj equal
        rcases hPair with ⟨hvalue, hweight⟩
        subst value
        subst weight
        apply Rat.mul_nonneg
        · exact inputNonnegative input inputWeight (by simp)
        · exact kernelNonnegative input outValue outWeight inKernel
      · exact ih (fun v w hv => inputNonnegative v w (by simp [hv]))
          value weight right

/-- Exact finite probability distribution with rational point masses. Duplicate
    outcomes are allowed and their masses add when interpreting events. -/
structure FiniteDistribution (α : Type) where
  outcomes : List (α × Rat)
  nonnegative : ∀ value weight, (value, weight) ∈ outcomes → 0 ≤ weight
  normalized : mass outcomes = 1

def Supports {α : Type} (distribution : FiniteDistribution α) (value : α) : Prop :=
  ∃ weight, (value, weight) ∈ distribution.outcomes ∧ 0 < weight

/-- Probability mass assigned to an event in a finite distribution. -/
def eventMass {α : Type} (distribution : FiniteDistribution α) (event : α → Bool) : Rat :=
  distribution.outcomes.foldr
    (fun outcome total => if event outcome.1 then outcome.2 + total else total) 0

def eventMassEntries {α : Type} (outcomes : List (α × Rat))
    (event : α → Bool) : Rat :=
  outcomes.foldr
    (fun outcome total => if event outcome.1 then outcome.2 + total else total) 0

def mapDistribution {α β : Type} (f : α → β)
    (distribution : FiniteDistribution α) : FiniteDistribution β := by
  refine ⟨mapEntries f distribution.outcomes, ?_, ?_⟩
  · intro value weight member
    unfold mapEntries at member
    rcases List.mem_map.mp member with ⟨outcome, inDistribution, equal⟩
    rcases outcome with ⟨source, sourceWeight⟩
    have hPair := Prod.mk.inj equal
    rcases hPair with ⟨_, hweight⟩
    subst weight
    exact distribution.nonnegative source sourceWeight inDistribution
  · rw [mass_mapEntries]
    exact distribution.normalized

theorem eventMassEntries_mapEntries {α β : Type} (f : α → β)
    (outcomes : List (α × Rat)) (event : β → Bool) :
    eventMassEntries (mapEntries f outcomes) event =
      eventMassEntries outcomes (fun value => event (f value)) := by
  induction outcomes with
  | nil => rfl
  | cons outcome rest ih =>
      rcases outcome with ⟨value, weight⟩
      have tailEquality :
          List.foldr (fun outcome total =>
            if event outcome.1 then outcome.2 + total else total) 0
              (List.map (fun outcome => (f outcome.1, outcome.2)) rest) =
          List.foldr (fun outcome total =>
            if event (f outcome.1) then outcome.2 + total else total) 0 rest := by
        simpa [eventMassEntries, mapEntries] using ih
      simp only [eventMassEntries, mapEntries, List.map_cons, List.foldr_cons]
      cases event (f value) <;> simp [tailEquality]

/-- Pushforward preserves event probabilities exactly. This probability-kernel
    identity belongs to the ontology layer because autoregressive responses,
    mechanisms, and allocations all compose by pushforward. -/
theorem eventMass_mapDistribution {α β : Type} (f : α → β)
    (distribution : FiniteDistribution α) (event : β → Bool) :
    eventMass (mapDistribution f distribution) event =
      eventMass distribution (fun value => event (f value)) := by
  change eventMassEntries (mapEntries f distribution.outcomes) event =
    eventMassEntries distribution.outcomes (fun value => event (f value))
  exact eventMassEntries_mapEntries f distribution.outcomes event

theorem supports_mapDistribution_of_supports {α β : Type}
    (f : α → β) (distribution : FiniteDistribution α) (input : α)
    (inputSupported : Supports distribution input) :
    Supports (mapDistribution f distribution) (f input) := by
  rcases inputSupported with ⟨weight, member, positive⟩
  refine ⟨weight, ?_, positive⟩
  change (f input, weight) ∈ mapEntries f distribution.outcomes
  exact List.mem_map.mpr ⟨(input, weight), member, rfl⟩

def bindDistribution {α β : Type} (distribution : FiniteDistribution α)
    (kernel : α → FiniteDistribution β) : FiniteDistribution β := by
  refine ⟨bindEntries distribution.outcomes (fun value => (kernel value).outcomes), ?_, ?_⟩
  · exact bindEntries_nonnegative distribution.outcomes
      (fun value => (kernel value).outcomes) distribution.nonnegative
      (fun input => (kernel input).nonnegative)
  · rw [mass_bindEntries, bindMass_eq_mass]
    · exact distribution.normalized
    · intro value
      exact (kernel value).normalized

theorem bindEntries_contains_supported_pair {α β : Type}
    (outcomes : List (α × Rat)) (kernel : α → List (β × Rat))
    (input : α) (inputWeight : Rat) (output : β) (outputWeight : Rat)
    (inputMember : (input, inputWeight) ∈ outcomes)
    (outputMember : (output, outputWeight) ∈ kernel input) :
    (output, inputWeight * outputWeight) ∈ bindEntries outcomes kernel := by
  induction outcomes with
  | nil => simp at inputMember
  | cons head rest ih =>
      rcases head with ⟨headValue, headWeight⟩
      simp only [List.mem_cons] at inputMember
      rcases inputMember with headMember | restMember
      · have components := Prod.mk.inj headMember
        rcases components with ⟨rfl, rfl⟩
        change (output, inputWeight * outputWeight) ∈
          scaleEntries inputWeight (kernel input) ++ bindEntries rest kernel
        apply List.mem_append.mpr
        left
        unfold scaleEntries
        apply List.mem_map.mpr
        exact ⟨(output, outputWeight), outputMember, rfl⟩
      · change (output, inputWeight * outputWeight) ∈
          scaleEntries headWeight (kernel headValue) ++ bindEntries rest kernel
        apply List.mem_append.mpr
        right
        exact ih restMember

/-- Support composes through a finite conditional kernel: any supported input
    followed by a conditionally supported output has positive support in the
    joint bind distribution. The resulting path weight is the product of the
    two conditional weights. -/
theorem supports_bindDistribution_of_supports {α β : Type}
    (distribution : FiniteDistribution α) (kernel : α → FiniteDistribution β)
    (input : α) (output : β)
    (inputSupported : Supports distribution input)
    (outputSupported : Supports (kernel input) output) :
    Supports (bindDistribution distribution kernel) output := by
  rcases inputSupported with ⟨inputWeight, inputMember, inputPositive⟩
  rcases outputSupported with ⟨outputWeight, outputMember, outputPositive⟩
  refine ⟨inputWeight * outputWeight, ?_, Rat.mul_pos inputPositive outputPositive⟩
  change (output, inputWeight * outputWeight) ∈
    bindEntries distribution.outcomes (fun value => (kernel value).outcomes)
  exact bindEntries_contains_supported_pair distribution.outcomes
    (fun value => (kernel value).outcomes) input inputWeight output outputWeight
    inputMember outputMember

def pureDistribution {α : Type} (value : α) : FiniteDistribution α :=
  ⟨[(value, 1)], by
    intro outcome weight member
    simp only [List.mem_singleton] at member
    rcases member with ⟨rfl, rfl⟩
    exact of_decide_eq_true rfl,
    by change (1 : Rat) + 0 = 1; exact Rat.add_zero _⟩

/-- A proposed state encoding is sufficient for prediction exactly when the
    next-outcome law is constant across histories mapped to the same state.
    This is a model-admissibility condition, not an axiom about LLM memory. -/
def StateSufficient {History State Outcome : Type}
    (encode : History → State)
    (law : History → FiniteDistribution Outcome) : Prop :=
  ∀ first second, encode first = encode second → law first = law second

/-- A history-dependent prediction law can be represented using only the
    encoded state iff it is constant on every fiber of that encoding. This
    makes the Markov/state-sufficiency requirement explicit and falsifiable. -/
theorem state_sufficient_iff_law_factors_through_encoding
    {History State Outcome : Type}
    (encode : History → State)
    (law : History → FiniteDistribution Outcome) :
    StateSufficient encode law ↔
      ∃ stateLaw : State → Option (FiniteDistribution Outcome),
        ∀ history, stateLaw (encode history) = some (law history) := by
  constructor
  · intro sufficient
    classical
    let stateLaw : State → Option (FiniteDistribution Outcome) := fun state =>
      if witness : ∃ history, encode history = state then
        some (law witness.choose)
      else none
    refine ⟨stateLaw, ?_⟩
    intro history
    have witness : ∃ candidate, encode candidate = encode history :=
      ⟨history, rfl⟩
    have sameLaw := sufficient witness.choose history witness.choose_spec
    simp [stateLaw, witness, sameLaw]
  · rintro ⟨stateLaw, factors⟩ first second sameState
    have firstLaw := factors first
    have secondLaw := factors second
    rw [← sameState] at secondLaw
    have equalSome : some (law first) = some (law second) :=
      firstLaw.symm.trans secondLaw
    exact Option.some.inj equalSome

structure AgentState (InternalState ResourceState : Type) where
  internal : InternalState
  resources : ResourceState

abbrev StateProfile (Agent InternalState ResourceState : Type) :=
  Agent → AgentState InternalState ResourceState

abbrev ProposalProfile (Agent Proposal : Type) := Agent → Proposal
abbrev ExecutionProfile (Agent Opportunity : Type) := Agent → Option Opportunity
abbrev ProductionProfile (Agent Production : Type) := Agent → Option Production

/-- An event schema for the agent-centered economic unit of observation.
    Resources and opportunities are recorded for an identified participant;
    execution and verified production are kept distinct from a proposal.
    This is an ontology/measurement interface, not an assumption that every
    message or every run contains such an event. -/
structure AgentEconomicEvent (Agent Resource Opportunity Production : Type) where
  participant : Agent
  resourceBefore : Resource
  resourceAfter : Resource
  opportunitiesBefore : List Opportunity
  opportunitiesAfter : List Opportunity
  executedOpportunity : Option Opportunity
  verifiedProduction : Option Production
  relationalStateChanged : Bool
  continuesBefore : Bool
  continuesAfter : Bool

/-- An observed event has a recorded economic consequence when it changes the
    participant's attributable resource, feasible opportunity set, relational
    state, or continuation status, or records verified production. Merely recording
    that an opportunity was executed is not sufficient: execution is a stage
    in the event chain, not by itself an economic outcome. Whether a resource,
    opportunity, production, relational, or continuation margin belongs to a
    concrete case must be declared by that case's system boundary. A bare proposal is
    deliberately absent from this predicate. -/
def AgentEconomicEvent.hasConsequence
    {Agent Resource Opportunity Production : Type}
    (event : AgentEconomicEvent Agent Resource Opportunity Production) : Prop :=
  event.resourceBefore ≠ event.resourceAfter ∨
  (∃ opportunity, opportunity ∈ event.opportunitiesBefore ∧
    opportunity ∉ event.opportunitiesAfter) ∨
  (∃ opportunity, opportunity ∈ event.opportunitiesAfter ∧
    opportunity ∉ event.opportunitiesBefore) ∨
  event.verifiedProduction.isSome = true ∨
  event.relationalStateChanged = true ∨
  event.continuesBefore ≠ event.continuesAfter

/-- The environment model: `Condition` is a model input, not a mechanism.
    `Agent` indexes tracked subjects, while `AgentState` carries dynamic
    internal state and resources. Response may depend on each agent's
    observation, opportunity menu, and visible institutional signal. Joint
    response and production distributions may encode arbitrary dependence
    across agents; no product or independent-agent assumption is built in.

    These fields define a law-bearing interface; they do not assert that any
    particular LLM follows a specified law. Resource updating receives the
    proposal profile as well as execution and production, so generation costs
    can be booked even for rejected proposals when the proposal representation
    carries auditable compute use. Empirical restrictions on these kernels
    must be stated separately and can be rejected by data. -/
structure AgentEconomyModel
    (Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type)
    [DecidableEq Proposal] where
  observe : Agent → AgentState InternalState ResourceState → Condition → Observation
  opportunityMenu : Agent → AgentState InternalState ResourceState → Condition → List Opportunity
  individualResponse : Agent → Condition → AgentState InternalState ResourceState →
    Observation → InstitutionalSignal → List Opportunity → FiniteDistribution Proposal
  jointResponse : Condition → StateProfile Agent InternalState ResourceState →
    (Agent → Observation) → (Agent → InstitutionalSignal) → (Agent → List Opportunity) →
      FiniteDistribution (ProposalProfile Agent Proposal)
  responseMarginalsAgree : ∀ agent condition states observations institutionalSignals menus action,
    eventMass
      (jointResponse condition states observations institutionalSignals menus)
      (fun profile => decide (profile agent = action)) =
    eventMass
      (individualResponse agent condition (states agent) (observations agent)
        (institutionalSignals agent) (menus agent))
      (fun proposal => decide (proposal = action))
  feasibleExecution : Condition → StateProfile Agent InternalState ResourceState →
    ExecutionProfile Agent Opportunity → Prop
  jointProduction : Condition → StateProfile Agent InternalState ResourceState →
    ProposalProfile Agent Proposal → ExecutionProfile Agent Opportunity →
      FiniteDistribution (ProductionProfile Agent Production)
  /-- Resource updating observes the submitted proposals as well as execution
      and verified production. This lets an application book agent-attributed
      generation/communication cost even when a proposal is not executed; the
      proposal type may carry an auditable token-use statistic. -/
  resourceAfter : Agent → AgentState InternalState ResourceState →
    ProposalProfile Agent Proposal → ExecutionProfile Agent Opportunity →
      ProductionProfile Agent Production → ResourceState
  internalStateAfter : Agent → AgentState InternalState ResourceState → Condition →
    ProposalProfile Agent Proposal → ExecutionProfile Agent Opportunity →
      ProductionProfile Agent Production → InternalState
  continues : Agent → AgentState InternalState ResourceState → Prop

/-- An optional, empirically testable representation of persistent computational
    constitution. Constitution is held fixed within the represented model, while
    condition, current state, observation, institutional information, and the
    opportunity menu remain inputs to the response law. This is a restriction on
    individual response marginals, not a claim that all systems factor this way;
    the model's joint response may still contain arbitrary dependence across agents. -/
structure ConstitutionallyFactoredResponses
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) where
  Constitution : Type
  constitution : Agent → Constitution
  responseByConstitution : Constitution → Condition → AgentState InternalState ResourceState →
    Observation → InstitutionalSignal → List Opportunity → FiniteDistribution Proposal
  responseFactorization : ∀ agent condition state observation institutionalSignal menu,
    model.individualResponse agent condition state observation institutionalSignal menu =
      responseByConstitution (constitution agent) condition state observation institutionalSignal menu

/-- Under the optional factorization restriction, agents with the same
    constitution have the same individual response law when all dynamic inputs
    are held fixed. This creates a falsifiable comparison without assuming
    rationality, stable preferences across contexts, or independent agents. -/
theorem equal_constitution_equal_response
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    {model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production}
    (representation : ConstitutionallyFactoredResponses model)
    (first second : Agent)
    (condition : Condition)
    (state : AgentState InternalState ResourceState)
    (observation : Observation)
    (institutionalSignal : InstitutionalSignal)
    (menu : List Opportunity)
    (sameConstitution : representation.constitution first = representation.constitution second) :
    model.individualResponse first condition state observation institutionalSignal menu =
      model.individualResponse second condition state observation institutionalSignal menu := by
  rw [representation.responseFactorization, representation.responseFactorization, sameConstitution]

/-- Two menus are the same opportunity set when they contain the same options,
    regardless of their list order or duplicate representation. -/
def sameOpportunitySet {Opportunity : Type} (left right : List Opportunity) : Prop :=
  ∀ opportunity, opportunity ∈ left ↔ opportunity ∈ right

/-- Resource relevance is a property of a model, not an axiom imposed on every
    computational agent. It says that for some fixed agent, condition, and
    internal state, changing only the resource state changes the available
    opportunity set. A model may contain a resource variable without resources
    binding any opportunity; such a model does not satisfy this predicate. -/
def ResourceRelevant
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) :
  Prop :=
  ∃ agent condition internal resource₁ resource₂,
    ¬ sameOpportunitySet
      (model.opportunityMenu agent ⟨internal, resource₁⟩ condition)
      (model.opportunityMenu agent ⟨internal, resource₂⟩ condition)

def AgentEconomyModel.nextState
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState)
    (proposals : ProposalProfile Agent Proposal)
    (execution : ExecutionProfile Agent Opportunity)
    (production : ProductionProfile Agent Production) :
    StateProfile Agent InternalState ResourceState :=
  fun agent => {
    internal := model.internalStateAfter agent (states agent) condition proposals execution production
    resources := model.resourceAfter agent (states agent) proposals execution production
  }

/-- A mechanism rule is an institution specified independently of any
    environment model. It separates pre-action disclosure from its
    post-proposal execution lottery. Whether its supported outcomes are
    feasible in a particular environment is expressed by `MechanismCompatible`,
    a relation on the pair. A constant disclosure captures an unobserved
    institution. -/
structure MechanismRule
    (Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type) where
  /-- Information about the institution visible to each agent before acting.
      A constant signal represents an unannounced or unobserved mechanism. -/
  institutionalSignal : Condition → StateProfile Agent InternalState ResourceState →
    Agent → InstitutionalSignal
  execute : Condition → StateProfile Agent InternalState ResourceState →
    ProposalProfile Agent Proposal → FiniteDistribution (ExecutionProfile Agent Opportunity)

/-- Compatibility is a relation between two independently defined objects:
    an environment model supplies the feasible execution set, while a
    mechanism supplies the execution lottery. It is not built into either
    object's identity. -/
def MechanismCompatible
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) : Prop :=
  ∀ condition states proposals execution,
    Supports (mechanism.execute condition states proposals) execution →
      model.feasibleExecution condition states execution

/-- In a compatible model-rule pair, every positively supported execution
    outcome satisfies the model's feasibility predicate. This consequence is
    available only after compatibility is supplied; feasibility is not silently
    built into the mechanism's definition. -/
theorem compatible_execution_support_is_feasible
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (compatible : MechanismCompatible model mechanism)
    (condition : Condition) (states : StateProfile Agent InternalState ResourceState)
    (proposals : ProposalProfile Agent Proposal) (execution : ExecutionProfile Agent Opportunity)
    (supported : Supports (mechanism.execute condition states proposals) execution) :
    model.feasibleExecution condition states execution :=
  compatible condition states proposals execution supported

/-- A model and a mechanism rule become an admissible institutional pairing
    only after their compatibility condition is supplied. The rule itself
    remains reusable and independently defined. -/
structure AdmissibleInstitution
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) where
  rule : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production
  compatible : MechanismCompatible model rule

/-- A resource-only post-event state, used to isolate the channel from the
    resource ledger to the next opportunity set. The internal state is held
    fixed so this predicate does not conflate resource feedback with memory or
    context updating. -/
def resourceOnlyUpdatedState
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (agent : Agent) (state : AgentState InternalState ResourceState)
    (proposals : ProposalProfile Agent Proposal)
    (execution : ExecutionProfile Agent Opportunity)
    (production : ProductionProfile Agent Production) :
    AgentState InternalState ResourceState :=
  { internal := state.internal
    resources := model.resourceAfter agent state proposals execution production }

/-- Resource feedback is present when a proposal, its execution, and a
    production outcome all have positive conditional probability under the
    response, mechanism, and production kernels, and the result can change an
    agent's next opportunity set through the resource ledger alone. The
    starting state need not be reachable from any designated initial state.
    This is a property of a model-mechanism pair, not an assumption that every
    agent economy has such feedback or that agents respond rationally. -/
def KernelSupportedResourceFeedback
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) : Prop :=
  ∃ condition states proposals execution production agent,
    Supports
      (model.jointResponse condition states
        (fun current => model.observe current (states current) condition)
        (fun current => mechanism.institutionalSignal condition states current)
        (fun current => model.opportunityMenu current (states current) condition))
      proposals ∧
    Supports (mechanism.execute condition states proposals) execution ∧
    Supports (model.jointProduction condition states proposals execution) production ∧
    ¬ sameOpportunitySet
      (model.opportunityMenu agent (states agent) condition)
      (model.opportunityMenu agent
        (resourceOnlyUpdatedState model agent (states agent) proposals execution production)
        condition)

/-- Kernel-supported resource feedback entails that resources are genuinely
    opportunity-relevant in the static sense. The converse need not hold:
    externally imaginable resource states may change a menu even when no
    positive-probability transition at the represented state moves the agent
    between them. -/
theorem kernel_supported_resource_feedback_implies_resource_relevant
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (feedback : KernelSupportedResourceFeedback model mechanism) :
    ResourceRelevant model := by
  rcases feedback with
    ⟨condition, states, proposals, execution, production, agent,
      _proposalSupported, _executionSupported, _productionSupported, menuChanges⟩
  exact ⟨agent, condition, (states agent).internal, (states agent).resources,
    model.resourceAfter agent (states agent) proposals execution production, menuChanges⟩

/-- The proposal law induced by a model and the information disclosed by a
    mechanism. The execution rule itself is downstream and does not enter this
    distribution. -/
def proposalDistribution
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState) :
    FiniteDistribution (ProposalProfile Agent Proposal) :=
  model.jointResponse condition states
    (fun agent => model.observe agent (states agent) condition)
    (fun agent => mechanism.institutionalSignal condition states agent)
    (fun agent => model.opportunityMenu agent (states agent) condition)

/-- A menu entry is conditionally executable when some positively supported
    proposal profile can lead the mechanism to execute that opportunity for
    the named agent with positive conditional support. -/
def SupportedExecutableOpportunity
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState)
    (agent : Agent) (opportunity : Opportunity) : Prop :=
  ∃ proposals execution,
    Supports (proposalDistribution model mechanism condition states) proposals ∧
    Supports (mechanism.execute condition states proposals) execution ∧
    execution agent = some opportunity

/-- Model-mechanism contract stating that the agent-visible menu is exactly
    the set of opportunities reachable through positive support of proposal
    and execution kernels. This is an optional, falsifiable interface property,
    not a universal axiom about institutions. -/
def MenuFaithfulAt
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState) : Prop :=
  ∀ agent opportunity,
    opportunity ∈ model.opportunityMenu agent (states agent) condition ↔
      SupportedExecutableOpportunity model mechanism condition states agent opportunity

/-- When the menu faithfully represents supported executable opportunities
    at two states, a change in menu implies a change in which opportunities
    can actually be executed with positive conditional support. -/
theorem menu_change_implies_supported_executable_set_change
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) (condition : Condition)
    (first second : StateProfile Agent InternalState ResourceState)
    (agent : Agent)
    (firstFaithful : MenuFaithfulAt model mechanism condition first)
    (secondFaithful : MenuFaithfulAt model mechanism condition second)
    (menusDiffer : ¬ sameOpportunitySet
      (model.opportunityMenu agent (first agent) condition)
      (model.opportunityMenu agent (second agent) condition)) :
    ¬ ∀ opportunity,
      SupportedExecutableOpportunity model mechanism condition first agent opportunity ↔
        SupportedExecutableOpportunity model mechanism condition second agent opportunity := by
  intro executableSetsSame
  apply menusDiffer
  intro opportunity
  constructor
  · intro inFirstMenu
    apply (secondFaithful agent opportunity).mpr
    apply (executableSetsSame opportunity).mp
    exact (firstFaithful agent opportunity).mp inFirstMenu
  · intro inSecondMenu
    apply (firstFaithful agent opportunity).mpr
    apply (executableSetsSame opportunity).mpr
    exact (secondFaithful agent opportunity).mp inSecondMenu

/-- If two institutions disclose the same signal to every agent at a fixed
    state and condition, the model predicts the same proposal distribution,
    regardless of how their downstream execution rules differ. This is the
    direct/adaptive mechanism-effect boundary; it assumes the response model
    and the agents' other inputs are held fixed. -/
theorem equal_disclosure_implies_equal_proposal_law
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (first second : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState)
    (sameDisclosure : ∀ agent,
      first.institutionalSignal condition states agent =
        second.institutionalSignal condition states agent) :
    proposalDistribution model first condition states =
      proposalDistribution model second condition states := by
  unfold proposalDistribution
  have signalsEqual :
      (fun agent => first.institutionalSignal condition states agent) =
        (fun agent => second.institutionalSignal condition states agent) :=
    funext sameDisclosure
  rw [signalsEqual]

/-- Correctly normalized one-period law: proposals conditional on visible
    institutional information, mechanism execution, production, and next
    state. Conditional composition preserves mass one by construction;
    dependence within each joint population kernel is allowed.
-/
def onePeriodDistribution
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState) :
    FiniteDistribution
      (ProposalProfile Agent Proposal × ExecutionProfile Agent Opportunity ×
        ProductionProfile Agent Production × StateProfile Agent InternalState ResourceState) :=
  bindDistribution
    (model.jointResponse condition states
      (fun agent => model.observe agent (states agent) condition)
      (fun agent => mechanism.institutionalSignal condition states agent)
      (fun agent => model.opportunityMenu agent (states agent) condition))
    (fun proposals =>
      bindDistribution (mechanism.execute condition states proposals)
        (fun execution =>
            mapDistribution
              (fun production =>
                (proposals, execution, production,
                  model.nextState condition states proposals execution production))
            (model.jointProduction condition states proposals execution)))

/-- The period law for an admissible model-institution pair. The lower-level
    `onePeriodDistribution` remains useful for counterfactual or invalid rule
    comparisons; this interface requires compatibility for economic prediction.
-/
def admissibleOnePeriodDistribution
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (institution : AdmissibleInstitution model)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState) :=
  onePeriodDistribution model institution.rule condition states

/-- If a proposal, conditional execution, and conditional production outcome
    each have positive support, then the corresponding complete path has
    positive support in the composed one-period law. The path weight is the
    product of the stage weights; no independence between agents is introduced
    because each stage uses the model's joint population kernel. -/
theorem supported_stages_have_positive_one_period_path
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState)
    (proposals : ProposalProfile Agent Proposal)
    (execution : ExecutionProfile Agent Opportunity)
    (production : ProductionProfile Agent Production)
    (proposalSupported : Supports
      (proposalDistribution model mechanism condition states) proposals)
    (executionSupported : Supports
      (mechanism.execute condition states proposals) execution)
    (productionSupported : Supports
      (model.jointProduction condition states proposals execution) production) :
    Supports (onePeriodDistribution model mechanism condition states)
      (proposals, execution, production,
        model.nextState condition states proposals execution production) := by
  let nextState := model.nextState condition states proposals execution production
  have executedPath : Supports
      (bindDistribution (mechanism.execute condition states proposals)
        (fun assigned => mapDistribution
          (fun outcome =>
            (proposals, assigned, outcome,
              model.nextState condition states proposals assigned outcome))
          (model.jointProduction condition states proposals assigned)))
      (proposals, execution, production, nextState) := by
    apply supports_bindDistribution_of_supports
      (mechanism.execute condition states proposals)
      (fun assigned => mapDistribution
        (fun outcome =>
          (proposals, assigned, outcome,
            model.nextState condition states proposals assigned outcome))
        (model.jointProduction condition states proposals assigned))
      execution (proposals, execution, production, nextState)
      executionSupported
    exact supports_mapDistribution_of_supports
      (fun outcome =>
        (proposals, execution, outcome,
          model.nextState condition states proposals execution outcome))
      (model.jointProduction condition states proposals execution)
      production productionSupported
  have completePath := supports_bindDistribution_of_supports
    (proposalDistribution model mechanism condition states)
    (fun proposed =>
      bindDistribution (mechanism.execute condition states proposed)
        (fun assigned => mapDistribution
          (fun outcome =>
            (proposed, assigned, outcome,
              model.nextState condition states proposed assigned outcome))
          (model.jointProduction condition states proposed assigned)))
    proposals (proposals, execution, production, nextState)
    proposalSupported executedPath
  simpa [onePeriodDistribution, proposalDistribution, nextState] using completePath

/-- The staged support condition used by resource-feedback predicates really
    identifies a positive-probability path in the complete one-period model. -/
theorem kernel_supported_resource_feedback_yields_one_period_path
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (feedback : KernelSupportedResourceFeedback model mechanism) :
    ∃ condition states proposals execution production agent,
      Supports (onePeriodDistribution model mechanism condition states)
        (proposals, execution, production,
          model.nextState condition states proposals execution production) ∧
      ¬ sameOpportunitySet
        (model.opportunityMenu agent (states agent) condition)
        (model.opportunityMenu agent
          (resourceOnlyUpdatedState model agent (states agent) proposals execution production)
          condition) := by
  rcases feedback with
    ⟨condition, states, proposals, execution, production, agent,
      proposalSupported, executionSupported, productionSupported, menusChange⟩
  exact ⟨condition, states, proposals, execution, production, agent,
    supported_stages_have_positive_one_period_path model mechanism condition states
      proposals execution production proposalSupported executionSupported productionSupported,
    menusChange⟩

/-- One-period transition law from a finite initial population-state lottery.
    It retains the initial state alongside the realized proposal, execution,
    production, and updated state so paths remain auditable. -/
def initialOnePeriodDistribution
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (condition : Condition)
    (initialStates : FiniteDistribution (StateProfile Agent InternalState ResourceState)) :
    FiniteDistribution
      (StateProfile Agent InternalState ResourceState ×
        (ProposalProfile Agent Proposal × ExecutionProfile Agent Opportunity ×
          ProductionProfile Agent Production × StateProfile Agent InternalState ResourceState)) :=
  bindDistribution initialStates (fun states =>
    mapDistribution (fun outcome => (states, outcome))
      (onePeriodDistribution model mechanism condition states))

/-- Initial-state support plus positive conditional support at each stage
    yields a genuinely positive-probability path from the initial law. This is
    a one-period reachability result; it does not assume that every state in
    the model's type is reachable. -/
theorem initial_support_composes_with_one_period_path
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (mechanism : MechanismRule Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (condition : Condition)
    (initialStates : FiniteDistribution (StateProfile Agent InternalState ResourceState))
    (states : StateProfile Agent InternalState ResourceState)
    (proposals : ProposalProfile Agent Proposal)
    (execution : ExecutionProfile Agent Opportunity)
    (production : ProductionProfile Agent Production)
    (initialStateSupported : Supports initialStates states)
    (proposalSupported : Supports
      (proposalDistribution model mechanism condition states) proposals)
    (executionSupported : Supports
      (mechanism.execute condition states proposals) execution)
    (productionSupported : Supports
      (model.jointProduction condition states proposals execution) production) :
    Supports (initialOnePeriodDistribution model mechanism condition initialStates)
      (states, (proposals, execution, production,
        model.nextState condition states proposals execution production)) := by
  have onePeriodSupported := supported_stages_have_positive_one_period_path
    model mechanism condition states proposals execution production
    proposalSupported executionSupported productionSupported
  have retainedPathSupported := supports_mapDistribution_of_supports
    (fun outcome => (states, outcome))
    (onePeriodDistribution model mechanism condition states)
    (proposals, execution, production,
      model.nextState condition states proposals execution production)
    onePeriodSupported
  exact supports_bindDistribution_of_supports initialStates
    (fun initial => mapDistribution (fun outcome => (initial, outcome))
      (onePeriodDistribution model mechanism condition initial))
    states
    (states, (proposals, execution, production,
      model.nextState condition states proposals execution production))
    initialStateSupported retainedPathSupported

end AgentMicrofoundations.Ontology
