import AgentMicrofoundations.AutoregressiveIdentification

/-!
Sharp transport boundary for a fixed computational agent.

Complete-input invariance gives equality when the encoded prompt and budget
are held fixed. It does not imply invariance across population regimes whose
prompts encode different population sizes. This module proves sharpness: one
fixed autoregressive constitution, stop rule, and parser can realize any pair
of proposal-event probabilities at two distinct population sizes. Thus a
six-agent case cannot identify a three-, four-, or five-agent forecast from
the architectural form alone. The result is an impossibility theorem, not a
claim that a deployed model actually uses this response kernel.
-/
namespace AgentMicrofoundations.PopulationTransport

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AutoregressiveResponse
open AgentMicrofoundations.AutoregressiveIdentification

/-- A fixed agent constitution that can condition its first token on the
    population size encoded in the prompt. It uses one shared token kernel,
    parser, and stopping rule across all population regimes. -/
def populationConditionedConstitution
    (referencePopulation : Nat)
    (referenceProbability otherProbability : Rat)
    (referenceNonnegative : 0 ≤ referenceProbability)
    (referenceAtMostOne : referenceProbability ≤ 1)
    (otherNonnegative : 0 ≤ otherProbability)
    (otherAtMostOne : otherProbability ≤ 1) :
    AutoregressiveConstitution Nat Bool Bool := {
  prompt := fun population => [decide (population = referencePopulation)]
  nextToken := fun promptTokens =>
    match promptTokens with
    | [true] => bernoulliTokenLaw referenceProbability referenceNonnegative referenceAtMostOne
    | [false] => bernoulliTokenLaw otherProbability otherNonnegative otherAtMostOne
    | _ => bernoulliTokenLaw 0 (by decide) (by decide)
  stopToken := fun _ => true
  parseProposal := fun {_budget} trace => trace.tokens.headD false
}

theorem proposal_probability_at_reference_population
    (referencePopulation : Nat)
    (referenceProbability otherProbability : Rat)
    (referenceNonnegative : 0 ≤ referenceProbability)
    (referenceAtMostOne : referenceProbability ≤ 1)
    (otherNonnegative : 0 ≤ otherProbability)
    (otherAtMostOne : otherProbability ≤ 1) :
    eventMass
      (proposalLaw
        (populationConditionedConstitution referencePopulation
          referenceProbability otherProbability referenceNonnegative referenceAtMostOne
          otherNonnegative otherAtMostOne)
        referencePopulation 1) id = referenceProbability := by
  simp [proposalLaw, populationConditionedConstitution, bernoulliTokenLaw,
    generatedTokenTrace, extendGeneratedTrace, bindDistribution, bindEntries,
    mapDistribution, mapEntries, scaleEntries, pureDistribution, eventMass]
  exact Rat.add_zero _

theorem proposal_probability_at_other_population
    (referencePopulation otherPopulation : Nat)
    (referenceProbability otherProbability : Rat)
    (referenceNonnegative : 0 ≤ referenceProbability)
    (referenceAtMostOne : referenceProbability ≤ 1)
    (otherNonnegative : 0 ≤ otherProbability)
    (otherAtMostOne : otherProbability ≤ 1)
    (distinctPopulations : referencePopulation ≠ otherPopulation) :
    eventMass
      (proposalLaw
        (populationConditionedConstitution referencePopulation
          referenceProbability otherProbability referenceNonnegative referenceAtMostOne
          otherNonnegative otherAtMostOne)
        otherPopulation 1) id = otherProbability := by
  have promptIsOther :
      [decide (otherPopulation = referencePopulation)] = [false] := by
    have unequal : otherPopulation ≠ referencePopulation := Ne.symm distinctPopulations
    simp [unequal]
  simp [proposalLaw, populationConditionedConstitution, promptIsOther,
    bernoulliTokenLaw, generatedTokenTrace, extendGeneratedTrace,
    bindDistribution, bindEntries, mapDistribution, mapEntries, scaleEntries,
    pureDistribution, eventMass]
  exact Rat.add_zero _

/-- Sharp non-transport result: holding the agent's complete computational
    constitution fixed does not restrict the relationship between response
    probabilities at two distinct population sizes when population size changes
    the encoded prompt. Any pair in `[0,1]²` is attainable. A cross-size point
    forecast therefore requires a tested restriction on how the response law
    varies with the population-conditioned input. -/
theorem arbitrary_response_pair_across_population_sizes
    (referencePopulation otherPopulation : Nat)
    (referenceProbability otherProbability : Rat)
    (referenceNonnegative : 0 ≤ referenceProbability)
    (referenceAtMostOne : referenceProbability ≤ 1)
    (otherNonnegative : 0 ≤ otherProbability)
    (otherAtMostOne : otherProbability ≤ 1)
    (distinctPopulations : referencePopulation ≠ otherPopulation) :
    ∃ constitution : AutoregressiveConstitution Nat Bool Bool,
      eventMass (proposalLaw constitution referencePopulation 1) id = referenceProbability ∧
      eventMass (proposalLaw constitution otherPopulation 1) id = otherProbability := by
  refine ⟨populationConditionedConstitution referencePopulation
    referenceProbability otherProbability referenceNonnegative referenceAtMostOne
    otherNonnegative otherAtMostOne, ?_⟩
  exact ⟨proposal_probability_at_reference_population referencePopulation
    referenceProbability otherProbability referenceNonnegative referenceAtMostOne
    otherNonnegative otherAtMostOne,
    proposal_probability_at_other_population referencePopulation otherPopulation
    referenceProbability otherProbability referenceNonnegative referenceAtMostOne
    otherNonnegative otherAtMostOne distinctPopulations⟩

/-- In particular, a fixed constitution can reverse the ordering of an action
    probability across two population regimes. This rejects any directional
    population-size comparative static derived from autoregressive structure
    alone. -/
theorem fixed_constitution_can_reverse_population_response
    (referencePopulation otherPopulation : Nat)
    (distinctPopulations : referencePopulation ≠ otherPopulation) :
    ∃ constitution : AutoregressiveConstitution Nat Bool Bool,
      eventMass (proposalLaw constitution referencePopulation 1) id = 1 ∧
      eventMass (proposalLaw constitution otherPopulation 1) id = 0 := by
  exact arbitrary_response_pair_across_population_sizes referencePopulation otherPopulation
    1 0 (by decide) (by decide) (by decide) (by decide) distinctPopulations

end AgentMicrofoundations.PopulationTransport
