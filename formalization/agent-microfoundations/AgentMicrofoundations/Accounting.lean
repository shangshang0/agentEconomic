import AgentMicrofoundations.Ontology

/-!
Optional account-level closure for a family of resource dimensions.

This is a refinement of an `AgentEconomyModel`, not an axiom imposed on every
computational system. It records verified production, external supply/drain,
operating cost, and bilateral transfers separately for each resource kind,
then requires each coordinate of the account update to equal the sum of
recorded events in that coordinate. No conversion across resource kinds is
implicit. The pairwise transfer result below follows under that explicit
closure condition; it is not inferred from an observed experiment or from the
existence of a resource field alone. This module does not prove global
conservation for an arbitrary population or event stream.
-/
namespace AgentMicrofoundations.Accounting

open AgentMicrofoundations.Ontology

inductive ResourceEvent (Agent Resource : Type) where
  | verifiedProduction (resource : Resource) (owner : Agent) (amount : Nat)
  | externalSupply (resource : Resource) (owner : Agent) (amount : Nat)
  | externalDrain (resource : Resource) (owner : Agent) (amount : Nat)
  | operatingCost (resource : Resource) (owner : Agent) (amount : Nat)
  | internalTransfer (resource : Resource) (payer recipient : Agent) (amount : Nat)
  deriving Repr

structure TransferInstruction (Agent : Type) where
  payer : Agent
  recipient : Agent
  amount : Nat
  deriving Repr

def transferEvents {Agent Resource : Type}
    (resource : Resource) (transfers : List (TransferInstruction Agent)) :
    List (ResourceEvent Agent Resource) :=
  transfers.map fun transfer =>
    .internalTransfer resource transfer.payer transfer.recipient transfer.amount

def eventDeltaFor {Agent Resource : Type} [DecidableEq Agent] [DecidableEq Resource]
    (agent : Agent) (resource : Resource) : ResourceEvent Agent Resource → Int
  | .verifiedProduction eventResource owner amount =>
      if resource = eventResource ∧ agent = owner then (amount : Int) else 0
  | .externalSupply eventResource owner amount =>
      if resource = eventResource ∧ agent = owner then (amount : Int) else 0
  | .externalDrain eventResource owner amount =>
      if resource = eventResource ∧ agent = owner then -(amount : Int) else 0
  | .operatingCost eventResource owner amount =>
      if resource = eventResource ∧ agent = owner then -(amount : Int) else 0
  | .internalTransfer eventResource payer recipient amount =>
      (if resource = eventResource ∧ agent = recipient then (amount : Int) else 0) -
        (if resource = eventResource ∧ agent = payer then (amount : Int) else 0)

/-- Sum over an explicitly enumerated population. The population list must be
    duplicate-free whenever it is interpreted as a set of account holders. -/
def sumOver {Agent : Type} (population : List Agent) (value : Agent → Int) : Int :=
  population.foldr (fun agent total => value agent + total) 0

theorem sumOver_zero {Agent : Type} (population : List Agent) :
    sumOver population (fun _ => 0) = 0 := by
  induction population with
  | nil => rfl
  | cons agent rest ih =>
      change 0 + sumOver rest (fun _ => 0) = 0
      rw [ih]
      simp

theorem sumOver_congr {Agent : Type} (population : List Agent)
    (left right : Agent → Int)
    (sameOnPopulation : ∀ agent, agent ∈ population → left agent = right agent) :
    sumOver population left = sumOver population right := by
  induction population with
  | nil => rfl
  | cons agent rest ih =>
      change left agent + sumOver rest left = right agent + sumOver rest right
      have headEqual := sameOnPopulation agent (by simp)
      have tailEqual : ∀ current, current ∈ rest → left current = right current := by
        intro current member
        exact sameOnPopulation current (by simp [member])
      rw [headEqual, ih tailEqual]

theorem sumOver_add {Agent : Type} (population : List Agent)
    (left right : Agent → Int) :
    sumOver population (fun agent => left agent + right agent) =
      sumOver population left + sumOver population right := by
  induction population with
  | nil => simp [sumOver]
  | cons agent rest ih =>
      change left agent + right agent + sumOver rest
          (fun current => left current + right current) =
        (left agent + sumOver rest left) + (right agent + sumOver rest right)
      rw [ih]
      omega

theorem sumOver_sub {Agent : Type} (population : List Agent)
    (left right : Agent → Int) :
    sumOver population (fun agent => left agent - right agent) =
      sumOver population left - sumOver population right := by
  induction population with
  | nil => simp [sumOver]
  | cons agent rest ih =>
      change left agent - right agent + sumOver rest
          (fun current => left current - right current) =
        (left agent + sumOver rest left) - (right agent + sumOver rest right)
      rw [ih]
      omega

theorem sumOver_eqIndicator_of_not_mem
    {Agent : Type} [DecidableEq Agent]
    (population : List Agent) (target : Agent) (amount : Int)
    (absent : target ∉ population) :
    sumOver population (fun agent => if agent = target then amount else 0) = 0 := by
  induction population with
  | nil => simp [sumOver]
  | cons agent rest ih =>
      have agent_ne_target : agent ≠ target := by
        intro equal
        apply absent
        simp [equal]
      have target_absent_from_rest : target ∉ rest := by
        intro member
        apply absent
        simp [member]
      simp only [sumOver, List.foldr_cons, if_neg agent_ne_target]
      change 0 + sumOver rest (fun current => if current = target then amount else 0) = 0
      rw [ih target_absent_from_rest]
      simp

theorem sumOver_eqIndicator_of_mem_nodup
    {Agent : Type} [DecidableEq Agent]
    (population : List Agent) (target : Agent) (amount : Int)
    (noDuplicates : population.Nodup) (present : target ∈ population) :
    sumOver population (fun agent => if agent = target then amount else 0) = amount := by
  induction population with
  | nil => simp at present
  | cons agent rest ih =>
      rcases List.nodup_cons.mp noDuplicates with ⟨agent_absent, rest_nodup⟩
      by_cases headIsTarget : agent = target
      · subst agent
        have target_absent_from_rest : target ∉ rest := agent_absent
        simp only [sumOver, List.foldr_cons, if_pos rfl]
        change (amount : Int) + sumOver rest
          (fun current => if current = target then amount else 0) = amount
        rw [sumOver_eqIndicator_of_not_mem rest target amount target_absent_from_rest]
        simp
      · have target_in_rest : target ∈ rest := by
          have target_ne_agent : target ≠ agent := fun equal => headIsTarget equal.symm
          exact (List.mem_cons.mp present).resolve_left target_ne_agent
        simp only [sumOver, List.foldr_cons, if_neg headIsTarget]
        change 0 + sumOver rest
          (fun current => if current = target then amount else 0) = amount
        rw [ih rest_nodup target_in_rest]
        simp

def populationEventDelta {Agent Resource : Type}
    [DecidableEq Agent] [DecidableEq Resource]
    (population : List Agent) (resource : Resource)
    (event : ResourceEvent Agent Resource) : Int :=
  sumOver population (fun agent => eventDeltaFor agent resource event)

def netRecordedDelta {Agent Resource : Type} [DecidableEq Agent] [DecidableEq Resource]
    (agent : Agent) (resource : Resource) (events : List (ResourceEvent Agent Resource)) : Int :=
  events.foldr (fun event total => eventDeltaFor agent resource event + total) 0

theorem net_recorded_delta_append
    {Agent Resource : Type} [DecidableEq Agent] [DecidableEq Resource]
    (agent : Agent) (resource : Resource)
    (first second : List (ResourceEvent Agent Resource)) :
    netRecordedDelta agent resource (first ++ second) =
      netRecordedDelta agent resource first + netRecordedDelta agent resource second := by
  induction first with
  | nil => simp [netRecordedDelta]
  | cons event rest ih =>
      simp only [List.cons_append, netRecordedDelta, List.foldr_cons]
      have ih' :
          List.foldr (fun event total => eventDeltaFor agent resource event + total) 0
              (rest ++ second) =
            List.foldr (fun event total => eventDeltaFor agent resource event + total) 0 rest +
              List.foldr (fun event total => eventDeltaFor agent resource event + total) 0 second := by
        simpa [netRecordedDelta] using ih
      rw [ih']
      exact (Int.add_assoc _ _ _).symm

theorem internal_transfer_is_population_neutral
    {Agent Resource : Type} [DecidableEq Agent] [DecidableEq Resource]
    (population : List Agent) (resource : Resource)
    (payer recipient : Agent) (amount : Nat)
    (noDuplicates : population.Nodup)
    (payerPresent : payer ∈ population)
    (recipientPresent : recipient ∈ population) :
    populationEventDelta population resource
      (.internalTransfer resource payer recipient amount) = 0 := by
  unfold populationEventDelta
  simp [eventDeltaFor]
  rw [sumOver_sub]
  have recipientTotal := sumOver_eqIndicator_of_mem_nodup
    population recipient (amount : Int) noDuplicates recipientPresent
  have payerTotal := sumOver_eqIndicator_of_mem_nodup
    population payer (amount : Int) noDuplicates payerPresent
  rw [recipientTotal, payerTotal]
  simp

theorem internal_transfer_log_is_population_neutral
    {Agent Resource : Type} [DecidableEq Agent] [DecidableEq Resource]
    (population : List Agent) (resource : Resource)
    (transfers : List (TransferInstruction Agent))
    (populationNoDuplicates : population.Nodup)
    (endpointsInPopulation : ∀ transfer, transfer ∈ transfers →
      transfer.payer ∈ population ∧ transfer.recipient ∈ population) :
    sumOver population (fun agent =>
      netRecordedDelta agent resource (transferEvents resource transfers)) = 0 := by
  induction transfers with
  | nil => simp [transferEvents, netRecordedDelta, sumOver_zero]
  | cons transfer rest ih =>
      have headEndpoints := endpointsInPopulation transfer (by simp)
      have restEndpoints : ∀ later, later ∈ rest →
          later.payer ∈ population ∧ later.recipient ∈ population := by
        intro later member
        exact endpointsInPopulation later (by simp [member])
      simp only [transferEvents, List.map_cons]
      have firstEventNeutral :
          sumOver population (fun agent =>
            netRecordedDelta agent resource
              [.internalTransfer resource transfer.payer transfer.recipient transfer.amount]) = 0 := by
        simp only [netRecordedDelta, List.foldr_cons, List.foldr_nil, Int.add_zero]
        change populationEventDelta population resource
          (.internalTransfer resource transfer.payer transfer.recipient transfer.amount) = 0
        exact internal_transfer_is_population_neutral population resource transfer.payer
          transfer.recipient transfer.amount populationNoDuplicates headEndpoints.1 headEndpoints.2
      calc
        sumOver population (fun agent => netRecordedDelta agent resource
            ([.internalTransfer resource transfer.payer transfer.recipient transfer.amount] ++
              transferEvents resource rest)) =
          sumOver population (fun agent => netRecordedDelta agent resource
              [.internalTransfer resource transfer.payer transfer.recipient transfer.amount]) +
            sumOver population (fun agent => netRecordedDelta agent resource
              (transferEvents resource rest)) := by
                calc
                  _ = sumOver population (fun agent =>
                      netRecordedDelta agent resource
                          [.internalTransfer resource transfer.payer transfer.recipient transfer.amount] +
                        netRecordedDelta agent resource (transferEvents resource rest)) := by
                        apply sumOver_congr
                        intro agent _
                        exact net_recorded_delta_append agent resource
                          [.internalTransfer resource transfer.payer transfer.recipient transfer.amount]
                          (transferEvents resource rest)
                  _ = _ := sumOver_add population _ _
        _ = 0 := by rw [firstEventNeutral, ih restEndpoints, Int.zero_add]

theorem internal_transfer_pairwise_balance_neutral
    {Agent Resource : Type} [DecidableEq Agent] [DecidableEq Resource]
    (resource : Resource) (payer recipient : Agent) (amount : Nat) :
    eventDeltaFor payer resource (.internalTransfer resource payer recipient amount) +
      eventDeltaFor recipient resource (.internalTransfer resource payer recipient amount) = 0 := by
  by_cases same : payer = recipient
  · subst recipient
    simp [eventDeltaFor]
  · have recipient_ne_payer : recipient ≠ payer := fun h => same h.symm
    simp [eventDeltaFor, same, recipient_ne_payer]
    omega

theorem internal_transfer_spares_third_party
    {Agent Resource : Type} [DecidableEq Agent] [DecidableEq Resource]
    (resource : Resource) (payer recipient observer : Agent) (amount : Nat)
    (notPayer : observer ≠ payer) (notRecipient : observer ≠ recipient) :
    eventDeltaFor observer resource (.internalTransfer resource payer recipient amount) = 0 := by
  simp [eventDeltaFor, notPayer, notRecipient]

theorem internal_transfer_does_not_change_other_resource
    {Agent Resource : Type} [DecidableEq Agent] [DecidableEq Resource]
    (recordedResource observedResource : Resource) (payer recipient agent : Agent)
    (amount : Nat) (different : observedResource ≠ recordedResource) :
    eventDeltaFor agent observedResource
      (.internalTransfer recordedResource payer recipient amount) = 0 := by
  simp [eventDeltaFor, different]

/-- A ledger refinement ties the abstract resource transition in the core
    ontology to an event stream. This is an explicit, auditable structural
    condition for models whose resource state exposes an integer balance for
    each resource coordinate. -/
structure ResourceAccounting
    {Agent Resource InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Resource] [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) where
  balance : ResourceState → Resource → Int
  events : Condition → StateProfile Agent InternalState ResourceState →
    ProposalProfile Agent Proposal → ExecutionProfile Agent Opportunity →
      ProductionProfile Agent Production → List (ResourceEvent Agent Resource)
  closes : ∀ agent resource condition states proposals execution production,
    balance (model.resourceAfter agent (states agent) proposals execution production) resource =
      balance (states agent).resources resource +
        netRecordedDelta agent resource
          (events condition states proposals execution production)

theorem closed_ledger_internal_transfer_preserves_pair_balance
    {Agent Resource InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Resource] [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (ledger : ResourceAccounting model)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState)
    (proposals : ProposalProfile Agent Proposal)
    (execution : ExecutionProfile Agent Opportunity)
    (production : ProductionProfile Agent Production)
    (resource : Resource) (payer recipient : Agent) (amount : Nat)
    (onlyTransfer : ledger.events condition states proposals execution production =
      [.internalTransfer resource payer recipient amount]) :
    ledger.balance (model.resourceAfter payer (states payer) proposals execution production) resource +
      ledger.balance (model.resourceAfter recipient (states recipient) proposals execution production) resource =
    ledger.balance (states payer).resources resource +
      ledger.balance (states recipient).resources resource := by
  rw [ledger.closes payer resource condition states proposals execution production,
    ledger.closes recipient resource condition states proposals execution production]
  rw [onlyTransfer]
  simp only [netRecordedDelta, List.foldr_cons, List.foldr_nil]
  have transferNeutral := internal_transfer_pairwise_balance_neutral resource payer recipient amount
  omega

/-- For a finite, duplicate-free population containing the endpoints of every
    logged transfer, a closed-ledger log consisting only of internal transfers
    preserves the sum of account balances for that resource. The population
    must be explicitly enumerated; no assumption about an infinite or hidden
    set of agents is made. -/
theorem closed_ledger_internal_transfer_preserves_population_balance
    {Agent Resource InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Agent] [DecidableEq Resource] [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production)
    (ledger : ResourceAccounting model)
    (condition : Condition)
    (states : StateProfile Agent InternalState ResourceState)
    (proposals : ProposalProfile Agent Proposal)
    (execution : ExecutionProfile Agent Opportunity)
    (production : ProductionProfile Agent Production)
    (population : List Agent)
    (resource : Resource) (transfers : List (TransferInstruction Agent))
    (noDuplicates : population.Nodup)
    (endpointsInPopulation : ∀ transfer, transfer ∈ transfers →
      transfer.payer ∈ population ∧ transfer.recipient ∈ population)
    (onlyTransfer : ledger.events condition states proposals execution production =
      transferEvents resource transfers) :
    sumOver population (fun agent => ledger.balance
      (model.resourceAfter agent (states agent) proposals execution production) resource) =
    sumOver population (fun agent => ledger.balance (states agent).resources resource) := by
  let events := ledger.events condition states proposals execution production
  have closedEach : ∀ agent ∈ population,
        ledger.balance (model.resourceAfter agent (states agent) proposals execution production) resource =
        ledger.balance (states agent).resources resource +
          netRecordedDelta agent resource events := by
    intro agent _
    exact ledger.closes agent resource condition states proposals execution production
  calc
      sumOver population (fun agent => ledger.balance
        (model.resourceAfter agent (states agent) proposals execution production) resource) =
      sumOver population (fun agent => ledger.balance (states agent).resources resource +
        netRecordedDelta agent resource events) := by
          apply sumOver_congr
          exact closedEach
    _ = sumOver population (fun agent => ledger.balance (states agent).resources resource) +
        sumOver population (fun agent => netRecordedDelta agent resource events) :=
          sumOver_add population _ _
    _ = sumOver population (fun agent => ledger.balance (states agent).resources resource) := by
          have eventFlowZero :
              sumOver population (fun agent => netRecordedDelta agent resource events) = 0 := by
            have eventEq : events = transferEvents resource transfers := by
              dsimp [events]
              exact onlyTransfer
            rw [eventEq]
            exact internal_transfer_log_is_population_neutral population resource transfers
              noDuplicates endpointsInPopulation
          rw [eventFlowZero, Int.add_zero]

end AgentMicrofoundations.Accounting
