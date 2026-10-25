import AgentMicrofoundations.CouplingComparativeStatics

/-!
Finite-sample case instantiation generated from the archived resource-signal
pilot JSONL. The empirical pairing is the matched-vignette block pairing; it
is not a common-random-number coupling of the model's population response law.
All counts below refer only to these 20 observed blocks.
They do not estimate a population response law or validate a persistent
behavioral mechanism.

Source SHA-256: e7a0b8975f767baf10ba2cfee9acc078d55353b1b91a7cbffe7ea449ebd0e91d
-/
namespace AgentMicrofoundations.CaseStudies.ResourceSignalPilot

/-- Each pair records (work at displayed energy 2, work at displayed energy 5)
    for one matched vignette block. -/
def observedWorkPairs : List (Bool × Bool) := [
  (true, true),
  (true, true),
  (true, true),
  (true, true),
  (true, true),
  (false, true),
  (false, true),
  (true, true),
  (false, true),
  (true, true),
  (true, true),
  (true, true),
  (true, true),
  (true, true),
  (true, true),
  (true, true),
  (false, true),
  (false, true),
  (true, true),
  (true, true)
]

def countBy (predicate : Bool × Bool → Bool) : Nat :=
  (observedWorkPairs.filter predicate).length

def lowSignalWorkCount : Nat := countBy fun pair => pair.1
def highSignalWorkCount : Nat := countBy fun pair => pair.2
def discordantBlockCount : Nat := countBy fun pair => pair.1 != pair.2
def highOnlyDiscordanceCount : Nat := countBy fun pair => !pair.1 && pair.2
def lowOnlyDiscordanceCount : Nat := countBy fun pair => pair.1 && !pair.2

/-- On any paired binary sample, a marginal count difference cannot exceed
    the number of discordant pairs. This is the count-scale counterpart of the
    finite coupling event bound; it does not require a population law. -/
theorem paired_count_difference_bounded_by_disagreement
    (pairs : List (Bool × Bool)) :
    ((pairs.filter fun pair => pair.1).length ≤
        (pairs.filter fun pair => pair.2).length +
          (pairs.filter fun pair => pair.1 != pair.2).length) ∧
      ((pairs.filter fun pair => pair.2).length ≤
        (pairs.filter fun pair => pair.1).length +
          (pairs.filter fun pair => pair.1 != pair.2).length) := by
  induction pairs with
  | nil => simp
  | cons pair rest inductionHypothesis =>
      rcases pair with ⟨low, high⟩
      cases low <;> cases high <;> simp at * <;> omega

/-- Recomputed directly from the preserved 20-block JSONL: work was proposed
    in 15/20 low-signal rows and 20/20 high-signal rows; the five discordant
    blocks all favored the high signal. -/
theorem raw_pilot_counts :
    lowSignalWorkCount = 15 ∧ highSignalWorkCount = 20 ∧
      discordantBlockCount = 5 ∧ highOnlyDiscordanceCount = 5 ∧
      lowOnlyDiscordanceCount = 0 := by
  decide

/-- The observed count gap exactly exhausts the paired-disagreement bound.
    This certifies a finite-sample arithmetic fact only; it gives no confidence
    interval and no population-level treatment effect. -/
theorem pilot_count_bound_is_sharp_on_observed_sample :
    lowSignalWorkCount ≤ highSignalWorkCount + discordantBlockCount ∧
      highSignalWorkCount ≤ lowSignalWorkCount + discordantBlockCount ∧
      highSignalWorkCount = lowSignalWorkCount + discordantBlockCount := by
  have general := paired_count_difference_bounded_by_disagreement observedWorkPairs
  have values := raw_pilot_counts
  constructor
  · simpa [lowSignalWorkCount, highSignalWorkCount, discordantBlockCount,
      countBy, values.1, values.2.1, values.2.2.1] using general.1
  constructor
  · simpa [lowSignalWorkCount, highSignalWorkCount, discordantBlockCount,
      countBy, values.1, values.2.1, values.2.2.1] using general.2
  · rcases values with ⟨lowCount, highCount, discordanceCount, _, _⟩
    rw [lowCount, highCount, discordanceCount]

end AgentMicrofoundations.CaseStudies.ResourceSignalPilot
