import AgentMicrofoundations.ResponseIdentification

/-!
Distribution-free bounds for persistent events over a finite horizon.

An agent can remain active, solvent, productive, or admitted through a horizon
only if a list of period-specific events all occur. The joint dependence across
periods is left unrestricted. Marginal period probabilities therefore give a
union-bound lower prediction and each individual period gives an upper
prediction. The result is useful precisely when a full temporal response law
is not identified; it does not turn marginal frequencies into an independence
model.
-/
namespace AgentMicrofoundations.TemporalIntersectionBounds

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.ResponseIdentification

theorem eventFold_false {Outcome : Type} (outcomes : List (Outcome × Rat)) :
    eventFold outcomes (fun _ => false) = 0 := by
  induction outcomes with
  | nil => rfl
  | cons head rest ih =>
      change eventFold rest (fun _ => false) = 0
      exact ih

/-- The persistent event: every listed period-specific condition holds. -/
def allEvents {Outcome : Type} (events : List (Outcome → Bool)) : Outcome → Bool :=
  fun outcome => events.all (fun event => event outcome)

/-- Sum of the marginal failure probabilities over the specified horizon. -/
def totalFailureMass {Outcome : Type}
    (law : FiniteDistribution Outcome) (events : List (Outcome → Bool)) : Rat :=
  events.foldr
    (fun event total => eventMass law (fun outcome => !event outcome) + total) 0

/-- At a normalized finite law an event and its complement exhaust the mass. -/
theorem event_and_complement_mass_eq_one
    {Outcome : Type} (law : FiniteDistribution Outcome) (event : Outcome → Bool) :
    eventMass law event + eventMass law (fun outcome => !event outcome) = 1 := by
  have partition : eventFold law.outcomes event +
      eventFold law.outcomes (fun outcome => !event outcome) = mass law.outcomes := by
    induction law.outcomes with
    | nil => simp [eventFold, mass, Rat.zero_add]
    | cons head rest ih =>
        rcases head with ⟨outcome, weight⟩
        cases h : event outcome with
        | false =>
            simp only [eventFold, List.foldr_cons, h, mass]
            change eventFold rest event +
              (weight + eventFold rest (fun value => !event value)) =
              weight + mass rest
            calc
              eventFold rest event +
                  (weight + eventFold rest (fun value => !event value)) =
                weight + (eventFold rest event +
                  eventFold rest (fun value => !event value)) := by ac_rfl
              _ = weight + mass rest := by rw [ih]
        | true =>
            simp only [eventFold, List.foldr_cons, h, ↓reduceIte, mass]
            change (weight + eventFold rest event) +
              eventFold rest (fun value => !event value) =
              weight + mass rest
            calc
              (weight + eventFold rest event) +
                  eventFold rest (fun value => !event value) =
                weight + (eventFold rest event +
                  eventFold rest (fun value => !event value)) := by ac_rfl
              _ = weight + mass rest := by rw [ih]
  simpa [eventMass, eventFold, law.normalized] using partition

/-- Union of failures across a finite horizon. -/
def anyFailure {Outcome : Type} : List (Outcome → Bool) → Outcome → Bool
  | [] => fun _ => false
  | event :: rest => fun outcome => !event outcome || anyFailure rest outcome

/-- The probability of at least one failure is bounded by the sum of the
    period-specific failure probabilities. -/
theorem any_failure_mass_le_sum
    {Outcome : Type} (law : FiniteDistribution Outcome)
    (events : List (Outcome → Bool)) :
    eventMass law (anyFailure events) ≤ totalFailureMass law events := by
  induction events with
  | nil =>
      change eventFold law.outcomes (fun _ => false) ≤ 0
      rw [eventFold_false]
      exact Rat.le_refl
  | cons first rest ih =>
      simp only [anyFailure, totalFailureMass, List.foldr_cons]
      calc
        eventMass law (fun outcome => !first outcome || anyFailure rest outcome) ≤
            eventMass law (fun outcome => !first outcome) +
              eventMass law (anyFailure rest) := by
                simpa [eventMass, eventFold] using
                  (eventFold_union_le_sum law.outcomes
                    (fun outcome => !first outcome) (anyFailure rest) law.nonnegative)
        _ ≤ eventMass law (fun outcome => !first outcome) +
              totalFailureMass law rest :=
                Rat.add_le_add_left.mpr ih

/-- Failure of the persistent event is exactly occurrence of at least one
    listed period failure. -/
theorem not_allEvents_eq_anyFailure
    {Outcome : Type} (events : List (Outcome → Bool)) :
    (fun outcome => !(allEvents events outcome)) = anyFailure events := by
  induction events with
  | nil => rfl
  | cons first rest ih =>
      funext outcome
      simp only [allEvents, List.all_cons, Bool.not_and, anyFailure]
      exact congrArg (fun value => !first outcome || value) (congrFun ih outcome)

/-- Over any finite joint law, the probability that every period-specific
    condition holds is at least one minus the sum of the marginal failure
    probabilities. No independence, stationarity, or Markov assumption is
    needed. For horizons where this lower bound is negative, it is valid but
    uninformative; callers may truncate it at zero. -/
theorem persistent_event_probability_lower_bound
    {Outcome : Type} (law : FiniteDistribution Outcome)
    (events : List (Outcome → Bool)) :
    1 ≤ eventMass law (allEvents events) + totalFailureMass law events := by
  have partition := event_and_complement_mass_eq_one law (allEvents events)
  have failureBound := any_failure_mass_le_sum law events
  rw [← not_allEvents_eq_anyFailure events] at failureBound
  calc
    1 = eventMass law (allEvents events) +
        eventMass law (fun outcome => !(allEvents events outcome)) := partition.symm
    _ ≤ eventMass law (allEvents events) + totalFailureMass law events :=
      Rat.add_le_add_left.mpr failureBound

/-- The persistent event is contained in each listed period event. This is
    the corresponding distribution-free upper bound; it does not presume that
    the period with the smallest marginal rate is known in advance. -/
theorem persistent_event_probability_le_each_period
    {Outcome : Type} (law : FiniteDistribution Outcome)
    (events : List (Outcome → Bool)) (periodEvent : Outcome → Bool)
    (periodMember : periodEvent ∈ events) :
    eventMass law (allEvents events) ≤ eventMass law periodEvent := by
  have supportInclusion : ∀ outcome weight, (outcome, weight) ∈ law.outcomes →
      0 < weight → allEvents events outcome = true → periodEvent outcome = true := by
    intro outcome weight member positive allTrue
    have everyEvent : ∀ event, event ∈ events → event outcome = true := by
      intro event eventMember
      have := List.all_eq_true.mp allTrue event eventMember
      exact this
    exact everyEvent periodEvent periodMember
  have massBound := eventFold_mono_of_support_inclusion law.outcomes
    (allEvents events) periodEvent law.nonnegative supportInclusion
  simpa [eventMass, eventFold] using massBound

/-- If one period's marginal is minimal, it gives the tightest of the direct
    single-period upper bounds. The caller still supplies that finite minimum;
    the theorem does not impose a stationarity or monotone-rate assumption. -/
theorem persistent_event_probability_le_minimum_period_mass
    {Outcome : Type} (law : FiniteDistribution Outcome)
    (events : List (Outcome → Bool)) (minimumEvent : Outcome → Bool)
    (minimumMember : minimumEvent ∈ events) (minimumMass : Rat)
    (minimumMassEq : eventMass law minimumEvent = minimumMass) :
    eventMass law (allEvents events) ≤ minimumMass := by
  calc
    eventMass law (allEvents events) ≤ eventMass law minimumEvent :=
      persistent_event_probability_le_each_period law events minimumEvent minimumMember
    _ = minimumMass := minimumMassEq

/-- If a terminal event is one of the period requirements and implies every
    earlier requirement (the absorbing-state condition), then the probability
    of persistence is exactly the terminal-event probability. This removes
    the temporal-dependence uncertainty without estimating a joint path law.
    In an application, the implication is a short path-replay check: a subject
    that has exited cannot re-enter before the horizon. -/
theorem absorbing_persistence_equals_terminal_mass
    {Outcome : Type} (law : FiniteDistribution Outcome)
    (events : List (Outcome → Bool)) (terminalEvent : Outcome → Bool)
    (terminalMember : terminalEvent ∈ events)
    (terminalImpliesPersistence : ∀ outcome,
      terminalEvent outcome = true → allEvents events outcome = true) :
    eventMass law (allEvents events) = eventMass law terminalEvent := by
  have sameEvent : allEvents events = terminalEvent := by
    funext outcome
    cases all : allEvents events outcome with
    | false =>
        cases terminal : terminalEvent outcome with
        | false => rfl
        | true =>
            have contradiction := terminalImpliesPersistence outcome terminal
            rw [all] at contradiction
            contradiction
    | true =>
        cases terminal : terminalEvent outcome with
        | false =>
            have memberTrue := List.all_eq_true.mp all terminalEvent terminalMember
            rw [terminal] at memberTrue
            contradiction
        | true => rfl
  rw [sameEvent]

/-- A case record for a persistent economic outcome. The sole structural
    restriction is that persistence is the conjunction of listed period-level
    requirements. For survival, each requirement can be reconstructed by
    replaying the balance and execution rule at that period boundary. -/
structure PersistentEventCase (Outcome : Type) where
  law : FiniteDistribution Outcome
  periodRequirements : List (Outcome → Bool)
  survivalEvent : Outcome → Bool
  survivalDecomposes : ∀ outcome,
    survivalEvent outcome = allEvents periodRequirements outcome

/-- For a case whose persistence event is the conjunction of auditable
    period requirements, marginal failure masses imply a lower bound on the
    probability of persistence. Dependence between any periods is arbitrary. -/
theorem case_persistence_lower_bound
    {Outcome : Type} (case : PersistentEventCase Outcome) :
    1 ≤ eventMass case.law case.survivalEvent +
      totalFailureMass case.law case.periodRequirements := by
  have hsurvival : case.survivalEvent = allEvents case.periodRequirements := by
    funext outcome
    exact case.survivalDecomposes outcome
  rw [hsurvival]
  exact persistent_event_probability_lower_bound case.law case.periodRequirements

/-- Any one required period gives an upper bound on case persistence. A
    complete marginal vector therefore yields an interval without inventing a
    temporal dependence law. -/
theorem case_persistence_upper_bound
    {Outcome : Type} (case : PersistentEventCase Outcome)
    (periodEvent : Outcome → Bool) (member : periodEvent ∈ case.periodRequirements) :
    eventMass case.law case.survivalEvent ≤ eventMass case.law periodEvent := by
  have h := persistent_event_probability_le_each_period case.law
    case.periodRequirements periodEvent member
  have hsurvival : case.survivalEvent = allEvents case.periodRequirements := by
    funext outcome
    exact case.survivalDecomposes outcome
  rw [hsurvival]
  exact h

/-- A case may use this predicate as a forecast gate: the resulting interval
    is nonvacuous exactly when the union-bound lower endpoint is nonnegative.
    This does not claim that a wide interval is a failed theory; it records
    the predictive content left after refusing untested dependence assumptions. -/
def lowerBoundIsInformative {Outcome : Type}
    (law : FiniteDistribution Outcome) (events : List (Outcome → Bool)) : Prop :=
  0 ≤ 1 - totalFailureMass law events

end AgentMicrofoundations.TemporalIntersectionBounds
