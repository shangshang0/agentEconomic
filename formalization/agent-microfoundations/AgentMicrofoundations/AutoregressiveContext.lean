import AgentMicrofoundations.AutoregressiveResponse
import AgentMicrofoundations.ContextualResponse

/-!
Identification bridge from an autoregressive constitution to contextual
mixtures.

If every positive-probability context has the same complete encoded prompt and
the same resource-conditioned generation budget, a fixed token kernel,
stop-token rule, and parser induce the same conditional proposal law in every
such context. Therefore any event probability is invariant to the context
mixture. This is a falsifiable input-sufficiency restriction, not a claim that
different prompts must produce different behavior.
-/
namespace AgentMicrofoundations.AutoregressiveContext

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AutoregressiveResponse
open AgentMicrofoundations.ContextualResponse

def autoregressiveContextProposalLaw {Context Token Proposal : Type}
    (constitution : AutoregressiveConstitution Context Token Proposal)
    (generationBudget : Context → Nat) : Context → FiniteDistribution Proposal :=
  fun context => proposalLaw constitution context (generationBudget context)

/-- A fixed computational constitution gives the same mixed event probability
    whenever all positive-probability contexts encode the same full prompt and
    generation budget. The budget may be state/resource-dependent; the theorem
    only requires that it agrees on the realized context support. -/
theorem equal_prompt_budget_implies_context_mixture_invariance
    {Context Token Proposal : Type}
    (contexts : FiniteDistribution Context)
    (constitution : AutoregressiveConstitution Context Token Proposal)
    (generationBudget : Context → Nat)
    (event : Proposal → Bool) (reference : Context)
    (samePromptOnSupport : ∀ context weight,
      (context, weight) ∈ contexts.outcomes → weight ≠ 0 →
        constitution.prompt context = constitution.prompt reference)
    (sameBudgetOnSupport : ∀ context weight,
      (context, weight) ∈ contexts.outcomes → weight ≠ 0 →
        generationBudget context = generationBudget reference) :
    eventMass
        (bindDistribution contexts
          (autoregressiveContextProposalLaw constitution generationBudget)) event =
      eventMass (proposalLaw constitution reference (generationBudget reference)) event := by
  exact contextual_event_probability_eq_if_constant_on_support contexts
    (autoregressiveContextProposalLaw constitution generationBudget) event
    (eventMass (proposalLaw constitution reference (generationBudget reference)) event)
    (fun context weight member positiveWeight => by
      have budgetEq := sameBudgetOnSupport context weight member positiveWeight
      have promptEq := samePromptOnSupport context weight member positiveWeight
      have proposalLawEq :
          proposalLaw constitution context (generationBudget context) =
            proposalLaw constitution reference (generationBudget reference) := by
        calc
          proposalLaw constitution context (generationBudget context) =
              proposalLaw constitution context (generationBudget reference) := by
            rw [budgetEq]
          _ = proposalLaw constitution reference (generationBudget reference) :=
            equal_prompt_implies_equal_proposal_law constitution context reference
              (generationBudget reference) promptEq
      change eventMass (proposalLaw constitution context (generationBudget context)) event = _
      rw [proposalLawEq])

end AgentMicrofoundations.AutoregressiveContext
