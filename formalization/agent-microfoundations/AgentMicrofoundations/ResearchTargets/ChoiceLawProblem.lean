import AgentMicrofoundations.AutoregressiveResponse

/-!
## Research target: a non-circular computational choice law

This file formalizes the success criterion for the next foundation problem; it
does not assert that such a law has already been found. A candidate primitive
restriction is a predicate on the computational constitution, observed
context, and resource budget. It is not allowed to take the target action
event or its probability as an input. Scientific review must still check that
the predicate is independently motivated and cheaply auditable.

The target is a sharp, nontrivial interval prediction for how an action
probability changes between two conditions: every constitution satisfying the
primitives lies in the interval, both endpoints are attainable, and the
interval is strictly narrower than the logical range [-1,1].
-/
namespace AgentMicrofoundations.ResearchTargets.ChoiceLawProblem

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AutoregressiveResponse

abbrev Constitution (Context Token Proposal : Type) [DecidableEq Proposal] :=
  AutoregressiveConstitution Context Token Proposal

/-- The probability of a named proposal event computed from the token-level
    constitution. This is derived by running the autoregressive process and
    applying its parser; no action probability is supplied separately. -/
def eventProbability {Context Token Proposal : Type} [DecidableEq Proposal]
    (constitution : Constitution Context Token Proposal) (context : Context)
    (budget : Nat) (event : Proposal → Bool) : Rat :=
  eventMass (proposalLaw constitution context budget) event

/-- Comparative-static effect on a proposal event between two conditions. -/
def eventProbabilityChange {Context Token Proposal : Type} [DecidableEq Proposal]
    (constitution : Constitution Context Token Proposal)
    (firstContext : Context) (firstBudget : Nat)
    (secondContext : Context) (secondBudget : Nat)
    (event : Proposal → Bool) : Rat :=
  eventProbability constitution secondContext secondBudget event -
    eventProbability constitution firstContext firstBudget event

/-- A sharp interval law induced by a primitive class. The class may inspect
    the constitution and the pair of conditions/budgets, but does not receive
    the target proposal event or its probability as an argument. -/
structure SharpChoiceEffectLaw
    {Context Token Proposal : Type} [DecidableEq Proposal]
    (primitiveClass : Constitution Context Token Proposal →
      Context → Nat → Context → Nat → Prop)
    (firstContext : Context) (firstBudget : Nat)
    (secondContext : Context) (secondBudget : Nat)
    (event : Proposal → Bool) where
  lower : Rat
  upper : Rat
  lower_at_least_minus_one : -1 ≤ lower
  upper_at_most_one : upper ≤ 1
  ordered : lower ≤ upper
  sound : ∀ constitution,
    primitiveClass constitution firstContext firstBudget secondContext secondBudget →
      lower ≤ eventProbabilityChange constitution firstContext firstBudget
        secondContext secondBudget event ∧
        eventProbabilityChange constitution firstContext firstBudget
          secondContext secondBudget event ≤ upper
  lower_attained : ∃ constitution,
    primitiveClass constitution firstContext firstBudget secondContext secondBudget ∧
      eventProbabilityChange constitution firstContext firstBudget
        secondContext secondBudget event = lower
  upper_attained : ∃ constitution,
    primitiveClass constitution firstContext firstBudget secondContext secondBudget ∧
      eventProbabilityChange constitution firstContext firstBudget
        secondContext secondBudget event = upper
  strict_restriction : upper - lower < 2

/-- Completion criterion for a comparative choice question: derive a sharp,
    nontrivial restriction on a probability change from token-level primitives. -/
def SolvesChoiceLawProblem {Context Token Proposal : Type} [DecidableEq Proposal]
    (primitiveClass : Constitution Context Token Proposal →
      Context → Nat → Context → Nat → Prop)
    (firstContext : Context) (firstBudget : Nat)
    (secondContext : Context) (secondBudget : Nat)
    (event : Proposal → Bool) : Prop :=
  Nonempty (SharpChoiceEffectLaw primitiveClass firstContext firstBudget
    secondContext secondBudget event)

/-- One proposed structural primitive. It may constrain a constitution and a
    pair of environments, but cannot take the target action event or its
    probability as an argument. This type-level restriction prevents the most
    direct form of writing the desired choice result into an assumption. -/
abbrev ChoicePrimitive {Context Token Proposal : Type} [DecidableEq Proposal] :=
  Constitution Context Token Proposal → Context → Nat → Context → Nat → Prop

/-- The constitutions admitted by a finite package of structural primitives.
    `Fin n` indexes the assumptions; `n` is explicit so that parsimony and
    assumption-by-assumption ablation can be inspected. -/
def SatisfiesPrimitivePackage
    {Context Token Proposal : Type} [DecidableEq Proposal] {n : Nat}
    (primitives : Fin n → ChoicePrimitive (Context := Context)
      (Token := Token) (Proposal := Proposal))
    (constitution : Constitution Context Token Proposal)
    (firstContext : Context) (firstBudget : Nat)
    (secondContext : Context) (secondBudget : Nat) : Prop :=
  ∀ i, primitives i constitution firstContext firstBudget secondContext secondBudget

/-- A completion certificate for the *research target*, not a new agent
    economic axiom. A completed foundation must use one finite, event-blind
    primitive package and derive a sharp, nontrivial choice-effect interval
    uniformly for every action event whenever the package admits a model.
    Each primitive must also be necessary: deleting it must permit both
    extreme comparative-static effects for some event/environment, otherwise
    that primitive is redundant. Empirical auditability and independent
    motivation remain scientific obligations outside Lean. -/
structure ChoiceFoundationCertificate
    {Context Token Proposal : Type} [DecidableEq Proposal] (n : Nat) where
  primitives : Fin n → ChoicePrimitive (Context := Context)
    (Token := Token) (Proposal := Proposal)
  uniformSharpLaw : ∀ (firstContext secondContext : Context)
      (firstBudget secondBudget : Nat),
    (∃ constitution, SatisfiesPrimitivePackage primitives constitution
      firstContext firstBudget secondContext secondBudget) →
    ∀ (event : Proposal → Bool),
      Nonempty (SharpChoiceEffectLaw
        (SatisfiesPrimitivePackage primitives)
        firstContext firstBudget secondContext secondBudget event)
  primitiveIrredundancy : ∀ (i : Fin n),
    ∃ (constitutionLow constitutionHigh : Constitution Context Token Proposal)
      (firstContext secondContext : Context) (firstBudget secondBudget : Nat)
      (event : Proposal → Bool),
      (∀ j, j ≠ i → primitives j constitutionLow firstContext firstBudget
        secondContext secondBudget) ∧
      (∀ j, j ≠ i → primitives j constitutionHigh firstContext firstBudget
        secondContext secondBudget) ∧
      eventProbabilityChange constitutionLow firstContext firstBudget
        secondContext secondBudget event = -1 ∧
      eventProbabilityChange constitutionHigh firstContext firstBudget
        secondContext secondBudget event = 1

/-- What would count as having built the requested theory: a Lean inhabitant
    of the certificate for a concrete computational-agent model class, with
    its primitive meanings independently audited. At present this predicate
    is intentionally not inhabited by the general autoregressive model class;
    the existing no-identification theorem explains why. -/
def HasCompletedChoiceFoundation
    {Context Token Proposal : Type} [DecidableEq Proposal] (n : Nat) : Prop :=
  Nonempty (ChoiceFoundationCertificate (Context := Context)
    (Token := Token) (Proposal := Proposal) (n := n))

/-- Protocol-level primitive class for a controlled budget comparison: the
    token constitution is fixed, both budgets are positive, the complete
    prompts match, and the proposal parser commits from the first token. -/
def FirstTokenBudgetClass {Context Token Proposal : Type}
    [DecidableEq Proposal]
    : Constitution Context Token Proposal → Context → Nat → Context → Nat → Prop :=
  fun constitution firstContext firstBudget secondContext secondBudget =>
  constitution.prompt firstContext = constitution.prompt secondContext ∧
    0 < firstBudget ∧ 0 < secondBudget ∧
    Nonempty (FirstTokenSufficientParser constitution)

/-- Exact sharp law for the first-token protocol: changing only a positive
    generation horizon cannot change any proposal-event probability. The
    interval [0,0] is attained by the supplied constitution, so this packages
    an existing structural result as a solution of the target interface. -/
theorem firstToken_budget_effect_has_sharp_zero_law
    {Context Token Proposal : Type} [DecidableEq Proposal]
    (constitution : Constitution Context Token Proposal)
    (parser : FirstTokenSufficientParser constitution)
    (firstContext secondContext : Context) (firstBudget secondBudget : Nat)
    (samePrompt : constitution.prompt firstContext = constitution.prompt secondContext)
    (firstPositive : 0 < firstBudget) (secondPositive : 0 < secondBudget)
    (event : Proposal → Bool) :
    SolvesChoiceLawProblem (Context := Context) (Token := Token) (Proposal := Proposal)
      (@FirstTokenBudgetClass Context Token Proposal inferInstance)
      firstContext firstBudget secondContext secondBudget event := by
  have zeroEffect : ∀ (candidate : Constitution Context Token Proposal),
      @FirstTokenBudgetClass Context Token Proposal inferInstance candidate
        firstContext firstBudget secondContext secondBudget →
      eventProbabilityChange (Context := Context) (Token := Token) (Proposal := Proposal)
        candidate firstContext firstBudget secondContext secondBudget event = 0 := by
    intro candidate candidateInClass
    obtain ⟨candidatePrompt, budget₁Positive, budget₂Positive, candidateParser⟩ := candidateInClass
    obtain ⟨candidateParser⟩ := candidateParser
    have contextEquality := congrArg (fun law => eventMass law event)
      (equal_prompt_implies_equal_proposal_law candidate firstContext secondContext
        firstBudget candidatePrompt)
    have budgetEquality :=
      first_token_sufficient_parser_proposal_law_budget_invariant candidate
        candidateParser secondContext firstBudget secondBudget
        budget₁Positive budget₂Positive event
    have equalProbabilities :
        eventProbability candidate secondContext secondBudget event =
          eventProbability candidate firstContext firstBudget event := by
      unfold eventProbability
      exact budgetEquality.symm.trans contextEquality.symm
    unfold eventProbabilityChange
    rw [equalProbabilities]
    exact Rat.sub_self
  refine ⟨{
    lower := 0
    upper := 0
    lower_at_least_minus_one := by decide
    upper_at_most_one := by decide
    ordered := Rat.le_refl
    sound := ?_
    lower_attained := ?_
    upper_attained := ?_
    strict_restriction := by
      rw [Rat.sub_self]
      exact (by decide : (0 : Rat) < 2)
  }⟩
  · intro candidate candidateInClass
    rw [zeroEffect candidate candidateInClass]
    exact ⟨Rat.le_refl, Rat.le_refl⟩
  · refine ⟨constitution, ?_, ?_⟩
    · exact ⟨samePrompt, firstPositive, secondPositive, ⟨parser⟩⟩
    · exact zeroEffect constitution
        ⟨samePrompt, firstPositive, secondPositive, ⟨parser⟩⟩
  · refine ⟨constitution, ?_, ?_⟩
    · exact ⟨samePrompt, firstPositive, secondPositive, ⟨parser⟩⟩
    · exact zeroEffect constitution
        ⟨samePrompt, firstPositive, secondPositive, ⟨parser⟩⟩

end AgentMicrofoundations.ResearchTargets.ChoiceLawProblem
