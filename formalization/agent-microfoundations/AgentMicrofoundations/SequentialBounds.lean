import AgentMicrofoundations.FiniteDynamics
import AgentMicrofoundations.ContextualResponse

/-!
Sequential probability bounds for history-dependent agent economies.

The one-period event probability may depend on the full current state and may
be correlated with every other event in the path. If a uniform conditional
lower/upper bound holds at every reachable state, repeated event probability
is bounded by the corresponding powers. This is a conditional-hazard result,
not an independence or stationary-preference assumption.
-/
namespace AgentMicrofoundations.SequentialBounds

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.ContextualResponse
open AgentMicrofoundations.FiniteDynamics

def weightedStateValue {State : Type} (states : List (State × Rat))
    (value : State → Rat) : Rat :=
  match states with
  | [] => 0
  | (state, weight) :: rest => weight * value state + weightedStateValue rest value

theorem weightedStateValue_le_weightedContextEventMass
    {State Outcome : Type}
    (states : List (State × Rat))
    (response : State → FiniteDistribution Outcome)
    (event : Outcome → Bool) (lower : State → Rat)
    (weightsNonnegative : ∀ state weight, (state, weight) ∈ states → 0 ≤ weight)
    (conditionalLower : ∀ state weight, (state, weight) ∈ states →
      lower state ≤ eventMass (response state) event) :
    weightedStateValue states lower ≤
      weightedContextEventMass states response event := by
  induction states with
  | nil => rfl
  | cons entry rest ih =>
      rcases entry with ⟨state, weight⟩
      have headWeight := weightsNonnegative state weight (by simp)
      have headLower := conditionalLower state weight (by simp)
      have restWeights : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restLower : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest →
            lower candidate ≤ eventMass (response candidate) event := by
        intro candidate candidateWeight member
        exact conditionalLower candidate candidateWeight (by simp [member])
      have tail := ih restWeights restLower
      change weight * lower state + weightedStateValue rest lower ≤
        weight * eventMass (response state) event +
          weightedContextEventMass rest response event
      calc
        weight * lower state + weightedStateValue rest lower ≤
            weight * eventMass (response state) event + weightedStateValue rest lower :=
          Rat.add_le_add_right.mpr (Rat.mul_le_mul_of_nonneg_left headLower headWeight)
        _ ≤ weight * eventMass (response state) event +
            weightedContextEventMass rest response event :=
          Rat.add_le_add_left.mpr tail

theorem weightedStateValue_ge_weightedContextEventMass
    {State Outcome : Type}
    (states : List (State × Rat))
    (response : State → FiniteDistribution Outcome)
    (event : Outcome → Bool) (upper : State → Rat)
    (weightsNonnegative : ∀ state weight, (state, weight) ∈ states → 0 ≤ weight)
    (conditionalUpper : ∀ state weight, (state, weight) ∈ states →
      eventMass (response state) event ≤ upper state) :
    weightedContextEventMass states response event ≤ weightedStateValue states upper := by
  induction states with
  | nil => rfl
  | cons entry rest ih =>
      rcases entry with ⟨state, weight⟩
      have headWeight := weightsNonnegative state weight (by simp)
      have headUpper := conditionalUpper state weight (by simp)
      have restWeights : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restUpper : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest →
            eventMass (response candidate) event ≤ upper candidate := by
        intro candidate candidateWeight member
        exact conditionalUpper candidate candidateWeight (by simp [member])
      have tail := ih restWeights restUpper
      change weight * eventMass (response state) event +
          weightedContextEventMass rest response event ≤
        weight * upper state + weightedStateValue rest upper
      calc
        weight * eventMass (response state) event +
            weightedContextEventMass rest response event ≤
          weight * upper state + weightedContextEventMass rest response event :=
            Rat.add_le_add_right.mpr (Rat.mul_le_mul_of_nonneg_left headUpper headWeight)
        _ ≤ weight * upper state + weightedStateValue rest upper :=
          Rat.add_le_add_left.mpr tail

def weightedIndicatorValue {State : Type} (states : List (State × Rat))
    (event : State → Bool) (amount : Rat) : Rat :=
  match states with
  | [] => 0
  | (state, weight) :: rest =>
      if event state then weight * amount + weightedIndicatorValue rest event amount
      else weightedIndicatorValue rest event amount

theorem weightedIndicatorValue_eq_amount_mul_eventMassEntries
    {State : Type} (states : List (State × Rat))
    (event : State → Bool) (amount : Rat) :
    weightedIndicatorValue states event amount =
      amount * eventMassEntries states event := by
  induction states with
  | nil => simp [weightedIndicatorValue, eventMassEntries]
  | cons entry rest ih =>
      rcases entry with ⟨state, weight⟩
      cases eventValue : event state with
      | false =>
          simp only [weightedIndicatorValue, eventValue]
          have h : eventMassEntries ((state, weight) :: rest) event =
              eventMassEntries rest event := by
            simp [eventMassEntries, eventValue]
          rw [h]
          exact ih
      | true =>
          simp only [weightedIndicatorValue, eventValue]
          have h : eventMassEntries ((state, weight) :: rest) event =
              weight + eventMassEntries rest event := by
            simp [eventMassEntries, eventValue]
          rw [h, ih, Rat.mul_add, Rat.mul_comm weight amount]
          simp

theorem weightedStateValue_eq_weightedIndicatorValue
    {State : Type} (states : List (State × Rat))
    (event : State → Bool) (amount : Rat) :
    weightedStateValue states (fun state => if event state then amount else 0) =
      weightedIndicatorValue states event amount := by
  induction states with
  | nil => rfl
  | cons entry rest ih =>
      rcases entry with ⟨state, weight⟩
      cases eventValue : event state with
      | false => simp [weightedStateValue, weightedIndicatorValue, eventValue, ih,
          Rat.zero_add]
      | true => simp [weightedStateValue, weightedIndicatorValue, eventValue, ih]

abbrev PathObservation (State Observation : Type) := List Observation × State

def pathEventMass {State Observation : Type}
    (transition : State → FiniteDistribution (Observation × State))
    (event : Observation → Bool) (steps : Nat) (state : State) : Rat :=
  eventMass (trajectoryDistribution transition steps state)
    (fun path => path.1.all event)

theorem eventMass_false {Outcome : Type} (distribution : FiniteDistribution Outcome) :
    eventMass distribution (fun _ => false) = 0 := by
  change distribution.outcomes.foldr
      (fun outcome total => if (fun _ => false) outcome.1 then outcome.2 + total else total) 0 = 0
  induction distribution.outcomes with
  | nil => rfl
  | cons outcome rest ih =>
      change rest.foldr
        (fun outcome total => if (fun _ => false) outcome.1 then outcome.2 + total else total) 0 = 0
      exact ih

def continuationLaw {State Observation : Type}
    (transition : State → FiniteDistribution (Observation × State))
    (steps : Nat)
    (step : Observation × State) : FiniteDistribution (PathObservation State Observation) :=
  mapDistribution
    (fun continuation => (step.1 :: continuation.1, continuation.2))
    (trajectoryDistribution transition steps step.2)

theorem pathEventMass_succ_eq_weightedContext
    {State Observation : Type}
    (transition : State → FiniteDistribution (Observation × State))
    (event : Observation → Bool) (steps : Nat) (state : State) :
    pathEventMass transition event (steps + 1) state =
      weightedContextEventMass (transition state).outcomes
        (continuationLaw transition steps)
        (fun path => path.1.all event) := by
  change eventMass
      (bindDistribution (transition state) (fun step =>
        mapDistribution
          (fun continuation => (step.1 :: continuation.1, continuation.2))
          (trajectoryDistribution transition steps step.2)))
      (fun path => path.1.all event) = _
  rw [ContextualResponse.eventMass_bindDistribution]
  rfl

theorem continuation_event_mass_eq_indicator_mul_path_mass
    {State Observation : Type}
    (transition : State → FiniteDistribution (Observation × State))
    (event : Observation → Bool) (steps : Nat)
    (step : Observation × State) :
    eventMass (continuationLaw transition steps step)
      (fun path => path.1.all event) =
      if event step.1 then pathEventMass transition event steps step.2 else 0 := by
  by_cases currentEvent : event step.1
  · change eventMass
      (mapDistribution (fun continuation => (step.1 :: continuation.1, continuation.2))
        (trajectoryDistribution transition steps step.2))
      (fun path => path.1.all event) = _
    rw [eventMass_mapDistribution]
    simp [pathEventMass, currentEvent, List.all_cons]
  · change eventMass
      (mapDistribution (fun continuation => (step.1 :: continuation.1, continuation.2))
        (trajectoryDistribution transition steps step.2))
      (fun path => path.1.all event) = _
    rw [eventMass_mapDistribution]
    simp [currentEvent, List.all_cons, eventMass_false]

theorem pathEventMass_lower_bound
    {State Observation : Type}
    (transition : State → FiniteDistribution (Observation × State))
    (event : Observation → Bool) (lower : Rat)
    (lowerNonnegative : 0 ≤ lower)
    (oneStepLower : ∀ state,
      lower ≤ eventMass (transition state) (fun step => event step.1)) :
    ∀ steps state, lower ^ steps ≤ pathEventMass transition event steps state := by
  intro steps
  induction steps with
  | zero =>
      intro state
      simp [pathEventMass, trajectoryDistribution, pureDistribution, eventMass,
        Rat.add_zero]
  | succ steps ih =>
      intro state
      rw [pathEventMass_succ_eq_weightedContext transition event steps state]
      let lowerForStep : (Observation × State) → Rat := fun step =>
        if event step.1 then lower ^ steps else 0
      have weightedLower := weightedStateValue_le_weightedContextEventMass
        (transition state).outcomes (continuationLaw transition steps)
        (fun path => path.1.all event) lowerForStep
        (transition state).nonnegative
        (by
          intro step weight member
          rw [continuation_event_mass_eq_indicator_mul_path_mass
            transition event steps step]
          dsimp [lowerForStep]
          split
          · exact ih step.2
          · exact Rat.le_refl)
      have valueIdentity :
          weightedStateValue (transition state).outcomes lowerForStep =
            lower ^ steps * eventMass (transition state) (fun step => event step.1) := by
        rw [show lowerForStep = fun step =>
          if event step.1 then lower ^ steps else 0 by rfl]
        rw [weightedStateValue_eq_weightedIndicatorValue]
        rw [weightedIndicatorValue_eq_amount_mul_eventMassEntries]
        rfl
      calc
        lower ^ (steps + 1) = lower ^ steps * lower := Rat.pow_succ lower steps
        _ ≤ lower ^ steps * eventMass (transition state) (fun step => event step.1) :=
          Rat.mul_le_mul_of_nonneg_left (oneStepLower state)
            (Rat.pow_nonneg lowerNonnegative)
        _ = weightedStateValue (transition state).outcomes lowerForStep :=
          valueIdentity.symm
        _ ≤ weightedContextEventMass (transition state).outcomes
            (continuationLaw transition steps) (fun path => path.1.all event) :=
          weightedLower

theorem pathEventMass_upper_bound
    {State Observation : Type}
    (transition : State → FiniteDistribution (Observation × State))
    (event : Observation → Bool) (upper : Rat)
    (upperNonnegative : 0 ≤ upper)
    (oneStepUpper : ∀ state,
      eventMass (transition state) (fun step => event step.1) ≤ upper) :
    ∀ steps state, pathEventMass transition event steps state ≤ upper ^ steps := by
  intro steps
  induction steps with
  | zero =>
      intro state
      simp [pathEventMass, trajectoryDistribution, pureDistribution, eventMass,
        Rat.add_zero]
  | succ steps ih =>
      intro state
      rw [pathEventMass_succ_eq_weightedContext transition event steps state]
      let upperForStep : (Observation × State) → Rat := fun step =>
        if event step.1 then upper ^ steps else 0
      have weightedUpper := weightedStateValue_ge_weightedContextEventMass
        (transition state).outcomes (continuationLaw transition steps)
        (fun path => path.1.all event) upperForStep
        (transition state).nonnegative
        (by
          intro step weight member
          rw [continuation_event_mass_eq_indicator_mul_path_mass
            transition event steps step]
          dsimp [upperForStep]
          split
          · exact ih step.2
          · exact Rat.le_refl)
      have valueIdentity :
          weightedStateValue (transition state).outcomes upperForStep =
            upper ^ steps * eventMass (transition state) (fun step => event step.1) := by
        rw [show upperForStep = fun step =>
          if event step.1 then upper ^ steps else 0 by rfl]
        rw [weightedStateValue_eq_weightedIndicatorValue]
        rw [weightedIndicatorValue_eq_amount_mul_eventMassEntries]
        rfl
      calc
        weightedContextEventMass (transition state).outcomes
            (continuationLaw transition steps) (fun path => path.1.all event) ≤
          weightedStateValue (transition state).outcomes upperForStep :=
          weightedUpper
        _ = upper ^ steps * eventMass (transition state) (fun step => event step.1) :=
          valueIdentity
        _ ≤ upper ^ steps * upper :=
          Rat.mul_le_mul_of_nonneg_left (oneStepUpper state)
            (Rat.pow_nonneg upperNonnegative)
        _ = upper ^ (steps + 1) := (Rat.pow_succ upper steps).symm

/-- Exact geometric survival under a state-uniform conditional event rate.
    Equality of each full-state conditional event probability to `p` implies
    an all-period event probability of `p^steps`, despite arbitrary dependence
    between observations and next states. This recovers the familiar product
    formula from a conditional law, without asserting independent periods. -/
theorem pathEventMass_equals_power_of_constant_conditional_rate
    {State Observation : Type}
    (transition : State → FiniteDistribution (Observation × State))
    (event : Observation → Bool) (probability : Rat)
    (probabilityNonnegative : 0 ≤ probability)
    (oneStepExact : ∀ state,
      eventMass (transition state) (fun step => event step.1) = probability) :
    ∀ steps state, pathEventMass transition event steps state = probability ^ steps := by
  intro steps state
  apply Rat.le_antisymm
  · exact pathEventMass_upper_bound transition event probability probabilityNonnegative
      (fun current => by rw [oneStepExact current]; exact Rat.le_refl) steps state
  · exact pathEventMass_lower_bound transition event probability probabilityNonnegative
      (fun current => by rw [oneStepExact current]; exact Rat.le_refl) steps state

end AgentMicrofoundations.SequentialBounds
