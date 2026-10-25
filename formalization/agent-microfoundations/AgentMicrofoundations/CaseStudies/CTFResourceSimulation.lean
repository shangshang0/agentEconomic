import AgentMicrofoundations.CaseStudies.CTFParameterizedSimulation

/-!
Executable CTF resource-path semantics.

The design record supplies energy prices, task opening costs and rewards,
survival semantics, and the backend's death-check schedule. A finite path of
requests, task openings/results, transfers, refunds, and settlement events is
then replayed exactly. The path lottery is supplied by the scenario's response,
allocation, and production kernels; this module does not infer agent behavior
from the resource controls.
-/
namespace AgentMicrofoundations.CaseStudies.CTFResourceSimulation

open AgentMicrofoundations.CaseStudies.CTFParameterizedSimulation
open AgentMicrofoundations.Ontology

structure ResourceState where
  balance : Rat
  alive : Bool
  requestsRemaining : Nat
  deriving DecidableEq, Repr

def initialResourceState {Agent Task : Type} (design : CTFDesign Agent Task)
    (agent : Agent) : ResourceState :=
  { balance := design.initialEnergy agent, alive := true,
    requestsRemaining := design.initialApiQuota agent }

/-- Events are from one tracked agent's ledger perspective. Task indices are
    bounded by the supplied design, so opening costs and verified rewards are
    read from the actual menu rather than duplicated in the event log. -/
inductive ResourceEvent {Agent Task : Type}
    (design : CTFDesign Agent Task) where
  | modelRequest
  | taskOpened (taskIndex : Fin design.offeredTasks.length)
  | verifiedResult (taskIndex : Fin design.offeredTasks.length) (correct : Bool)
  | transferReceived (amount : Rat)
  | transferSent (amount : Rat)
  | refund (amount : Rat)
  | basalDrain
  | periodSettlement

def eventDelta {Agent Task : Type} (design : CTFDesign Agent Task) :
    ResourceEvent design → Rat
  | .modelRequest => -design.modelRequestEnergyCost
  | .taskOpened taskIndex => -(design.offeredTasks[taskIndex].openCost)
  | .verifiedResult taskIndex correct =>
      if correct then design.offeredTasks[taskIndex].reward else 0
  | .transferReceived amount => amount - design.transferFee
  | .transferSent amount => -(amount + design.transferFee)
  | .refund amount => amount
  | .basalDrain => -design.basalEnergyDrain
  | .periodSettlement => 0

/-- Which events trigger the threshold check in the encoded backend. The v2
    rule checks after model requests, transfers, and daily basal settlement;
    task-open debits and task rewards alter the balance but are checked at the
    next such boundary. -/
def checksDeathAfter {Agent Task : Type} (design : CTFDesign Agent Task) :
    ResourceEvent design → Bool
  | .modelRequest => design.deathCheck == .authorityWorldV2 || design.deathCheck == .eachEvent
  | .taskOpened _ => design.deathCheck == .eachEvent
  | .verifiedResult _ _ => design.deathCheck == .eachEvent
  | .transferReceived _ => design.deathCheck == .authorityWorldV2 || design.deathCheck == .eachEvent
  | .transferSent _ => design.deathCheck == .authorityWorldV2 || design.deathCheck == .eachEvent
  | .refund _ => design.deathCheck == .eachEvent
  | .basalDrain => design.deathCheck == .authorityWorldV2 || design.deathCheck == .eachEvent
  | .periodSettlement => design.deathCheck == .periodSettlement

/-- Apply one case event. An operational balance with a due threshold check is
    absorbing at zero; symbolic balances still change but do not kill the
    subject, matching the distinction encoded by the experiment. -/
def applyEvent {Agent Task : Type} (design : CTFDesign Agent Task)
    (state : ResourceState) (event : ResourceEvent design) : ResourceState :=
  if !state.alive then state else
    let nextBalance := state.balance + eventDelta design event
    let nextQuota := match event with
      | .modelRequest =>
          if design.quotaSemantics == .finite then state.requestsRemaining - 1
          else state.requestsRemaining
      | _ => state.requestsRemaining
    if design.energySemantics == .operational && checksDeathAfter design event &&
        nextBalance ≤ 0 then
      { balance := 0, alive := false, requestsRemaining := nextQuota }
    else
      { balance := nextBalance, alive := true, requestsRemaining := nextQuota }

def replayEvents {Agent Task : Type} (design : CTFDesign Agent Task)
    (initial : ResourceState) : List (ResourceEvent design) → ResourceState
  | [] => initial
  | event :: rest => replayEvents design (applyEvent design initial event) rest

/-- Resource-side execution gate for an already proposed event. Assignment,
    time-window, task-handle, and checker constraints are supplied by the
    institutional/production kernels; this gate checks the resource rules that
    are determined by `CTFDesign`. -/
def eventResourceFeasible {Agent Task : Type} (design : CTFDesign Agent Task)
    (state : ResourceState) : ResourceEvent design → Bool
  | .taskOpened taskIndex =>
      state.alive && (design.energySemantics == .symbolic ||
        design.offeredTasks[taskIndex].openCost < state.balance)
  | .transferReceived amount =>
      state.alive && design.transfersEnabled && 0 < amount
  | .transferSent amount =>
      state.alive && design.transfersEnabled && 0 < amount &&
        (design.energySemantics == .symbolic ||
          amount + design.transferFee ≤ state.balance)
  | .modelRequest => state.alive &&
      (design.quotaSemantics == .unmetered || 0 < state.requestsRemaining)
  | .verifiedResult _ _ => state.alive
  | .refund _ => state.alive
  | .basalDrain => state.alive
  | .periodSettlement => true

def resourcePathFeasible {Agent Task : Type} (design : CTFDesign Agent Task)
    (initial : ResourceState) : List (ResourceEvent design) → Bool
  | [] => true
  | event :: rest =>
      eventResourceFeasible design initial event &&
        resourcePathFeasible design (applyEvent design initial event) rest

def additiveEventFlow {Agent Task : Type} (design : CTFDesign Agent Task)
    (events : List (ResourceEvent design)) : Rat :=
  (events.map (eventDelta design)).sum

/-- Conditional resource forecast for any finite joint path law. Exact rational
    probability mass is summed over paths that remain alive after the chosen
    sequence of resource events. -/
def survivalProbability {Agent Task : Type} (design : CTFDesign Agent Task)
    (initial : ResourceState)
    (paths : FiniteDistribution (List (ResourceEvent design))) : Rat :=
  eventMass paths (fun events => decide ((replayEvents design initial events).alive))

/-- Exact expected terminal balance, including the absorbing zero balance for
    agents whose path crosses a binding threshold. -/
def expectedTerminalBalance {Agent Task : Type} (design : CTFDesign Agent Task)
    (initial : ResourceState)
    (paths : FiniteDistribution (List (ResourceEvent design))) : Rat :=
  paths.outcomes.foldr
    (fun weighted total => weighted.2 * (replayEvents design initial weighted.1).balance + total) 0

/-- Probability assigned by a proposed case kernel to resource-infeasible
    event histories. A nonzero value rejects the backend-to-model mapping before
    outcome forecasts are interpreted. -/
def resourceInfeasiblePathMass {Agent Task : Type} (design : CTFDesign Agent Task)
    (initial : ResourceState)
    (paths : FiniteDistribution (List (ResourceEvent design))) : Rat :=
  eventMass paths (fun events => decide (!(resourcePathFeasible design initial events)))

/-- A case event law is resource-admissible exactly when every positive-mass
    path respects the operational opening/transfer gates and dead-agent
    absorption. Zero-mass entries do not affect numerical forecasts. -/
def ResourceAdmissiblePathLaw {Agent Task : Type} (design : CTFDesign Agent Task)
    (initial : ResourceState)
    (paths : FiniteDistribution (List (ResourceEvent design))) : Prop :=
  ∀ events weight, (events, weight) ∈ paths.outcomes → 0 < weight →
    resourcePathFeasible design initial events = true

/-- Symbolic accounting still obeys its additive ledger identity even when
    balances cross zero, because death enforcement is disabled by semantics. -/
theorem symbolic_path_matches_additive_ledger
    {Agent Task : Type} (design : CTFDesign Agent Task)
    (symbolic : design.energySemantics = .symbolic)
    (initialBalance : Rat) (initialQuota : Nat) (events : List (ResourceEvent design)) :
    (replayEvents design
      { balance := initialBalance, alive := true, requestsRemaining := initialQuota } events).balance =
      initialBalance + additiveEventFlow design events := by
  induction events generalizing initialBalance initialQuota with
  | nil => simp [replayEvents, additiveEventFlow, Rat.add_zero]
  | cons event rest ih =>
      simp only [replayEvents]
      have hStep : applyEvent design
          { balance := initialBalance, alive := true, requestsRemaining := initialQuota } event =
          { balance := initialBalance + eventDelta design event, alive := true,
            requestsRemaining := match event with
              | .modelRequest =>
                  if design.quotaSemantics == .finite then initialQuota - 1
                  else initialQuota
              | _ => initialQuota } := by
        simp [applyEvent, symbolic]
      rw [hStep, ih]
      simp [additiveEventFlow, Rat.add_assoc]

/-- Small executable design fixture, used only to check the parameter schema
    and clock validator. It is not an empirical behavioral law. -/
def semanticsFixture : CTFDesign Unit Unit where
  population := ⟨[()], by simp⟩
  officeSelection := .elected
  allocationRule := .agentDiscretion
  voteRule := .plurality
  governanceMode := .taskAssignment
  auditMode := .none
  offeredTasks := [{ task := (), reward := 14, openCost := 0, workTicks := 1, tier := 0 }]
  dayTicks := 10
  prestartTicks := 0
  campaignOpensAt := 0
  campaignClosesAt := 2
  votingOpensAt := 2
  votingClosesAt := 3
  assignmentOpensAt := 3
  assignmentClosesAt := 4
  productionOpensAt := 4
  productionClosesAt := 7
  registrationOpensAt := 8
  idleCognitionTicks := 1
  maxSleepTicks := 10
  taskTimeoutTicks := 3
  taskOutputLimit := 1024
  taskPrewarmTicks := 0
  taskLifetimePeriods := 1
  horizonPeriods := 1
  seedId := 0
  maxAssignments := 1
  maxDistinctRecipients := 1
  correctWinnerLimit := 1
  initialEnergy := fun _ => 1
  quotaSemantics := .finite
  initialApiQuota := fun _ => 48
  modelRequestEnergyCost := 1
  basalEnergyDrain := 0
  taxRate := 0
  resourcePacks := []
  energySemantics := .operational
  deathCheck := .authorityWorldV2
  transfersEnabled := true
  transferFee := 0
  conditionId := 0
  protocolVersion := 0
  runtimeVersion := 0
  institutionSemantics := .neutral
  objectivePrompt := .survival
  taskSuiteId := 0

def symbolicSemanticsFixture : CTFDesign Unit Unit :=
  { semanticsFixture with energySemantics := .symbolic }

theorem fixture_clock_is_admissible : validCTFClock semanticsFixture := by
  unfold validCTFClock semanticsFixture
  exact ⟨by decide, by decide, by decide, by decide, by decide,
    by decide, by decide, by decide, by decide, by decide, by decide⟩

end AgentMicrofoundations.CaseStudies.CTFResourceSimulation
