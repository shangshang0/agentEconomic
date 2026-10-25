import AgentMicrofoundations.Ontology

/-!
Finite mixtures of contextual response laws.

An agent may face an uncertain context even when its conditional response law
is fixed. This module proves the finite law of total probability and shows
that context-specific probability bounds survive arbitrary context mixing.
It assumes neither stable action probabilities across contexts nor
independence between the context and any upstream process that generated it.
-/
namespace AgentMicrofoundations.ContextualResponse

open AgentMicrofoundations.Ontology

def eventMassList {α : Type} : List (α × Rat) → (α → Bool) → Rat
  | [], _ => 0
  | (value, weight) :: rest, event =>
      if event value then weight + eventMassList rest event else eventMassList rest event

def weightedContextEventMass {Context Outcome : Type}
    (contexts : List (Context × Rat))
    (response : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) : Rat :=
  match contexts with
  | [] => 0
  | (context, weight) :: rest =>
      weight * eventMass (response context) event +
        weightedContextEventMass rest response event

theorem eventMassList_append {α : Type} (first second : List (α × Rat))
    (event : α → Bool) :
    eventMassList (first ++ second) event =
      eventMassList first event + eventMassList second event := by
  induction first with
  | nil => simp [eventMassList, Rat.zero_add]
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      change (if event value then weight + eventMassList (rest ++ second) event
        else eventMassList (rest ++ second) event) =
        (if event value then weight + eventMassList rest event
          else eventMassList rest event) + eventMassList second event
      cases eventValue : event value with
      | false => simp [ih]
      | true =>
          simp [ih, Rat.add_assoc]

theorem eventMassList_scaleEntries {α : Type} (factor : Rat)
    (outcomes : List (α × Rat)) (event : α → Bool) :
    eventMassList (scaleEntries factor outcomes) event =
      factor * eventMassList outcomes event := by
  induction outcomes with
  | nil => simp [eventMassList, scaleEntries]
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      change eventMassList ((value, factor * weight) :: scaleEntries factor rest) event =
        factor * eventMassList ((value, weight) :: rest) event
      cases eventValue : event value with
      | false =>
          simp only [eventMassList, eventValue]
          exact ih
      | true =>
          simp only [eventMassList, eventValue, ↓reduceIte]
          rw [ih, Rat.mul_add]

theorem eventMassList_eq_foldr {α : Type} (outcomes : List (α × Rat))
    (event : α → Bool) :
    eventMassList outcomes event =
      outcomes.foldr
        (fun outcome total => if event outcome.1 then outcome.2 + total else total) 0 := by
  induction outcomes with
  | nil => rfl
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      cases eventValue : event value <;> simp [eventMassList, eventValue, ih]

theorem eventMassList_bindEntries {Context Outcome : Type}
    (contexts : List (Context × Rat))
    (response : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) :
    eventMassList (bindEntries contexts (fun context => (response context).outcomes)) event =
      weightedContextEventMass contexts response event := by
  induction contexts with
  | nil => rfl
  | cons head rest ih =>
      rcases head with ⟨context, weight⟩
      change eventMassList
          (scaleEntries weight (response context).outcomes ++
            bindEntries rest (fun value => (response value).outcomes)) event =
        weight * eventMass (response context) event +
          weightedContextEventMass rest response event
      rw [eventMassList_append, eventMassList_scaleEntries, ih]
      have kernelEventMass : eventMassList (response context).outcomes event =
          eventMass (response context) event := by
        unfold eventMass
        exact eventMassList_eq_foldr (response context).outcomes event
      rw [kernelEventMass]

/-- The event probability after first drawing a context and then drawing the
    agent's context-conditional response is the context-weighted mean of the
    conditional event probabilities. -/
theorem eventMass_bindDistribution {Context Outcome : Type}
    (contexts : FiniteDistribution Context)
    (response : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) :
  eventMass (bindDistribution contexts response) event =
      weightedContextEventMass contexts.outcomes response event := by
  unfold eventMass bindDistribution
  rw [← eventMassList_eq_foldr]
  exact eventMassList_bindEntries contexts.outcomes response event

/-- If two conditional laws assign the same event probability at every
    context, mixing them over the same context lottery preserves that equality.
    This is the extensional kernel-composition step used when tracing a
    mechanism effect through a stochastic state-dependent response. -/
theorem weightedContextEventMass_congr {Context Outcome : Type}
    (contexts : List (Context × Rat))
    (first second : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool)
    (conditionalEquality : ∀ context,
      eventMass (first context) event = eventMass (second context) event) :
    weightedContextEventMass contexts first event =
      weightedContextEventMass contexts second event := by
  induction contexts with
  | nil => rfl
  | cons entry rest ih =>
      rcases entry with ⟨context, weight⟩
      simp only [weightedContextEventMass]
      rw [conditionalEquality context, ih]

/-- Mapping each context-conditional outcome before mixing is equivalent to
    mapping the event after the mixture. This lets prefix-level observables be
    compared even when the underlying trace types carry different budget
    indices. -/
theorem weightedContextEventMass_mapDistribution
    {Context Outcome Mapped : Type}
    (contexts : List (Context × Rat))
    (response : Context → FiniteDistribution Outcome)
    (transform : Outcome → Mapped) (event : Mapped → Bool) :
    weightedContextEventMass contexts response
        (fun outcome => event (transform outcome)) =
      weightedContextEventMass contexts
        (fun context => mapDistribution transform (response context)) event := by
  induction contexts with
  | nil => rfl
  | cons entry rest ih =>
      rcases entry with ⟨context, weight⟩
      simp only [weightedContextEventMass]
      rw [eventMass_mapDistribution, ih]

/-- A transformed outcome event after a context-conditioned response is
    the same as first pushing each response law through the transform and then
    mixing. -/
theorem eventMass_map_bindDistribution
    {Context Outcome Mapped : Type}
    (contexts : FiniteDistribution Context)
    (response : Context → FiniteDistribution Outcome)
    (transform : Outcome → Mapped) (event : Mapped → Bool) :
    eventMass (mapDistribution transform (bindDistribution contexts response)) event =
      weightedContextEventMass contexts.outcomes
        (fun context => mapDistribution transform (response context)) event := by
  calc
    eventMass (mapDistribution transform (bindDistribution contexts response)) event =
        eventMass (bindDistribution contexts response)
          (fun outcome => event (transform outcome)) :=
      eventMass_mapDistribution transform (bindDistribution contexts response) event
    _ = weightedContextEventMass contexts.outcomes response
          (fun outcome => event (transform outcome)) :=
      eventMass_bindDistribution contexts response (fun outcome => event (transform outcome))
    _ = weightedContextEventMass contexts.outcomes
          (fun context => mapDistribution transform (response context)) event :=
      weightedContextEventMass_mapDistribution contexts.outcomes response transform event

/-- Mixing a deterministic response is exactly the event mass of the mapped
    context lottery. This records the no-additional-randomness case of the
    finite law of total probability. -/
theorem weightedContextEventMass_pure {Context Outcome : Type}
    (contexts : List (Context × Rat)) (response : Context → Outcome)
    (event : Outcome → Bool) :
    weightedContextEventMass contexts
        (fun context => pureDistribution (response context)) event =
      eventMassList contexts (fun context => event (response context)) := by
  induction contexts with
  | nil => rfl
  | cons entry rest ih =>
      rcases entry with ⟨context, weight⟩
      simp only [weightedContextEventMass]
      rw [ih]
      cases eventValue : event (response context) <;>
        simp [eventValue, eventMass, pureDistribution, eventMassList,
          Rat.zero_add, Rat.add_zero, Rat.mul_one]

theorem weightedContextEventMass_lower {Context Outcome : Type}
    (contexts : List (Context × Rat))
    (response : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) (lower : Rat)
    (weightsNonnegative : ∀ context weight, (context, weight) ∈ contexts → 0 ≤ weight)
    (conditionalLower : ∀ context weight, (context, weight) ∈ contexts →
      weight = 0 ∨ lower ≤ eventMass (response context) event) :
    lower * mass contexts ≤ weightedContextEventMass contexts response event := by
  induction contexts with
  | nil => simp [weightedContextEventMass, mass]
  | cons head rest ih =>
      rcases head with ⟨context, weight⟩
      have headWeightNonnegative : 0 ≤ weight := weightsNonnegative context weight (by simp)
      have headCondition := conditionalLower context weight (by simp)
      have headBound : weight * lower ≤
          weight * eventMass (response context) event := by
        rcases headCondition with zeroWeight | lowerBound
        · simp [zeroWeight]
        · exact Rat.mul_le_mul_of_nonneg_left lowerBound headWeightNonnegative
      have restWeightsNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restConditionalLower : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest →
            candidateWeight = 0 ∨ lower ≤ eventMass (response candidate) event := by
        intro candidate candidateWeight member
        exact conditionalLower candidate candidateWeight (by simp [member])
      have restBound := ih restWeightsNonnegative restConditionalLower
      simp only [weightedContextEventMass, mass]
      rw [Rat.mul_add]
      calc
        lower * weight + lower * mass rest = weight * lower + lower * mass rest := by
          rw [Rat.mul_comm lower weight]
        _ ≤ weight * eventMass (response context) event +
            weightedContextEventMass rest response event := by
          calc
            weight * lower + lower * mass rest ≤
                weight * eventMass (response context) event + lower * mass rest :=
              Rat.add_le_add_right.mpr headBound
            _ ≤ weight * eventMass (response context) event +
                weightedContextEventMass rest response event :=
              Rat.add_le_add_left.mpr restBound

theorem weightedContextEventMass_upper {Context Outcome : Type}
    (contexts : List (Context × Rat))
    (response : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) (upper : Rat)
    (weightsNonnegative : ∀ context weight, (context, weight) ∈ contexts → 0 ≤ weight)
    (conditionalUpper : ∀ context weight, (context, weight) ∈ contexts →
      weight = 0 ∨ eventMass (response context) event ≤ upper) :
    weightedContextEventMass contexts response event ≤ upper * mass contexts := by
  induction contexts with
  | nil => simp [weightedContextEventMass, mass]
  | cons head rest ih =>
      rcases head with ⟨context, weight⟩
      have headWeightNonnegative : 0 ≤ weight := weightsNonnegative context weight (by simp)
      have headCondition := conditionalUpper context weight (by simp)
      have headBound : weight * eventMass (response context) event ≤ weight * upper := by
        rcases headCondition with zeroWeight | upperBound
        · simp [zeroWeight]
        · exact Rat.mul_le_mul_of_nonneg_left upperBound headWeightNonnegative
      have restWeightsNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restConditionalUpper : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest →
            candidateWeight = 0 ∨ eventMass (response candidate) event ≤ upper := by
        intro candidate candidateWeight member
        exact conditionalUpper candidate candidateWeight (by simp [member])
      have restBound := ih restWeightsNonnegative restConditionalUpper
      simp only [weightedContextEventMass, mass]
      calc
        weight * eventMass (response context) event +
            weightedContextEventMass rest response event ≤
          weight * upper + weightedContextEventMass rest response event :=
            Rat.add_le_add_right.mpr headBound
        _ ≤ weight * upper + upper * mass rest := Rat.add_le_add_left.mpr restBound
        _ = upper * (weight + mass rest) := by
          rw [Rat.mul_add]
          rw [Rat.mul_comm upper weight]

/-- If every positive-mass context has the same conditional event probability,
    the weighted conditional probability equals that constant times total
    context mass. Zero-mass entries impose no restriction. -/
theorem weightedContextEventMass_eq_constant {Context Outcome : Type}
    (contexts : List (Context × Rat))
    (response : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) (probability : Rat)
    (weightsNonnegative : ∀ context weight, (context, weight) ∈ contexts → 0 ≤ weight)
    (conditionalEquality : ∀ context weight, (context, weight) ∈ contexts →
      weight = 0 ∨ eventMass (response context) event = probability) :
    weightedContextEventMass contexts response event = probability * mass contexts := by
  induction contexts with
  | nil => simp [weightedContextEventMass, mass]
  | cons head rest ih =>
      rcases head with ⟨context, weight⟩
      have headEquality : weight * eventMass (response context) event =
          weight * probability := by
        rcases conditionalEquality context weight (by simp) with zeroWeight | lawEq
        · simp [zeroWeight]
        · rw [lawEq]
      have restWeightsNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restConditionalEquality : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest →
            candidateWeight = 0 ∨ eventMass (response candidate) event = probability := by
        intro candidate candidateWeight member
        exact conditionalEquality candidate candidateWeight (by simp [member])
      have restEq := ih restWeightsNonnegative restConditionalEquality
      simp only [weightedContextEventMass, mass]
      rw [headEquality, restEq, Rat.mul_add, Rat.mul_comm probability weight]

/-- A normalized context lottery preserves a common conditional event
    probability exactly, even when the context distribution itself is unknown
    to the predictor. -/
theorem contextual_event_probability_eq_if_constant_on_support
    {Context Outcome : Type}
    (contexts : FiniteDistribution Context)
    (response : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) (probability : Rat)
    (conditionalEquality : ∀ context weight,
      (context, weight) ∈ contexts.outcomes → weight ≠ 0 →
        eventMass (response context) event = probability) :
    eventMass (bindDistribution contexts response) event = probability := by
  rw [eventMass_bindDistribution]
  calc
    weightedContextEventMass contexts.outcomes response event =
        probability * mass contexts.outcomes :=
      weightedContextEventMass_eq_constant contexts.outcomes response event probability
        contexts.nonnegative (fun context weight member => by
          by_cases zeroWeight : weight = 0
          · exact Or.inl zeroWeight
          · exact Or.inr (conditionalEquality context weight member zeroWeight))
    _ = probability := by rw [contexts.normalized, Rat.mul_one]

/-- Context variation cannot push the unconditional event probability outside
    bounds that hold in every context. Since the context distribution is
    normalized, this is a convexity result, not an assumption of context
    independence or preference stability. -/
theorem contextual_event_probability_respects_uniform_bounds
    {Context Outcome : Type}
    (contexts : FiniteDistribution Context)
    (response : Context → FiniteDistribution Outcome)
    (event : Outcome → Bool) (lower upper : Rat)
    (conditionalBounds : ∀ context weight,
      (context, weight) ∈ contexts.outcomes → weight ≠ 0 →
        lower ≤ eventMass (response context) event ∧
          eventMass (response context) event ≤ upper) :
    lower ≤ eventMass (bindDistribution contexts response) event ∧
      eventMass (bindDistribution contexts response) event ≤ upper := by
  rw [eventMass_bindDistribution]
  constructor
  · calc
      lower = lower * mass contexts.outcomes := by rw [contexts.normalized, Rat.mul_one]
      _ ≤ weightedContextEventMass contexts.outcomes response event :=
        weightedContextEventMass_lower contexts.outcomes response event lower
          contexts.nonnegative (fun context weight member => by
            by_cases zeroWeight : weight = 0
            · exact Or.inl zeroWeight
            · exact Or.inr ((conditionalBounds context weight member zeroWeight).1))
  · calc
      weightedContextEventMass contexts.outcomes response event ≤
          upper * mass contexts.outcomes :=
        weightedContextEventMass_upper contexts.outcomes response event upper
          contexts.nonnegative (fun context weight member => by
            by_cases zeroWeight : weight = 0
            · exact Or.inl zeroWeight
            · exact Or.inr ((conditionalBounds context weight member zeroWeight).2))
      _ = upper := by rw [contexts.normalized, Rat.mul_one]

end AgentMicrofoundations.ContextualResponse
