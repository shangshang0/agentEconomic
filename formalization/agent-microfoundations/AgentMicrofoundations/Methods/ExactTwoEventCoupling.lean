import AgentMicrofoundations.TemporalIntersectionBounds

/-!
Auxiliary probability lemma: exact two-period identification under unrestricted dependence.

Given only two event marginals p and q, every feasible intersection mass r is
characterized by the finite Frechet inequalities. Conversely, each such r is
implemented by an explicit four-atom rational law. This is a standard
probability calculation useful for case identification; it is not a primitive,
behavioral law, or novel agent-economics contribution.
-/
namespace AgentMicrofoundations.Methods.ExactTwoEventCoupling

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.ResponseIdentification

/-- Feasibility inequalities for a proposed joint mass of two events. -/
def FeasibleJointMass (p q joint : Rat) : Prop :=
  0 ≤ joint ∧ joint ≤ p ∧ joint ≤ q ∧ p + q ≤ 1 + joint

/-- If a is no larger than b, their difference b-a is nonnegative. -/
theorem sub_nonnegative_of_le (a b : Rat) (h : a ≤ b) : 0 ≤ b - a := by
  have shifted := (Rat.add_le_add_right (a := a) (b := b) (c := -a)).mpr h
  simpa [Rat.sub_eq_add_neg, Rat.add_neg_cancel] using shifted

/-- The four cell probabilities of a 2×2 table. -/
def couplingOutcomes (p q joint : Rat) : List ((Bool × Bool) × Rat) :=
  [((true, true), joint),
   ((true, false), p - joint),
   ((false, true), q - joint),
   ((false, false), 1 - (joint + (p - joint) + (q - joint)))]

theorem coupling_mass_normalized (p q joint : Rat) :
    mass (couplingOutcomes p q joint) = 1 := by
  simp only [couplingOutcomes, mass]
  let total := joint + (p - joint) + (q - joint)
  have complement : total + (1 - total) = 1 := by
    calc
      total + (1 - total) = (1 - total) + total := by ac_rfl
      _ = 1 := Rat.sub_add_cancel
  change joint + (p - joint + (q - joint + (1 - total + 0))) = 1
  calc
    joint + (p - joint + (q - joint + (1 - total + 0))) = total + (1 - total) := by
      dsimp [total]
      ac_rfl
    _ = 1 := complement

/-- Construct a finite joint law that attains any feasible intersection
    probability. The four cells are TT, TF, FT, and FF; no product structure is
    imposed. -/
def couplingLaw (p q joint : Rat) (feasible : FeasibleJointMass p q joint) :
    FiniteDistribution (Bool × Bool) := by
  rcases feasible with ⟨jointNonnegative, jointLeP, jointLeQ, totalBound⟩
  let total := joint + (p - joint) + (q - joint)
  have firstPair : joint + (p - joint) = p := by
    calc
      joint + (p - joint) = (p - joint) + joint := by ac_rfl
      _ = p := Rat.sub_add_cancel
  have shifted := (Rat.add_le_add_right (a := p + q) (b := 1 + joint) (c := -joint)).mpr totalBound
  have totalLeOne : total ≤ 1 := by
    dsimp [total]
    calc
      joint + (p - joint) + (q - joint) = p + (q - joint) := by rw [firstPair]
      _ ≤ 1 := by simpa [Rat.sub_eq_add_neg, Rat.add_assoc, Rat.add_neg_cancel, Rat.add_zero] using shifted
  refine ⟨couplingOutcomes p q joint, ?_, coupling_mass_normalized p q joint⟩
  intro outcome weight member
  simp [couplingOutcomes] at member
  rcases member with h | h | h | h
  · rcases h with ⟨_, rfl⟩
    exact jointNonnegative
  · rcases h with ⟨_, rfl⟩
    exact sub_nonnegative_of_le joint p jointLeP
  · rcases h with ⟨_, rfl⟩
    exact sub_nonnegative_of_le joint q jointLeQ
  · rcases h with ⟨_, rfl⟩
    exact sub_nonnegative_of_le total 1 totalLeOne

theorem couplingLaw_first_marginal
    (p q joint : Rat) (feasible : FeasibleJointMass p q joint) :
    eventMass (couplingLaw p q joint feasible) (fun pair => pair.1) = p := by
  simp [couplingLaw, couplingOutcomes, eventMass, Rat.sub_eq_add_neg,
    Rat.add_assoc]
  simp only [Rat.add_zero]
  calc
    joint + (p + -joint) = (joint + -joint) + p := by ac_rfl
    _ = p := by rw [Rat.add_neg_cancel, Rat.zero_add]

theorem couplingLaw_second_marginal
    (p q joint : Rat) (feasible : FeasibleJointMass p q joint) :
    eventMass (couplingLaw p q joint feasible) (fun pair => pair.2) = q := by
  simp [couplingLaw, couplingOutcomes, eventMass, Rat.sub_eq_add_neg,
    Rat.add_assoc]
  simp only [Rat.add_zero]
  calc
    joint + (q + -joint) = (joint + -joint) + q := by ac_rfl
    _ = q := by rw [Rat.add_neg_cancel, Rat.zero_add]

theorem couplingLaw_intersection
    (p q joint : Rat) (feasible : FeasibleJointMass p q joint) :
    eventMass (couplingLaw p q joint feasible)
      (fun pair => pair.1 && pair.2) = joint := by
  simp [couplingLaw, couplingOutcomes, eventMass, Rat.add_zero]

/-- Exact characterization: a rational intersection mass is attainable by a
    joint law with prescribed marginals p and q iff it satisfies the Frechet
    inequalities. The forward direction is the universal probability bound;
    the reverse direction is constructive via `couplingLaw`. -/
theorem joint_mass_feasible_iff
    (p q joint : Rat) :
    FeasibleJointMass p q joint ↔
      ∃ law : FiniteDistribution (Bool × Bool),
        eventMass law (fun pair => pair.1) = p ∧
        eventMass law (fun pair => pair.2) = q ∧
        eventMass law (fun pair => pair.1 && pair.2) = joint := by
  constructor
  · intro feasible
    refine ⟨couplingLaw p q joint feasible,
      couplingLaw_first_marginal p q joint feasible,
      couplingLaw_second_marginal p q joint feasible,
      couplingLaw_intersection p q joint feasible⟩
  · rintro ⟨law, firstEq, secondEq, intersectionEq⟩
    have bounds := finite_event_intersection_frechet_bounds law
      (fun pair => pair.1) (fun pair => pair.2)
    constructor
    · rw [← intersectionEq]
      exact eventMass_nonnegative law _
    constructor
    · rw [← firstEq, ← intersectionEq]
      exact bounds.2.1
    constructor
    · rw [← secondEq, ← intersectionEq]
      exact bounds.2.2
    · rw [← firstEq, ← secondEq, ← intersectionEq]
      simpa using bounds.1

/-- The lower Frechet boundary when the marginals sum to at most one is
    attained by a law with zero joint success mass. -/
theorem lower_boundary_zero_is_feasible
    (p q : Rat) (pNonnegative : 0 ≤ p) (qNonnegative : 0 ≤ q)
    (sumBound : p + q ≤ 1) :
    FeasibleJointMass p q 0 := by
  refine ⟨Rat.le_refl, ?_, ?_, ?_⟩
  · exact pNonnegative
  · exact qNonnegative
  · simpa [Rat.add_zero] using sumBound

/-- The lower Frechet boundary when the marginals sum above one is attained. -/
theorem lower_boundary_excess_is_feasible
    (p q : Rat) (pAtMostOne : p ≤ 1) (qAtMostOne : q ≤ 1)
    (sumAboveOne : 1 ≤ p + q) :
    FeasibleJointMass p q (p + q - 1) := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · exact sub_nonnegative_of_le 1 (p + q) sumAboveOne
  · have qShift := (Rat.add_le_add_left (a := q) (b := 1) (c := p)).mpr qAtMostOne
    have shifted := (Rat.add_le_add_right (a := p + q) (b := p + 1) (c := -1)).mpr qShift
    simpa [Rat.sub_eq_add_neg, Rat.add_assoc, Rat.add_zero, Rat.add_neg_cancel] using shifted
  · have pShift := (Rat.add_le_add_left (a := p) (b := 1) (c := q)).mpr pAtMostOne
    have shifted := (Rat.add_le_add_right (a := q + p) (b := q + 1) (c := -1)).mpr pShift
    simpa [Rat.sub_eq_add_neg, Rat.add_assoc, Rat.add_comm, Rat.add_zero, Rat.add_neg_cancel] using shifted
  · have identity : (p + q) - 1 + 1 = p + q := Rat.sub_add_cancel
    calc
      p + q = 1 + ((p + q) - 1) := by
        calc
          p + q = ((p + q) - 1) + 1 := identity.symm
          _ = 1 + ((p + q) - 1) := by ac_rfl
      _ ≤ 1 + ((p + q) - 1) := Rat.le_refl

/-- The upper Frechet boundary is attained when p is the smaller marginal. -/
theorem upper_boundary_p_is_feasible
    (p q : Rat) (pNonnegative : 0 ≤ p) (qAtMostOne : q ≤ 1)
    (pBelowQ : p ≤ q) :
    FeasibleJointMass p q p := by
  refine ⟨pNonnegative, Rat.le_refl, pBelowQ, ?_⟩
  have shifted := (Rat.add_le_add_left (a := q) (b := 1) (c := p)).mpr qAtMostOne
  simpa [Rat.add_comm] using shifted

/-- The upper Frechet boundary is attained when q is the smaller marginal. -/
theorem upper_boundary_q_is_feasible
    (p q : Rat) (pAtMostOne : p ≤ 1) (qNonnegative : 0 ≤ q)
    (qBelowP : q ≤ p) :
    FeasibleJointMass p q q := by
  refine ⟨qNonnegative, qBelowP, Rat.le_refl, ?_⟩
  have shifted := (Rat.add_le_add_left (a := p) (b := 1) (c := q)).mpr pAtMostOne
  simpa [Rat.add_comm] using shifted

end AgentMicrofoundations.Methods.ExactTwoEventCoupling
