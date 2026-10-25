#!/usr/bin/env python3
"""Generate the Lean finite-sample resource-signal case from its raw JSONL."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent.parent / "WWW2027_submission" / "appendix" / "pilot" / "pilot_v2.jsonl"
TARGET = ROOT / "AgentMicrofoundations" / "CaseStudies" / "ResourceSignalPilot.lean"


def main() -> None:
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines() if line.strip()]
    if len(rows) != 40:
        raise SystemExit(f"Expected 40 valid pilot records, found {len(rows)}")

    by_block: dict[int, dict[int, bool]] = {}
    for row in rows:
        if not row.get("ok") or not row.get("valid_action"):
            raise SystemExit("Pilot JSONL contains a failed or invalid action row")
        if row.get("experiment") != "signal_x_execution_gate_v1":
            raise SystemExit("Unexpected experiment identifier in pilot JSONL")
        energy = row.get("displayed_energy")
        if energy not in (2, 5):
            raise SystemExit(f"Unexpected displayed energy: {energy}")
        block = row.get("block")
        if not isinstance(block, int) or block < 1 or block > 20:
            raise SystemExit(f"Unexpected block identifier: {block}")
        if energy in by_block.setdefault(block, {}):
            raise SystemExit(f"Duplicate energy condition in block {block}")
        action = row.get("action")
        if action not in ("work", "rest"):
            raise SystemExit(f"Unexpected action: {action}")
        by_block[block][energy] = action == "work"

    if sorted(by_block) != list(range(1, 21)):
        raise SystemExit("Pilot blocks are not exactly 1 through 20")
    if any(set(conditions) != {2, 5} for conditions in by_block.values()):
        raise SystemExit("Every pilot block must contain both displayed energies")

    pairs = [(by_block[b][2], by_block[b][5]) for b in range(1, 21)]
    lean_pairs = ",\n  ".join(
        f"({str(low).lower()}, {str(high).lower()})" for low, high in pairs
    )
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    TARGET.write_text(f'''import AgentMicrofoundations.CouplingComparativeStatics

/-!
Finite-sample case instantiation generated from the archived resource-signal
pilot JSONL. The empirical pairing is the matched-vignette block pairing; it
is not a common-random-number coupling of the model's population response law.
All counts below refer only to these 20 observed blocks.
They do not estimate a population response law or validate a persistent
behavioral mechanism.

Source SHA-256: {source_hash}
-/
namespace AgentMicrofoundations.CaseStudies.ResourceSignalPilot

/-- Each pair records (work at displayed energy 2, work at displayed energy 5)
    for one matched vignette block. -/
def observedWorkPairs : List (Bool × Bool) := [
  {lean_pairs}
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
''')
    print(f"Generated {TARGET.relative_to(ROOT)} from {SOURCE}")


if __name__ == "__main__":
    main()
