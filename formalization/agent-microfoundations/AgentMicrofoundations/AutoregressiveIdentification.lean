import AgentMicrofoundations.AutoregressiveResponse

/-!
Identification boundary for deriving proposal behavior from autoregressive
form alone. A fixed kernel and parser determine a proposal law, but the
architecture class by itself permits every rational event probability.
Therefore directional economic choice claims require token-kernel content,
context encoding, or an empirically identified restriction; autoregression
alone supplies no preference or rationality law.
-/
namespace AgentMicrofoundations.AutoregressiveIdentification

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AutoregressiveResponse

def bernoulliTokenLaw (probability : Rat)
    (nonnegative : 0 ≤ probability) (atMostOne : probability ≤ 1) :
    FiniteDistribution Bool := {
  outcomes := [(true, probability), (false, 1 - probability)]
  nonnegative := by
    intro value weight member
    simp only [List.mem_cons, Prod.mk.injEq] at member
    rcases member with ⟨valueEq, weightEq⟩ | ⟨valueEq, weightEq⟩ | impossible
    · subst value
      subst weight
      exact nonnegative
    · subst value
      subst weight
      exact (Rat.le_iff_sub_nonneg probability 1).mp atMostOne
    · simp at impossible
  normalized := by
    change probability + (1 - probability + 0) = 1
    rw [Rat.add_zero]
    calc
      probability + (1 - probability) = (1 - probability) + probability :=
        Rat.add_comm _ _
      _ = 1 := Rat.sub_add_cancel
}

/-- A minimal autoregressive constitution: the first token directly encodes
    the proposal. It uses a fixed prompt, a fixed stop rule, and a fixed parser;
    only the next-token probabilities vary with `probability`. -/
def bernoulliProposalConstitution (probability : Rat)
    (nonnegative : 0 ≤ probability) (atMostOne : probability ≤ 1) :
    AutoregressiveConstitution Unit Bool Bool := {
  prompt := fun _ => []
  nextToken := fun _ => bernoulliTokenLaw probability nonnegative atMostOne
  stopToken := fun _ => true
  parseProposal := fun {_budget} trace => trace.tokens.headD false
}

/-- Autoregressive architecture, with a fixed protocol and stop rule, can
    realize every rational proposal probability in `[0,1]`. Thus no universal
    directional choice probability follows from the autoregressive form alone.
    This is a sharp non-identification theorem over the constitution class,
    not a claim that a particular deployed model has arbitrary weights. -/
theorem every_probability_realizable_by_autoregressive_constitution
    (probability : Rat) (nonnegative : 0 ≤ probability)
    (atMostOne : probability ≤ 1) :
    ∃ constitution : AutoregressiveConstitution Unit Bool Bool,
      eventMass (proposalLaw constitution () 1) id = probability := by
  refine ⟨bernoulliProposalConstitution probability nonnegative atMostOne, ?_⟩
  simp [proposalLaw, bernoulliProposalConstitution, bernoulliTokenLaw,
    generatedTokenTrace, extendGeneratedTrace, bindDistribution, bindEntries,
    mapDistribution, mapEntries, scaleEntries, pureDistribution, eventMass,
    Rat.add_zero]

/-- The same computational architecture can also realize both degenerate
    outcomes, showing that the endpoints of the identified set are attainable. -/
theorem autoregressive_event_probability_endpoints_realizable :
    (∃ constitution : AutoregressiveConstitution Unit Bool Bool,
      eventMass (proposalLaw constitution () 1) id = 0) ∧
    (∃ constitution : AutoregressiveConstitution Unit Bool Bool,
      eventMass (proposalLaw constitution () 1) id = 1) := by
  constructor
  · exact every_probability_realizable_by_autoregressive_constitution 0
      (Rat.le_refl) (by decide)
  · exact every_probability_realizable_by_autoregressive_constitution 1
      (by decide) (Rat.le_refl)

end AgentMicrofoundations.AutoregressiveIdentification
