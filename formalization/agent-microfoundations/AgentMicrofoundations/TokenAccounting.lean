import AgentMicrofoundations.AutoregressiveResponse

/-!
Resource bounds for a linear token-denominated generation account.

The assumptions are explicit: a spendable Nat balance, a fixed charge per
generated token, and a technical maximum. This is one application class, not a
universal claim that all compute costs are linear or agent-owned.
-/
namespace AgentMicrofoundations.TokenAccounting

open AgentMicrofoundations.AutoregressiveResponse
open AgentMicrofoundations.Ontology

/-- Maximum generated-token count allowed by both the technical cap and an
    account that must cover a fixed per-token charge. At zero price, only the
    technical cap binds. -/
def affordableGenerationBudget (balance tokenPrice technicalCap : Nat) : Nat :=
  if tokenPrice = 0 then technicalCap
  else min technicalCap (balance / tokenPrice)

/-- The budget derived from balance and price never exceeds the technical
    generation cap. -/
theorem affordable_budget_respects_technical_cap
    (balance tokenPrice technicalCap : Nat) :
    affordableGenerationBudget balance tokenPrice technicalCap ≤ technicalCap := by
  by_cases priceZero : tokenPrice = 0
  · simp [affordableGenerationBudget, priceZero]
  · rw [affordableGenerationBudget, if_neg priceZero]
    exact Nat.min_le_left _ _

/-- Every token in the balance-derived generation budget can be paid for. -/
theorem affordable_budget_cost_fits_balance
    (balance tokenPrice technicalCap : Nat) :
    tokenPrice * affordableGenerationBudget balance tokenPrice technicalCap ≤ balance := by
  by_cases priceZero : tokenPrice = 0
  · simp [affordableGenerationBudget, priceZero]
  · have pricePositive : 0 < tokenPrice := Nat.pos_of_ne_zero priceZero
    rw [affordableGenerationBudget, if_neg priceZero]
    calc
      tokenPrice * min technicalCap (balance / tokenPrice) ≤
          tokenPrice * (balance / tokenPrice) :=
        Nat.mul_le_mul_left tokenPrice (Nat.min_le_right _ _)
      _ = balance / tokenPrice * tokenPrice := Nat.mul_comm _ _
      _ ≤ balance := Nat.div_mul_le_self _ _

/-- The balance-derived budget is maximal: every technically allowed budget
    whose full linear token charge is affordable is no larger. -/
theorem affordable_budget_is_maximal
    (balance tokenPrice technicalCap candidate : Nat)
    (pricePositive : 0 < tokenPrice)
    (withinTechnicalCap : candidate ≤ technicalCap)
    (candidateAffordable : tokenPrice * candidate ≤ balance) :
    candidate ≤ affordableGenerationBudget balance tokenPrice technicalCap := by
  have priceNonzero : tokenPrice ≠ 0 := Nat.ne_of_gt pricePositive
  rw [affordableGenerationBudget, if_neg priceNonzero]
  apply (Nat.le_min).2
  constructor
  · exact withinTechnicalCap
  · apply (Nat.le_div_iff_mul_le pricePositive).2
    calc
      candidate * tokenPrice = tokenPrice * candidate := Nat.mul_comm _ _
      _ ≤ balance := candidateAffordable

/-- At a fixed token price and technical cap, a larger spendable balance can
    never lower the maximum affordable generation budget. This is a resource
    comparative static; it does not imply monotonicity of any particular
    action probability. -/
theorem affordable_budget_monotone_in_balance
    (lowerBalance higherBalance tokenPrice technicalCap : Nat)
    (balanceOrdered : lowerBalance ≤ higherBalance) :
    affordableGenerationBudget lowerBalance tokenPrice technicalCap ≤
      affordableGenerationBudget higherBalance tokenPrice technicalCap := by
  by_cases priceZero : tokenPrice = 0
  · simp [affordableGenerationBudget, priceZero]
  · have pricePositive : 0 < tokenPrice := Nat.pos_of_ne_zero priceZero
    apply affordable_budget_is_maximal higherBalance tokenPrice technicalCap
      (affordableGenerationBudget lowerBalance tokenPrice technicalCap) pricePositive
    · exact affordable_budget_respects_technical_cap lowerBalance tokenPrice technicalCap
    · exact Nat.le_trans
        (affordable_budget_cost_fits_balance lowerBalance tokenPrice technicalCap)
        balanceOrdered

/-- Once the balance can pay for the full technical cap, additional balance
    cannot increase the affordable token horizon. This is the saturation
    boundary for the resource-to-compute channel. -/
theorem affordable_budget_saturates_at_technical_cap
    (balance tokenPrice technicalCap : Nat)
    (coversCapCost : tokenPrice * technicalCap ≤ balance) :
    affordableGenerationBudget balance tokenPrice technicalCap = technicalCap := by
  by_cases priceZero : tokenPrice = 0
  · simp [affordableGenerationBudget, priceZero]
  · have pricePositive : 0 < tokenPrice := Nat.pos_of_ne_zero priceZero
    apply Nat.le_antisymm
    · exact affordable_budget_respects_technical_cap balance tokenPrice technicalCap
    · exact affordable_budget_is_maximal balance tokenPrice technicalCap technicalCap
        pricePositive (Nat.le_refl _) coversCapCost

/-- Saturated balances give exactly the same proposal law when the complete
    prompts match and the computational constitution is fixed. Thus a
    response change while both accounts can afford the technical cap rejects
    the *budget-only, fixed-prompt* channel for that comparison; it does not
    reject resource effects that enter through prompts, other state, or a
    changing constitution. -/
theorem saturated_balances_same_prompt_imply_equal_proposal_law
    {Context Token Proposal : Type}
    (constitution : AutoregressiveConstitution Context Token Proposal)
    (firstContext secondContext : Context)
    (firstBalance secondBalance tokenPrice technicalCap : Nat)
    (firstCoversCap : tokenPrice * technicalCap ≤ firstBalance)
    (secondCoversCap : tokenPrice * technicalCap ≤ secondBalance)
    (samePrompt : constitution.prompt firstContext = constitution.prompt secondContext) :
    proposalLaw constitution firstContext
        (affordableGenerationBudget firstBalance tokenPrice technicalCap) =
      proposalLaw constitution secondContext
        (affordableGenerationBudget secondBalance tokenPrice technicalCap) := by
  rw [affordable_budget_saturates_at_technical_cap firstBalance tokenPrice technicalCap
      firstCoversCap,
    affordable_budget_saturates_at_technical_cap secondBalance tokenPrice technicalCap
      secondCoversCap]
  exact equal_prompt_implies_equal_proposal_law constitution firstContext secondContext
    technicalCap samePrompt

/-- Decision-prefix resource threshold. If the protocol's proposal parser is
    determined by the first `prefixLength` generated tokens, then an account
    that can fund that prefix induces exactly the same proposal-event law as
    the full technical cap. Thus the resource-to-choice channel saturates at
    the decision-completion cost, even when the technical output cap is larger.

    This is a sufficient threshold for the budget-only channel. It requires a
    fixed context/constitution: if balance changes the prompt, model state,
    parser, or token kernel, this theorem does not apply. -/
theorem decision_prefix_balance_suffices_for_full_cap_choice_law
    {Context Token Proposal : Type}
    (constitution : AutoregressiveConstitution Context Token Proposal)
    (prefixLength : Nat)
    (parser : PrefixSufficientParser constitution prefixLength)
    (context : Context) (balance tokenPrice technicalCap : Nat)
    (prefixWithinTechnicalCap : prefixLength ≤ technicalCap)
    (balanceFundsDecisionPrefix : tokenPrice * prefixLength ≤ balance) :
    ∀ event : Proposal → Bool,
      eventMass
          (proposalLaw constitution context
            (affordableGenerationBudget balance tokenPrice technicalCap)) event =
        eventMass (proposalLaw constitution context technicalCap) event := by
  intro event
  by_cases priceZero : tokenPrice = 0
  · simp [affordableGenerationBudget, priceZero]
  · have pricePositive : 0 < tokenPrice := Nat.pos_of_ne_zero priceZero
    have affordableBudgetCoversPrefix : prefixLength ≤
        affordableGenerationBudget balance tokenPrice technicalCap :=
      affordable_budget_is_maximal balance tokenPrice technicalCap prefixLength
        pricePositive prefixWithinTechnicalCap balanceFundsDecisionPrefix
    exact prefix_sufficient_parser_proposal_law_invariant constitution prefixLength parser
      context (affordableGenerationBudget balance tokenPrice technicalCap) technicalCap
      affordableBudgetCoversPrefix prefixWithinTechnicalCap event

/-- End-to-end partial identification from an agent-owned balance to a
    proposal event. Hold the complete encoded context and autoregressive
    constitution fixed, derive each generation horizon from the corresponding
    balance, and require both horizons to cover a common prefix. The change in
    any proposal-event probability is then bounded by the two budgets'
    parser-versus-prefix disagreement masses. The result gives no direction of
    change: more affordable computation does not by itself imply a higher or
    lower probability of any economic action. If the balance is included in
    the prompt, the common-context premise must be replaced by a model that
    accounts for that additional input channel. -/
theorem affordable_balance_change_proposal_event_bound
    {Context Token Proposal : Type} [DecidableEq Proposal]
    (constitution : AutoregressiveConstitution Context Token Proposal)
    (context : Context)
    (firstBalance secondBalance tokenPrice technicalCap prefixLength : Nat)
    (prefixParser : List Token → Proposal)
    (firstCoversPrefix : prefixLength ≤
      affordableGenerationBudget firstBalance tokenPrice technicalCap)
    (secondCoversPrefix : prefixLength ≤
      affordableGenerationBudget secondBalance tokenPrice technicalCap)
    (event : Proposal → Bool) :
    (eventMass
        (proposalLaw constitution context
          (affordableGenerationBudget firstBalance tokenPrice technicalCap)) event ≤
      eventMass
        (proposalLaw constitution context
          (affordableGenerationBudget secondBalance tokenPrice technicalCap)) event +
        prefixParserDisagreementMass constitution context
          (affordableGenerationBudget firstBalance tokenPrice technicalCap)
          prefixLength prefixParser +
        prefixParserDisagreementMass constitution context
          (affordableGenerationBudget secondBalance tokenPrice technicalCap)
          prefixLength prefixParser) ∧
    (eventMass
        (proposalLaw constitution context
          (affordableGenerationBudget secondBalance tokenPrice technicalCap)) event ≤
      eventMass
        (proposalLaw constitution context
          (affordableGenerationBudget firstBalance tokenPrice technicalCap)) event +
        prefixParserDisagreementMass constitution context
          (affordableGenerationBudget firstBalance tokenPrice technicalCap)
          prefixLength prefixParser +
        prefixParserDisagreementMass constitution context
          (affordableGenerationBudget secondBalance tokenPrice technicalCap)
          prefixLength prefixParser) := by
  exact proposal_event_budget_sensitivity_bounded_by_prefix_disagreement
    constitution context
    (affordableGenerationBudget firstBalance tokenPrice technicalCap)
    (affordableGenerationBudget secondBalance tokenPrice technicalCap)
    prefixLength prefixParser firstCoversPrefix secondCoversPrefix event

/-- Resource state specialized to spendable token units. -/
structure TokenAccount where
  spendable : Nat

/-- Cost of a realized generated-token trace under a per-token price schedule. -/
def realizedGenerationCharge {Action Token : Type}
    (tokenPrice : Nat) (proposal : TraceCarryingProposal Action Token) : Nat :=
  tokenPrice * proposal.generatedTokens.length

/-- Remaining spendable balance after charging the realized generated trace. -/
def afterGenerationCharge {Action Token : Type}
    (account : TokenAccount) (tokenPrice : Nat)
    (proposal : TraceCarryingProposal Action Token) : TokenAccount :=
  ⟨account.spendable - realizedGenerationCharge tokenPrice proposal⟩

/-- If the maximum token budget was affordable, every realized output trace
    admitted by that budget is affordable as well. Early stopping can only
    reduce the charge. -/
theorem generated_proposal_charge_fits_balance
    {Action Token : Type}
    (balance tokenPrice : Nat)
    (proposal : TraceCarryingProposal Action Token)
    (budgetAffordable : tokenPrice * proposal.generationBudget ≤ balance) :
    realizedGenerationCharge tokenPrice proposal ≤ balance := by
  unfold realizedGenerationCharge
  calc
    tokenPrice * proposal.generatedTokens.length ≤
        tokenPrice * proposal.generationBudget :=
      Nat.mul_le_mul_left tokenPrice proposal.withinBudget
    _ ≤ balance := budgetAffordable

/-- Exact account closure for an affordable generation charge. -/
theorem affordable_generation_debit_closes_account
    {Action Token : Type}
    (account : TokenAccount) (tokenPrice : Nat)
    (proposal : TraceCarryingProposal Action Token)
    (chargeAffordable : realizedGenerationCharge tokenPrice proposal ≤ account.spendable) :
    (afterGenerationCharge account tokenPrice proposal).spendable +
      realizedGenerationCharge tokenPrice proposal = account.spendable := by
  exact Nat.sub_add_cancel chargeAffordable

/-- An optional model restriction that makes the autoregressive maximum
    generation budget a function of the agent's spendable token balance. The
    technical cap, token price, and ownership of this account are explicit
    application primitives. -/
structure ResourceBoundedResponseProcess
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    (model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production) where
  response : ResponseKernelRepresentation model
  tokenBalance : ResourceState → Nat
  tokenPrice : Nat
  technicalCap : Agent → Nat
  budgetFromBalance : ∀ agent state,
    response.generationBudget agent state =
      affordableGenerationBudget (tokenBalance state.resources) tokenPrice (technicalCap agent)

/-- In the resource-bounded response refinement, the full maximum generation
    budget is affordable from the represented agent balance. -/
theorem resource_bounded_generation_fits_account
    {Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production : Type}
    [DecidableEq Proposal]
    {model : AgentEconomyModel Agent InternalState ResourceState Condition Observation InstitutionalSignal Opportunity Proposal Production}
    (process : ResourceBoundedResponseProcess model)
    (agent : Agent) (state : AgentState InternalState ResourceState) :
    process.tokenPrice * process.response.generationBudget agent state ≤
      process.tokenBalance state.resources := by
  rw [process.budgetFromBalance]
  exact affordable_budget_cost_fits_balance
    (process.tokenBalance state.resources) process.tokenPrice (process.technicalCap agent)

end AgentMicrofoundations.TokenAccounting
