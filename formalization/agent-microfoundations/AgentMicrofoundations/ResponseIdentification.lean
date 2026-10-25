import AgentMicrofoundations.Ontology

/-!
Sharp identification boundary for an unrestricted agent response law.

Feasibility, resources, and production determine which proposals can occur,
but do not select among feasible proposals. If both an event and its
complement contain a feasible proposal, every rational event probability in
[0, 1] is compatible with the same feasibility restriction. This is a
non-identification theorem, not a behavioral assumption about real agents.
-/
namespace AgentMicrofoundations.ResponseIdentification

open AgentMicrofoundations.Ontology

/-- Event mass before imposing a probability-law structure. -/
def eventFold {α : Type} (outcomes : List (α × Rat)) (event : α → Bool) : Rat :=
  outcomes.foldr
    (fun outcome total => if event outcome.1 then outcome.2 + total else total) 0

theorem eventFold_nonnegative {α : Type} (outcomes : List (α × Rat))
    (event : α → Bool)
    (weightsNonnegative : ∀ value weight, (value, weight) ∈ outcomes → 0 ≤ weight) :
    0 ≤ eventFold outcomes event := by
  induction outcomes with
  | nil => simp [eventFold]
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      simp only [eventFold, List.foldr_cons]
      cases eventValue : event value with
      | false =>
          simp only [Bool.false_eq_true, ↓reduceIte]
          exact ih (fun candidate candidateWeight member =>
            weightsNonnegative candidate candidateWeight (by simp [member]))
      | true =>
          simp only [↓reduceIte]
          apply Rat.add_nonneg
          · exact weightsNonnegative value weight (by simp)
          · exact ih (fun candidate candidateWeight member =>
              weightsNonnegative candidate candidateWeight (by simp [member]))

theorem eventFold_le_mass {α : Type} (outcomes : List (α × Rat))
    (event : α → Bool)
    (weightsNonnegative : ∀ value weight, (value, weight) ∈ outcomes → 0 ≤ weight) :
    eventFold outcomes event ≤ mass outcomes := by
  induction outcomes with
  | nil => simp [eventFold, mass]
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      simp only [eventFold, List.foldr_cons, mass]
      cases eventValue : event value with
      | false =>
          simp only [Bool.false_eq_true, ↓reduceIte]
          have tailBound := ih (fun candidate candidateWeight member =>
            weightsNonnegative candidate candidateWeight (by simp [member]))
          have headNonnegative : 0 ≤ weight := weightsNonnegative value weight (by simp)
          calc
            eventFold rest event ≤ weight + eventFold rest event := by
              calc
                eventFold rest event = 0 + eventFold rest event := by
                  exact (Rat.zero_add _).symm
                _ ≤ weight + eventFold rest event :=
                  Rat.add_le_add_right.mpr headNonnegative
            _ ≤ weight + mass rest := Rat.add_le_add_left.mpr tailBound
      | true =>
          simp only [↓reduceIte]
          have tailBound := ih (fun candidate candidateWeight member =>
            weightsNonnegative candidate candidateWeight (by simp [member]))
          exact Rat.add_le_add_left.mpr tailBound

theorem eventMass_nonnegative {α : Type} (law : FiniteDistribution α)
    (event : α → Bool) : 0 ≤ eventMass law event := by
  exact eventFold_nonnegative law.outcomes event law.nonnegative

theorem eventMass_le_one {α : Type} (law : FiniteDistribution α)
    (event : α → Bool) : eventMass law event ≤ 1 := by
  calc
    eventMass law event ≤ mass law.outcomes := by
      exact eventFold_le_mass law.outcomes event law.nonnegative
    _ = 1 := law.normalized

/-- Event probability is monotone under support-wise event inclusion on a
    common finite outcome law. Zero-weight listed outcomes are deliberately
    ignored: only positive-probability outcomes constrain the inclusion. -/
theorem eventFold_mono_of_support_inclusion {α : Type}
    (outcomes : List (α × Rat)) (lowerEvent upperEvent : α → Bool)
    (weightsNonnegative : ∀ value weight, (value, weight) ∈ outcomes → 0 ≤ weight)
    (supportInclusion : ∀ value weight, (value, weight) ∈ outcomes →
      0 < weight → lowerEvent value = true → upperEvent value = true) :
    eventFold outcomes lowerEvent ≤ eventFold outcomes upperEvent := by
  induction outcomes with
  | nil => simp [eventFold]
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      have restNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have restInclusion : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 < candidateWeight →
            lowerEvent candidate = true → upperEvent candidate = true := by
        intro candidate candidateWeight member positive lowerTrue
        exact supportInclusion candidate candidateWeight (by simp [member]) positive lowerTrue
      have tailMono := ih restNonnegative restInclusion
      have headNonnegative : 0 ≤ weight := weightsNonnegative value weight (by simp)
      by_cases lowerTrue : lowerEvent value = true
      · have upperTrueOrZero : weight = 0 ∨ upperEvent value = true := by
          by_cases weightZero : weight = 0
          · exact Or.inl weightZero
          · have notLeZero : ¬ weight ≤ 0 := by
              intro weightLeZero
              have weightEqZero : weight = 0 := Rat.le_antisymm weightLeZero headNonnegative
              exact weightZero weightEqZero
            have positive : 0 < weight := Rat.not_le.mp notLeZero
            exact Or.inr (supportInclusion value weight (by simp) positive lowerTrue)
        rcases upperTrueOrZero with weightZero | upperTrue
        · simpa [eventFold, lowerTrue, weightZero, Rat.zero_add] using tailMono
        · simpa [eventFold, lowerTrue, upperTrue, Rat.zero_add] using
            (Rat.add_le_add_left.mpr tailMono)
      · by_cases upperTrue : upperEvent value = true
        · simp [eventFold, lowerTrue, upperTrue]
          calc
            eventFold rest lowerEvent = 0 + eventFold rest lowerEvent := by
              rw [Rat.zero_add]
            _ ≤ weight + eventFold rest lowerEvent :=
              Rat.add_le_add_right.mpr headNonnegative
            _ ≤ weight + eventFold rest upperEvent :=
              Rat.add_le_add_left.mpr tailMono
        · simp [eventFold, lowerTrue, upperTrue]
          exact tailMono

/-- The finite union bound for two events under a nonnegative weighted law.
    This elementary probability inequality is used below to quantify how a
    change in a deterministic parser can alter an event probability. -/
theorem eventFold_union_le_sum {α : Type}
    (outcomes : List (α × Rat)) (first second : α → Bool)
    (weightsNonnegative : ∀ value weight, (value, weight) ∈ outcomes → 0 ≤ weight) :
    eventFold outcomes (fun value => first value || second value) ≤
      eventFold outcomes first + eventFold outcomes second := by
  induction outcomes with
  | nil =>
      change 0 ≤ 0 + 0
      rw [Rat.zero_add]
      exact Rat.le_refl
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      have headNonnegative : 0 ≤ weight := weightsNonnegative value weight (by simp)
      have restNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have tailBound := ih restNonnegative
      change (if first value || second value then
          weight + eventFold rest (fun item => first item || second item) else
          eventFold rest (fun item => first item || second item)) ≤
        (if first value then weight + eventFold rest first else eventFold rest first) +
          (if second value then weight + eventFold rest second else eventFold rest second)
      cases firstValue : first value <;> cases secondValue : second value <;>
        simp only [firstValue, secondValue, Bool.false_eq_true, ↓reduceIte]
      · exact tailBound
      · calc
          weight + eventFold rest (fun item => first item || second item) ≤
              weight + (eventFold rest first + eventFold rest second) :=
                Rat.add_le_add_left.mpr tailBound
          _ = eventFold rest first + (weight + eventFold rest second) := by ac_rfl
      · calc
          weight + eventFold rest (fun item => first item || second item) ≤
              weight + (eventFold rest first + eventFold rest second) :=
                Rat.add_le_add_left.mpr tailBound
          _ = (weight + eventFold rest first) + eventFold rest second := by ac_rfl
      · calc
          weight + eventFold rest (fun item => first item || second item) ≤
              weight + (eventFold rest first + eventFold rest second) :=
                Rat.add_le_add_left.mpr tailBound
          _ ≤ (weight + eventFold rest first) +
              (weight + eventFold rest second) := by
                have addWeight : weight + (eventFold rest first + eventFold rest second) ≤
                    (weight + (eventFold rest first + eventFold rest second)) + weight :=
                  calc
                    weight + (eventFold rest first + eventFold rest second) =
                        (weight + (eventFold rest first + eventFold rest second)) + 0 :=
                      (Rat.add_zero _).symm
                    _ ≤ (weight + (eventFold rest first + eventFold rest second)) + weight :=
                      Rat.add_le_add_left.mpr headNonnegative
                calc
                  weight + (eventFold rest first + eventFold rest second) ≤
                      (weight + (eventFold rest first + eventFold rest second)) + weight :=
                    addWeight
                  _ = (weight + eventFold rest first) +
                      (weight + eventFold rest second) := by ac_rfl

/-- Under any common finite coupling, an event's probability can change by no
    more than the probability that the paired outcomes differ. The statement
    is two-sided and makes no monotonicity or independence assumption. -/
theorem event_probability_difference_bounded_by_mismatch
    {Source Outcome : Type} [DecidableEq Outcome]
    (law : FiniteDistribution Source) (firstMap secondMap : Source → Outcome)
    (event : Outcome → Bool) :
    (eventMass (mapDistribution firstMap law) event ≤
        eventMass (mapDistribution secondMap law) event +
          eventMass law (fun source => decide (firstMap source ≠ secondMap source))) ∧
      (eventMass (mapDistribution secondMap law) event ≤
        eventMass (mapDistribution firstMap law) event +
          eventMass law (fun source => decide (firstMap source ≠ secondMap source))) := by
  have firstIncl : ∀ source weight, (source, weight) ∈ law.outcomes → 0 < weight →
      event (firstMap source) = true →
      (event (secondMap source) || decide (firstMap source ≠ secondMap source)) = true := by
    intro source weight _ _ firstTrue
    by_cases mismatch : firstMap source = secondMap source
    · have secondTrue : event (secondMap source) = true := by
        simpa [mismatch] using firstTrue
      simp [secondTrue]
    · simp [mismatch]
  have secondIncl : ∀ source weight, (source, weight) ∈ law.outcomes → 0 < weight →
      event (secondMap source) = true →
      (event (firstMap source) || decide (firstMap source ≠ secondMap source)) = true := by
    intro source weight _ _ secondTrue
    by_cases mismatch : firstMap source = secondMap source
    · have firstTrue : event (firstMap source) = true := by
        simpa [mismatch] using secondTrue
      simp [firstTrue]
    · simp [mismatch]
  have firstBelowUnion := eventFold_mono_of_support_inclusion law.outcomes
    (fun source => event (firstMap source))
    (fun source => event (secondMap source) || decide (firstMap source ≠ secondMap source))
    law.nonnegative firstIncl
  have secondBelowUnion := eventFold_mono_of_support_inclusion law.outcomes
    (fun source => event (secondMap source))
    (fun source => event (firstMap source) || decide (firstMap source ≠ secondMap source))
    law.nonnegative secondIncl
  have firstUnionBound := eventFold_union_le_sum law.outcomes
    (fun source => event (secondMap source))
    (fun source => decide (firstMap source ≠ secondMap source)) law.nonnegative
  have secondUnionBound := eventFold_union_le_sum law.outcomes
    (fun source => event (firstMap source))
    (fun source => decide (firstMap source ≠ secondMap source)) law.nonnegative
  constructor
  · calc
      eventMass (mapDistribution firstMap law) event =
          eventMass law (fun source => event (firstMap source)) :=
        eventMass_mapDistribution firstMap law event
      _ ≤ eventMass law (fun source =>
          event (secondMap source) || decide (firstMap source ≠ secondMap source)) := by
            simpa [eventMass, eventFold] using firstBelowUnion
      _ ≤ eventMass law (fun source => event (secondMap source)) +
          eventMass law (fun source => decide (firstMap source ≠ secondMap source)) := by
            simpa [eventMass, eventFold] using firstUnionBound
      _ = eventMass (mapDistribution secondMap law) event +
          eventMass law (fun source => decide (firstMap source ≠ secondMap source)) := by
            rw [eventMass_mapDistribution]
  · calc
      eventMass (mapDistribution secondMap law) event =
          eventMass law (fun source => event (secondMap source)) :=
        eventMass_mapDistribution secondMap law event
      _ ≤ eventMass law (fun source =>
          event (firstMap source) || decide (firstMap source ≠ secondMap source)) := by
            simpa [eventMass, eventFold] using secondBelowUnion
      _ ≤ eventMass law (fun source => event (firstMap source)) +
          eventMass law (fun source => decide (firstMap source ≠ secondMap source)) := by
            simpa [eventMass, eventFold] using secondUnionBound
      _ = eventMass (mapDistribution firstMap law) event +
          eventMass law (fun source => decide (firstMap source ≠ secondMap source)) := by
            rw [eventMass_mapDistribution]

/-- For any two events on one finite weighted sample, the sum of their
    probability masses is at most total mass plus their intersection mass.
    This is the lower Frechet inequality in a form that avoids subtraction. -/
theorem eventFold_sum_le_mass_add_intersection {α : Type}
    (outcomes : List (α × Rat)) (first second : α → Bool)
    (weightsNonnegative : ∀ value weight, (value, weight) ∈ outcomes →
      0 ≤ weight) :
    eventFold outcomes first + eventFold outcomes second ≤
      mass outcomes + eventFold outcomes (fun value => first value && second value) := by
  induction outcomes with
  | nil => simp [eventFold, mass]
  | cons head rest ih =>
      rcases head with ⟨value, weight⟩
      have headNonnegative : 0 ≤ weight := weightsNonnegative value weight (by simp)
      have restNonnegative : ∀ candidate candidateWeight,
          (candidate, candidateWeight) ∈ rest → 0 ≤ candidateWeight := by
        intro candidate candidateWeight member
        exact weightsNonnegative candidate candidateWeight (by simp [member])
      have tailBound := ih restNonnegative
      change (if first value then weight + eventFold rest first else
          eventFold rest first) +
        (if second value then weight + eventFold rest second else
          eventFold rest second) ≤
        (weight + mass rest) +
          (if first value && second value then
            weight + eventFold rest (fun item => first item && second item) else
            eventFold rest (fun item => first item && second item))
      cases firstValue : first value <;> cases secondValue : second value <;>
        simp only [firstValue, secondValue, Bool.false_eq_true, ↓reduceIte]
      · calc
          eventFold rest first + eventFold rest second ≤
              mass rest + eventFold rest (fun value => first value && second value) :=
                tailBound
          _ ≤ weight + (mass rest +
              eventFold rest (fun value => first value && second value)) := by
                simpa [Rat.zero_add] using
                  (Rat.add_le_add_right.mpr headNonnegative :
                    0 + (mass rest + eventFold rest
                      (fun value => first value && second value)) ≤
                    weight + (mass rest + eventFold rest
                      (fun value => first value && second value)))
          _ = weight + mass rest +
              eventFold rest (fun value => first value && second value) := by
                exact (Rat.add_assoc _ _ _).symm
      · calc
          eventFold rest first + (weight + eventFold rest second) =
              weight + (eventFold rest first + eventFold rest second) := by ac_rfl
          _ ≤ weight + (mass rest +
              eventFold rest (fun value => first value && second value)) :=
                Rat.add_le_add_left.mpr tailBound
          _ = weight + mass rest +
              eventFold rest (fun value => first value && second value) := by
                exact (Rat.add_assoc _ _ _).symm
      · calc
          (weight + eventFold rest first) + eventFold rest second =
              weight + (eventFold rest first + eventFold rest second) := by ac_rfl
          _ ≤ weight + (mass rest +
              eventFold rest (fun value => first value && second value)) :=
                Rat.add_le_add_left.mpr tailBound
          _ = weight + mass rest +
              eventFold rest (fun value => first value && second value) := by
                exact (Rat.add_assoc _ _ _).symm
      · calc
          (weight + eventFold rest first) + (weight + eventFold rest second) =
              (weight + weight) +
                (eventFold rest first + eventFold rest second) := by ac_rfl
          _ ≤ (weight + weight) + (mass rest +
              eventFold rest (fun value => first value && second value)) :=
                Rat.add_le_add_left.mpr tailBound
          _ = (weight + mass rest) +
              (weight + eventFold rest (fun value => first value && second value)) := by ac_rfl

/-- Marginal probabilities alone bound the joint event without an independence
    assumption: P(A)+P(B) ≤ 1+P(A∩B), while P(A∩B) is no larger than either
    marginal. These are the finite rational Frechet inequalities in an
    addition-only form. -/
theorem finite_event_intersection_frechet_bounds {α : Type}
    (law : FiniteDistribution α) (first second : α → Bool) :
    eventMass law first + eventMass law second ≤
        1 + eventMass law (fun value => first value && second value) ∧
      eventMass law (fun value => first value && second value) ≤
        eventMass law first ∧
      eventMass law (fun value => first value && second value) ≤
        eventMass law second := by
  have lower := eventFold_sum_le_mass_add_intersection law.outcomes first second
    law.nonnegative
  have upperFirst := eventFold_mono_of_support_inclusion law.outcomes
    (fun value => first value && second value) first law.nonnegative
    (by
      intro value weight _ _ both
      have components : first value = true ∧ second value = true := by
        simpa using both
      exact components.1)
  have upperSecond := eventFold_mono_of_support_inclusion law.outcomes
    (fun value => first value && second value) second law.nonnegative
    (by
      intro value weight _ _ both
      have components : first value = true ∧ second value = true := by
        simpa using both
      exact components.2)
  constructor
  · simpa [eventMass, eventFold, law.normalized] using lower
  constructor
  · simpa [eventMass, eventFold] using upperFirst
  · simpa [eventMass, eventFold] using upperSecond

/-- A response law respects a feasibility boundary when every positive-mass
    proposal is feasible. Zero-weight entries have no behavioral meaning. -/
def RespectsFeasibility {Proposal : Type} (feasible : Proposal → Bool)
    (law : FiniteDistribution Proposal) : Prop :=
  ∀ proposal, Supports law proposal → feasible proposal = true

/-- The response probabilities compatible with a feasibility boundary and an
    event of interest. -/
def CompatibleResponseProbability {Proposal : Type} (feasible : Proposal → Bool)
    (event : Proposal → Bool) (probability : Rat) : Prop :=
  ∃ law : FiniteDistribution Proposal,
    RespectsFeasibility feasible law ∧ eventMass law event = probability

/-- Feasibility alone cannot identify an event probability when both the event
    and its complement contain a feasible proposal: every rational probability
    in [0,1] is generated by some admissible response law. This is sharp at the
    level of the unrestricted finite response model. -/
theorem every_probability_compatible_with_two_feasible_outcomes
    {Proposal : Type} (feasible event : Proposal → Bool)
    (eventProposal nonEventProposal : Proposal)
    (eventHolds : event eventProposal = true)
    (eventFails : event nonEventProposal = false)
    (eventFeasible : feasible eventProposal = true)
    (nonEventFeasible : feasible nonEventProposal = true)
    (probability : Rat) (probabilityNonnegative : 0 ≤ probability)
    (probabilityAtMostOne : probability ≤ 1) :
    CompatibleResponseProbability feasible event probability := by
  let law : FiniteDistribution Proposal := {
    outcomes := [(eventProposal, probability), (nonEventProposal, 1 - probability)]
    nonnegative := by
      intro value weight member
      simp only [List.mem_cons, Prod.mk.injEq] at member
      rcases member with ⟨valueEq, weightEq⟩ | ⟨valueEq, weightEq⟩ | impossible
      · subst value
        subst weight
        exact probabilityNonnegative
      · subst value
        subst weight
        exact (Rat.le_iff_sub_nonneg probability 1).mp probabilityAtMostOne
      · simp at impossible
    normalized := by
      change probability + (1 - probability + 0) = 1
      rw [Rat.add_zero]
      calc
        probability + (1 - probability) = (1 - probability) + probability :=
          Rat.add_comm _ _
        _ = 1 := Rat.sub_add_cancel
  }
  have respects : RespectsFeasibility feasible law := by
    intro proposal supported
    rcases supported with ⟨weight, member, positive⟩
    simp only [law, List.mem_cons, Prod.mk.injEq] at member
    rcases member with ⟨proposalEq, _⟩ | ⟨proposalEq, _⟩ | impossible
    · subst proposal
      exact eventFeasible
    · subst proposal
      exact nonEventFeasible
    · simp at impossible
  have eventProbability : eventMass law event = probability := by
    simp [law, eventMass, eventHolds, eventFails]
    exact Rat.add_zero _
  exact ⟨law, respects, eventProbability⟩

/-- When resources and production leave both success and failure physically
    feasible, no point prediction of success probability follows without a
    restriction on the response law. -/
theorem resource_production_feasibility_does_not_point_identify_behavior
    {Proposal : Type} (feasible success : Proposal → Bool)
    (successProposal failureProposal : Proposal)
    (successPossible : success successProposal = true)
    (failurePossible : success failureProposal = false)
    (successFeasible : feasible successProposal = true)
    (failureFeasible : feasible failureProposal = true) :
    ∀ probability : Rat, 0 ≤ probability → probability ≤ 1 →
    CompatibleResponseProbability feasible success probability := by
  intro probability probabilityNonnegative probabilityAtMostOne
  exact every_probability_compatible_with_two_feasible_outcomes feasible success
    successProposal failureProposal successPossible failurePossible successFeasible
    failureFeasible probability probabilityNonnegative probabilityAtMostOne

/-- Exact identified set: under the two-feasible-outcomes condition, the
    probabilities compatible with feasibility are precisely all rational
    values between zero and one. The upper/lower inclusion follows only from
    probability normalization; attainability follows from the constructed
    response laws above. -/
theorem sharp_feasibility_only_identified_set
    {Proposal : Type} (feasible event : Proposal → Bool)
    (eventProposal nonEventProposal : Proposal)
    (eventHolds : event eventProposal = true)
    (eventFails : event nonEventProposal = false)
    (eventFeasible : feasible eventProposal = true)
    (nonEventFeasible : feasible nonEventProposal = true)
    (probability : Rat) :
    CompatibleResponseProbability feasible event probability ↔
      0 ≤ probability ∧ probability ≤ 1 := by
  constructor
  · rintro ⟨law, _, equality⟩
    constructor
    · rw [← equality]
      exact eventMass_nonnegative law event
    · rw [← equality]
      exact eventMass_le_one law event
  · rintro ⟨probabilityNonnegative, probabilityAtMostOne⟩
    exact every_probability_compatible_with_two_feasible_outcomes feasible event
      eventProposal nonEventProposal eventHolds eventFails eventFeasible nonEventFeasible
      probability probabilityNonnegative probabilityAtMostOne

end AgentMicrofoundations.ResponseIdentification
