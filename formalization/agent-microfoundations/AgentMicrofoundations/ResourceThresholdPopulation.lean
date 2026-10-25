import AgentMicrofoundations.TokenAccounting

/-!
Exact heterogeneous-population implication of action-specific resource gates.

The result sums individual autoregressive proposal probabilities over any
finite list of agents. It does not assume exchangeability, independence, or a
common token kernel. Increasing balances only changes the population proposal
mass through agents whose balance crosses the event's own decision-prefix
threshold.
-/
namespace AgentMicrofoundations.ResourceThresholdPopulation

open AgentMicrofoundations.AutoregressiveResponse
open AgentMicrofoundations.TokenAccounting
open AgentMicrofoundations.Ontology

/-- Expected number of agents in a finite list whose response law produces a
    named proposal event when each has its own constitution, input context,
    balance, and decision-prefix length. This is a sum of marginal probabilities;
    it makes no claim about the joint distribution of realized proposals. -/
def proposalEventRateSum {Agent Context Token Proposal : Type}
    (agents : List Agent)
    (constitution : Agent → AutoregressiveConstitution Context Token Proposal)
    (context : Agent → Context)
    (balance : Agent → Nat)
    (tokenPrice technicalCap : Nat)
    (event : Proposal → Bool) : Rat :=
  match agents with
  | [] => 0
  | agent :: rest =>
      eventMass
        (proposalLaw (constitution agent) (context agent)
          (affordableGenerationBudget (balance agent) tokenPrice technicalCap))
        event + proposalEventRateSum rest constitution context balance tokenPrice technicalCap event

/-- Full-cap probability mass contributed by agents whose individual resource
    balance crosses the event's decision-prefix threshold between two regimes. -/
def thresholdCrossingFullCapMass {Agent Context Token Proposal : Type}
    (agents : List Agent)
    (constitution : Agent → AutoregressiveConstitution Context Token Proposal)
    (context : Agent → Context)
    (prefixLength : Agent → Nat)
    (lowBalance highBalance : Agent → Nat)
    (tokenPrice technicalCap : Nat)
    (event : Proposal → Bool) : Rat :=
  match agents with
  | [] => 0
  | agent :: rest =>
      if tokenPrice * prefixLength agent ≤ lowBalance agent then
        thresholdCrossingFullCapMass rest constitution context prefixLength
          lowBalance highBalance tokenPrice technicalCap event
      else if tokenPrice * prefixLength agent ≤ highBalance agent then
        eventMass (proposalLaw (constitution agent) (context agent) technicalCap) event +
          thresholdCrossingFullCapMass rest constitution context prefixLength
            lowBalance highBalance tokenPrice technicalCap event
      else
        thresholdCrossingFullCapMass rest constitution context prefixLength
          lowBalance highBalance tokenPrice technicalCap event

/-- **Exact population extensive-margin law.** Under a fixed constitution and
    context for each agent, and with an event-specific parser prefix, the change
    in the expected number of event proposals from low to high balances is
    exactly the sum of full-cap event probabilities for agents who cross their
    own affordability threshold.

    This is stronger than an upper bound: agents who can afford the event in
    both regimes keep the same event probability, agents who can afford it in
    neither regime contribute zero in both, and only threshold crossers add
    mass. Arbitrary heterogeneity across agents is allowed. The theorem
    concerns proposal marginals; realized population counts may still be
    dependent, and execution/allocation/production require separate kernels. -/
theorem population_event_rate_change_equals_threshold_crossing_mass
    {Agent Context Token Proposal : Type}
    (agents : List Agent)
    (constitution : Agent → AutoregressiveConstitution Context Token Proposal)
    (context : Agent → Context)
    (prefixLength : Agent → Nat)
    (prefixParser : ∀ agent, PrefixSufficientParser (constitution agent) (prefixLength agent))
    (event : Proposal → Bool)
    (requiresPrefix : ∀ agent,
      ProposalEventRequiresPrefix (constitution agent) (prefixLength agent) event)
    (lowBalance highBalance : Agent → Nat)
    (tokenPrice technicalCap : Nat)
    (prefixWithinCap : ∀ agent, agent ∈ agents → prefixLength agent ≤ technicalCap)
    (balancesOrdered : ∀ agent, agent ∈ agents → lowBalance agent ≤ highBalance agent) :
    proposalEventRateSum agents constitution context highBalance
        tokenPrice technicalCap event =
      proposalEventRateSum agents constitution context lowBalance
        tokenPrice technicalCap event +
      thresholdCrossingFullCapMass agents constitution context prefixLength
        lowBalance highBalance tokenPrice technicalCap event := by
  induction agents with
  | nil => simp [proposalEventRateSum, thresholdCrossingFullCapMass]
  | cons agent rest ih =>
      have orderedHead : lowBalance agent ≤ highBalance agent :=
        balancesOrdered agent (by simp)
      have orderedRest : ∀ current, current ∈ rest →
          lowBalance current ≤ highBalance current := by
        intro current member
        exact balancesOrdered current (by simp [member])
      have capHead : prefixLength agent ≤ technicalCap :=
        prefixWithinCap agent (by simp)
      have capRest : ∀ current, current ∈ rest → prefixLength current ≤ technicalCap := by
        intro current member
        exact prefixWithinCap current (by simp [member])
      have lowLaw := resource_limited_proposal_event_has_decision_cost_threshold
        (constitution agent) (prefixLength agent) (prefixParser agent) event
        (requiresPrefix agent) (context agent) (lowBalance agent) tokenPrice
        technicalCap capHead
      have highLaw := resource_limited_proposal_event_has_decision_cost_threshold
        (constitution agent) (prefixLength agent) (prefixParser agent) event
        (requiresPrefix agent) (context agent) (highBalance agent) tokenPrice
        technicalCap capHead
      have tailLaw := ih capRest orderedRest
      simp only [proposalEventRateSum, thresholdCrossingFullCapMass]
      by_cases lowFunded : tokenPrice * prefixLength agent ≤ lowBalance agent
      · have highFunded : tokenPrice * prefixLength agent ≤ highBalance agent :=
          Nat.le_trans lowFunded orderedHead
        rw [if_pos lowFunded] at lowLaw
        rw [if_pos highFunded] at highLaw
        rw [lowLaw, highLaw]
        rw [tailLaw]
        ac_rfl
      · by_cases highFunded : tokenPrice * prefixLength agent ≤ highBalance agent
        · rw [if_neg lowFunded] at lowLaw
          rw [if_pos highFunded] at highLaw
          rw [lowLaw, highLaw]
          rw [tailLaw]
          ac_rfl
        · have lowNotHigh : ¬ tokenPrice * prefixLength agent ≤ lowBalance agent := lowFunded
          have highNotFunded : ¬ tokenPrice * prefixLength agent ≤ highBalance agent := highFunded
          rw [if_neg lowNotHigh] at lowLaw
          rw [if_neg highNotFunded] at highLaw
          rw [lowLaw, highLaw]
          rw [tailLaw]
          ac_rfl

end AgentMicrofoundations.ResourceThresholdPopulation
