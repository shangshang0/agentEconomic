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

/-- A one-token subject can condition its emitted proposal on a context bit.
    This tiny constitution is used only as a countermodel to any purported
    context-comparative law that has no structural restrictions on the token
    kernel. -/
def contextEchoConstitution (reverse : Bool) :
    Constitution Bool Bool Bool := {
  prompt := fun context => [context]
  nextToken := fun tokenPrefix =>
    pureDistribution (if reverse then !(tokenPrefix.headD false) else tokenPrefix.headD false)
  stopToken := fun _ => true
  parseProposal := fun {_budget} trace => trace.tokens.headD false
}

theorem contextEcho_event_probability (reverse context : Bool) :
    eventProbability (contextEchoConstitution reverse) context 1 id =
      if (if reverse then !context else context) then (1 : Rat) else 0 := by
  cases reverse <;> cases context <;>
    simp [eventProbability, contextEchoConstitution, proposalLaw,
      generatedTokenTrace, extendGeneratedTrace, bindDistribution, bindEntries,
      mapDistribution, mapEntries, scaleEntries, pureDistribution, eventMass,
      Rat.add_zero] <;> try exact Rat.add_zero 1

/-- With an unrestricted context-sensitive token kernel, the same fixed
    protocol can produce either sign of the full [-1,1] comparative effect.
    Thus no strict choice-effect interval follows from computational form and
    parsing alone; at least one independently motivated structural restriction
    is mathematically necessary. -/
theorem unrestricted_context_kernels_realize_both_extreme_effects :
    eventProbabilityChange (contextEchoConstitution false) false 1 true 1 id = 1 ∧
    eventProbabilityChange (contextEchoConstitution true) false 1 true 1 id = -1 := by
  constructor
  · simp only [eventProbabilityChange, contextEcho_event_probability]
    calc
      1 - 0 = 1 + -0 := Rat.sub_eq_add_neg _ _
      _ = 1 := by rw [Rat.neg_zero, Rat.add_zero]
  · simp only [eventProbabilityChange, contextEcho_event_probability]
    calc
      0 - 1 = 0 + -1 := Rat.sub_eq_add_neg _ _
      _ = -1 := Rat.zero_add _

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

/-- The primitive-free model class cannot satisfy the sharp, strict-range
    choice-law target for this context comparison. The two context-echo
    constitutions attain both logical extremes, so at least one independently
    motivated structural restriction is mathematically necessary. -/
theorem no_strict_choice_law_without_context_restrictions :
    ¬ Nonempty (SharpChoiceEffectLaw
      (fun (_ : Constitution Bool Bool Bool) (_ : Bool) (_ : Nat)
        (_ : Bool) (_ : Nat) => True)
      false 1 true 1 id) := by
  intro lawExists
  obtain ⟨law⟩ := lawExists
  have effects := unrestricted_context_kernels_realize_both_extreme_effects
  have lowerBound : law.lower ≤ -1 := by
    have h := (law.sound (contextEchoConstitution true) trivial).1
    rw [effects.2] at h
    exact h
  have upperBound : 1 ≤ law.upper := by
    have h := (law.sound (contextEchoConstitution false) trivial).2
    rw [effects.1] at h
    exact h
  have lowerNegated : 1 ≤ -law.lower := by
    exact Rat.neg_le_neg lowerBound
  have widthLower : (2 : Rat) ≤ 1 + -law.lower := by
    have h := (Rat.add_le_add_left (a := 1) (b := -law.lower) (c := 1)).mpr
      lowerNegated
    have natEq : (2 : Nat) = 1 + 1 := by omega
    have twoEq : (2 : Rat) = 1 + 1 := by
      calc
        (2 : Rat) = ((2 : Nat) : Rat) := rfl
        _ = ((1 + 1 : Nat) : Rat) := congrArg (fun n : Nat => (n : Rat)) natEq
        _ = (1 : Rat) + 1 := Rat.natCast_add 1 1
    rw [twoEq]
    exact h
  have widthUpper : 1 + -law.lower ≤ law.upper + -law.lower :=
    (Rat.add_le_add_right (a := 1) (b := law.upper) (c := -law.lower)).mpr
      upperBound
  have fullWidth : (2 : Rat) ≤ law.upper - law.lower := by
    simpa [Rat.sub_eq_add_neg] using Rat.le_trans widthLower widthUpper
  have widthAtMostTwo : law.upper - law.lower ≤ 2 :=
    Rat.le_of_lt law.strict_restriction
  have widthEqTwo : law.upper - law.lower = 2 :=
    Rat.le_antisymm widthAtMostTwo fullWidth
  have strictWidth := law.strict_restriction
  rw [widthEqTwo] at strictWidth
  exact Rat.lt_irrefl strictWidth

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

/-- The allowed syntax of a primitive in the research certificate.

    This is intentionally a closed grammar rather than an arbitrary predicate:
    an unrestricted `Constitution → ... → Prop` could hide a choice law inside
    a predicate even if it never receives the target event as an argument.
    Constructors are added only when their operational meaning is independently
    auditable. The current grammar contains protocol facts, not preference
    directions. -/
inductive ChoicePrimitive where
  | sameCompletePrompt
  | firstBudgetPositive
  | secondBudgetPositive
  | firstTokenSufficientParser
  deriving DecidableEq, Repr

/-- Operational meaning of the current primitive grammar. -/
def ChoicePrimitive.holds
    {Context Token Proposal : Type} [DecidableEq Proposal]
    (primitive : ChoicePrimitive)
    (constitution : Constitution Context Token Proposal)
    (firstContext : Context) (firstBudget : Nat)
    (secondContext : Context) (secondBudget : Nat) : Prop :=
  match primitive with
  | .sameCompletePrompt =>
      constitution.prompt firstContext = constitution.prompt secondContext
  | .firstBudgetPositive => 0 < firstBudget
  | .secondBudgetPositive => 0 < secondBudget
  | .firstTokenSufficientParser =>
      Nonempty (FirstTokenSufficientParser constitution)

/-- The constitutions admitted by a finite package of structural primitives.
    `Fin n` indexes the assumptions; `n` is explicit so that parsimony and
    assumption-by-assumption ablation can be inspected. -/
def SatisfiesPrimitivePackage
    {Context Token Proposal : Type} [DecidableEq Proposal] {n : Nat}
    (primitives : Fin n → ChoicePrimitive)
    (constitution : Constitution Context Token Proposal)
    (firstContext : Context) (firstBudget : Nat)
    (secondContext : Context) (secondBudget : Nat) : Prop :=
  ∀ i, (primitives i).holds constitution firstContext firstBudget
    secondContext secondBudget

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
  primitives : Fin n → ChoicePrimitive
  uniformSharpLaw : ∀ (firstContext secondContext : Context)
      (firstBudget secondBudget : Nat),
    (∃ constitution, @SatisfiesPrimitivePackage Context Token Proposal inferInstance n
      primitives constitution
      firstContext firstBudget secondContext secondBudget) →
    ∀ (event : Proposal → Bool),
      Nonempty (SharpChoiceEffectLaw
        (@SatisfiesPrimitivePackage Context Token Proposal inferInstance n primitives)
        firstContext firstBudget secondContext secondBudget event)
  primitiveIrredundancy : ∀ (i : Fin n),
    ∃ (constitutionLow constitutionHigh : Constitution Context Token Proposal)
      (firstContext secondContext : Context) (firstBudget secondBudget : Nat)
      (event : Proposal → Bool),
      (∀ j, j ≠ i → (primitives j).holds constitutionLow firstContext firstBudget
        secondContext secondBudget) ∧
      ¬ (primitives i).holds constitutionLow firstContext firstBudget secondContext secondBudget ∧
      (∀ j, j ≠ i → (primitives j).holds constitutionHigh firstContext firstBudget
        secondContext secondBudget) ∧
      ¬ (primitives i).holds constitutionHigh firstContext firstBudget secondContext secondBudget ∧
      eventProbabilityChange constitutionLow firstContext firstBudget
        secondContext secondBudget event = -1 ∧
      eventProbabilityChange constitutionHigh firstContext firstBudget
        secondContext secondBudget event = 1

/-- What would count as having built the requested theory: a Lean inhabitant
    of the certificate for a concrete computational-agent model class, using
    only the closed primitive grammar above. At present this predicate is
    intentionally not inhabited by the general autoregressive model class;
    the existing no-identification theorem explains why. A Lean inhabitant
    still does not establish that a primitive's operational interpretation
    matches a deployed agent; that is a separate audit obligation. -/
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
