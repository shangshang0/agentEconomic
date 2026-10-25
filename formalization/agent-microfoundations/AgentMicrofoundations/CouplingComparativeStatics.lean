import AgentMicrofoundations.ResponseIdentification
import AgentMicrofoundations.AnonymousAllocation

/-!
A coupling gives a clean, testable route from a joint law of low/high resource
outcomes to an event-probability comparative static. It does not assume
rational choice or independent agents. The substantive restriction is the
support-wise monotonicity of the paired event; deriving such a coupling from an
autoregressive token process remains a separate obligation.
-/
namespace AgentMicrofoundations.CouplingComparativeStatics

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.ResponseIdentification
open AgentMicrofoundations.AnonymousAllocation

/-- Two finite distributions represent the same probability law when every
    Boolean event has the same mass. This is extensional in outcomes and
    therefore respects duplicate entries in the underlying lists. -/
def SameFiniteLaw {α : Type}
    (first second : FiniteDistribution α) : Prop :=
  ∀ event : α → Bool, eventMass first event = eventMass second event

/-- A finite coupling is a joint law whose pushforward marginal laws agree
    extensionally with the specified outcome laws. Exact list equality is not
    required, because duplicate outcomes are permitted in `FiniteDistribution`. -/
structure FiniteCoupling {α β : Type}
    (firstLaw : FiniteDistribution α) (secondLaw : FiniteDistribution β) where
  joint : FiniteDistribution (α × β)
  firstMarginal : SameFiniteLaw (mapDistribution Prod.fst joint) firstLaw
  secondMarginal : SameFiniteLaw (mapDistribution Prod.snd joint) secondLaw

/-- Probability mass on which two coupled conditions disagree about a
    specified event. Unlike a difference between marginal probabilities, this
    quantity is defined on paired outcomes and can be estimated directly when
    the case supplies matched counterfactual draws. -/
def coupledEventDisagreement {α β : Type}
    (joint : FiniteDistribution (α × β))
    (firstEvent : α → Bool) (secondEvent : β → Bool) : Rat :=
  eventMass joint (fun pair => decide (firstEvent pair.1 ≠ secondEvent pair.2))

/-- A coupling bounds the event-probability contrast by its event-disagreement
    mass. This requires no independence, utility maximization, or sign
    restriction. A useful tight bound requires a substantively justified or
    experimentally available coupling; an arbitrary coupling may give only a
    vacuous bound. -/
theorem event_probability_difference_bounded_by_coupling_disagreement
    {α β : Type}
    {firstLaw : FiniteDistribution α} {secondLaw : FiniteDistribution β}
    (coupling : FiniteCoupling firstLaw secondLaw)
    (firstEvent : α → Bool) (secondEvent : β → Bool) :
    (eventMass firstLaw firstEvent ≤
      eventMass secondLaw secondEvent +
        coupledEventDisagreement coupling.joint firstEvent secondEvent) ∧
    (eventMass secondLaw secondEvent ≤
      eventMass firstLaw firstEvent +
        coupledEventDisagreement coupling.joint firstEvent secondEvent) := by
  have pairedBound := event_probability_difference_bounded_by_mismatch
    coupling.joint (fun pair => firstEvent pair.1)
      (fun pair => secondEvent pair.2) id
  have firstProjection :
      eventMass (mapDistribution (fun pair => firstEvent pair.1) coupling.joint) id =
        eventMass coupling.joint (fun pair => firstEvent pair.1) := by
    rw [eventMass_mapDistribution]
    rfl
  have secondProjection :
      eventMass (mapDistribution (fun pair => secondEvent pair.2) coupling.joint) id =
        eventMass coupling.joint (fun pair => secondEvent pair.2) := by
    rw [eventMass_mapDistribution]
    rfl
  constructor
  · calc
      eventMass firstLaw firstEvent =
          eventMass (mapDistribution Prod.fst coupling.joint) firstEvent :=
        (coupling.firstMarginal firstEvent).symm
      _ = eventMass coupling.joint (fun pair => firstEvent pair.1) :=
        eventMass_mapDistribution Prod.fst coupling.joint firstEvent
      _ ≤ eventMass coupling.joint (fun pair => secondEvent pair.2) +
          coupledEventDisagreement coupling.joint firstEvent secondEvent := by
        calc
          eventMass coupling.joint (fun pair => firstEvent pair.1) =
              eventMass (mapDistribution (fun pair => firstEvent pair.1) coupling.joint) id :=
            firstProjection.symm
          _ ≤ eventMass (mapDistribution (fun pair => secondEvent pair.2) coupling.joint) id +
              eventMass coupling.joint
                (fun pair => decide (firstEvent pair.1 ≠ secondEvent pair.2)) := pairedBound.1
          _ = eventMass coupling.joint (fun pair => secondEvent pair.2) +
              coupledEventDisagreement coupling.joint firstEvent secondEvent := by
                rw [secondProjection]
                rfl
      _ = eventMass (mapDistribution Prod.snd coupling.joint) secondEvent +
          coupledEventDisagreement coupling.joint firstEvent secondEvent := by
        congr 1
        exact (eventMass_mapDistribution Prod.snd coupling.joint secondEvent).symm
      _ = eventMass secondLaw secondEvent +
          coupledEventDisagreement coupling.joint firstEvent secondEvent := by
        congr 1
        exact coupling.secondMarginal secondEvent
  · calc
      eventMass secondLaw secondEvent =
          eventMass (mapDistribution Prod.snd coupling.joint) secondEvent :=
        (coupling.secondMarginal secondEvent).symm
      _ = eventMass coupling.joint (fun pair => secondEvent pair.2) :=
        eventMass_mapDistribution Prod.snd coupling.joint secondEvent
      _ ≤ eventMass coupling.joint (fun pair => firstEvent pair.1) +
          coupledEventDisagreement coupling.joint firstEvent secondEvent := by
        calc
          eventMass coupling.joint (fun pair => secondEvent pair.2) =
              eventMass (mapDistribution (fun pair => secondEvent pair.2) coupling.joint) id :=
            secondProjection.symm
          _ ≤ eventMass (mapDistribution (fun pair => firstEvent pair.1) coupling.joint) id +
              eventMass coupling.joint
                (fun pair => decide (firstEvent pair.1 ≠ secondEvent pair.2)) := pairedBound.2
          _ = eventMass coupling.joint (fun pair => firstEvent pair.1) +
              coupledEventDisagreement coupling.joint firstEvent secondEvent := by
                rw [firstProjection]
                rfl
      _ = eventMass (mapDistribution Prod.fst coupling.joint) firstEvent +
          coupledEventDisagreement coupling.joint firstEvent secondEvent := by
        congr 1
        exact (eventMass_mapDistribution Prod.fst coupling.joint firstEvent).symm
      _ = eventMass firstLaw firstEvent +
          coupledEventDisagreement coupling.joint firstEvent secondEvent := by
        congr 1
        exact coupling.firstMarginal firstEvent

/-- If a joint coupling pairs low-resource and high-resource outcomes so that
    every positive-mass productive low-resource outcome is paired with a
    productive high-resource outcome, then the productive-event probability
    cannot fall. Zero-weight entries impose no restriction. This is a
    sufficient condition, not an unconditional law of resource effects. -/
theorem event_probability_mono_under_support_monotone_coupling
    {LowOutcome HighOutcome : Type}
    {lowLaw : FiniteDistribution LowOutcome}
    {highLaw : FiniteDistribution HighOutcome}
    (coupling : FiniteCoupling lowLaw highLaw)
    (lowEvent : LowOutcome → Bool)
    (highEvent : HighOutcome → Bool)
    (eventPreserved : ∀ pair weight,
      (pair, weight) ∈ coupling.joint.outcomes → 0 < weight →
        lowEvent pair.1 = true → highEvent pair.2 = true) :
    eventMass lowLaw lowEvent ≤ eventMass highLaw highEvent := by
  have firstProjection :
      eventMass (mapDistribution Prod.fst coupling.joint) lowEvent =
        eventMass coupling.joint (fun pair => lowEvent pair.1) :=
    eventMass_mapDistribution Prod.fst coupling.joint lowEvent
  have secondProjection :
      eventMass (mapDistribution Prod.snd coupling.joint) highEvent =
        eventMass coupling.joint (fun pair => highEvent pair.2) :=
    eventMass_mapDistribution Prod.snd coupling.joint highEvent
  calc
    eventMass lowLaw lowEvent =
        eventMass coupling.joint (fun pair => lowEvent pair.1) := by
      calc
        eventMass lowLaw lowEvent =
            eventMass (mapDistribution Prod.fst coupling.joint) lowEvent :=
          (coupling.firstMarginal lowEvent).symm
        _ = eventMass coupling.joint (fun pair => lowEvent pair.1) := firstProjection
    _ ≤ eventMass coupling.joint (fun pair => highEvent pair.2) := by
      exact eventFold_mono_of_support_inclusion coupling.joint.outcomes
        (fun pair => lowEvent pair.1) (fun pair => highEvent pair.2)
        coupling.joint.nonnegative eventPreserved
    _ = eventMass highLaw highEvent := by
      calc
        eventMass coupling.joint (fun pair => highEvent pair.2) =
            eventMass (mapDistribution Prod.snd coupling.joint) highEvent :=
          secondProjection.symm
        _ = eventMass highLaw highEvent := coupling.secondMarginal highEvent

/-- Potential outcomes evaluated on one common exogenous seed. This gives a
    constructive coupling rather than treating the joint law as an unrelated
    extra primitive. The common-seed interpretation is appropriate only when
    the same random-tape semantics can be maintained across the compared runs. -/
structure CommonSeedResponses (Seed LowOutcome HighOutcome : Type) where
  seedLaw : FiniteDistribution Seed
  lowOutcome : Seed → LowOutcome
  highOutcome : Seed → HighOutcome

def lowResponseLaw {Seed LowOutcome HighOutcome : Type}
    (responses : CommonSeedResponses Seed LowOutcome HighOutcome) :
    FiniteDistribution LowOutcome :=
  mapDistribution responses.lowOutcome responses.seedLaw

def highResponseLaw {Seed LowOutcome HighOutcome : Type}
    (responses : CommonSeedResponses Seed LowOutcome HighOutcome) :
    FiniteDistribution HighOutcome :=
  mapDistribution responses.highOutcome responses.seedLaw

def commonSeedCoupling {Seed LowOutcome HighOutcome : Type}
    (responses : CommonSeedResponses Seed LowOutcome HighOutcome) :
    FiniteCoupling (lowResponseLaw responses) (highResponseLaw responses) := by
  refine ⟨mapDistribution (fun seed =>
    (responses.lowOutcome seed, responses.highOutcome seed)) responses.seedLaw,
    ?_, ?_⟩
  · intro event
    calc
      eventMass
          (mapDistribution Prod.fst
            (mapDistribution (fun seed =>
              (responses.lowOutcome seed, responses.highOutcome seed)) responses.seedLaw))
          event =
          eventMass
            (mapDistribution (fun seed =>
              (responses.lowOutcome seed, responses.highOutcome seed)) responses.seedLaw)
            (fun pair => event pair.1) :=
        eventMass_mapDistribution Prod.fst _ event
      _ = eventMass responses.seedLaw
          (fun seed => event (responses.lowOutcome seed)) := by
        simpa using
          (eventMass_mapDistribution
            (fun seed => (responses.lowOutcome seed, responses.highOutcome seed))
            responses.seedLaw (fun pair => event pair.1))
      _ = eventMass (lowResponseLaw responses) event :=
        (eventMass_mapDistribution responses.lowOutcome responses.seedLaw event).symm
  · intro event
    calc
      eventMass
          (mapDistribution Prod.snd
            (mapDistribution (fun seed =>
              (responses.lowOutcome seed, responses.highOutcome seed)) responses.seedLaw))
          event =
          eventMass
            (mapDistribution (fun seed =>
              (responses.lowOutcome seed, responses.highOutcome seed)) responses.seedLaw)
            (fun pair => event pair.2) :=
        eventMass_mapDistribution Prod.snd _ event
      _ = eventMass responses.seedLaw
          (fun seed => event (responses.highOutcome seed)) := by
        simpa using
          (eventMass_mapDistribution
            (fun seed => (responses.lowOutcome seed, responses.highOutcome seed))
            responses.seedLaw (fun pair => event pair.2))
      _ = eventMass (highResponseLaw responses) event :=
        (eventMass_mapDistribution responses.highOutcome responses.seedLaw event).symm

/-- A pathwise event implication under a shared random seed supplies the
    support-monotone coupling condition and hence a probability comparative
    static. This isolates the behavioral assumption needed for monotonicity:
    the event must be preserved seed by seed. -/
theorem event_probability_mono_under_common_seed
    {Seed LowOutcome HighOutcome : Type}
    (responses : CommonSeedResponses Seed LowOutcome HighOutcome)
    (lowEvent : LowOutcome → Bool) (highEvent : HighOutcome → Bool)
    (pathwisePreservation : ∀ seed,
      lowEvent (responses.lowOutcome seed) = true →
        highEvent (responses.highOutcome seed) = true) :
    eventMass (lowResponseLaw responses) lowEvent ≤
      eventMass (highResponseLaw responses) highEvent := by
  apply event_probability_mono_under_support_monotone_coupling
    (commonSeedCoupling responses) lowEvent highEvent
  intro pair weight member positive lowTrue
  change (pair, weight) ∈ mapEntries
    (fun seed => (responses.lowOutcome seed, responses.highOutcome seed))
      responses.seedLaw.outcomes at member
  rcases List.mem_map.mp member with ⟨source, seedMember, outcomeEq⟩
  rcases source with ⟨seed, seedWeight⟩
  have components := Prod.mk.inj outcomeEq
  rcases components with ⟨outcomeEq, weightEq⟩
  cases outcomeEq
  cases weightEq
  exact pathwisePreservation seed lowTrue

end AgentMicrofoundations.CouplingComparativeStatics
