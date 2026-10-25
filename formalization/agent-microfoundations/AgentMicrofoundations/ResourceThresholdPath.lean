import AgentMicrofoundations.ResourceLedger

/-!
Threshold-mediated resource dynamics.

The additive ledger is order-invariant, but a viability gate applied after
each event makes event order economically relevant: a subject that crosses the
death threshold cannot use a later reward. This separates an aggregate
accounting identity from a path-dependent continuation rule. It motivates
event-level resource replay in CTF-style scenarios and gives a precise
boundary for when end-of-period net flows suffice.
-/
namespace AgentMicrofoundations.ResourceThresholdPath

structure ViabilityState where
  balance : Int
  alive : Bool
  deriving DecidableEq, Repr

/-- Apply one signed resource event. Death is absorbing; a live subject
    continues iff the post-event balance reaches the viability threshold. -/
def applyEvent (threshold : Int) (state : ViabilityState) (delta : Int) :
    ViabilityState :=
  if state.alive then
    let after := state.balance + delta
    if threshold ≤ after then { balance := after, alive := true }
    else { balance := 0, alive := false }
  else state

def runEvents (threshold : Int) (initial : ViabilityState) (events : List Int) :
    ViabilityState :=
  events.foldl (applyEvent threshold) initial

theorem dead_state_is_absorbing (threshold : Int) (balance : Int) (delta : Int) :
    applyEvent threshold { balance := balance, alive := false } delta =
      { balance := balance, alive := false } := by
  simp [applyEvent]

theorem dead_run_is_absorbing (threshold : Int) (balance : Int) (events : List Int) :
    runEvents threshold { balance := balance, alive := false } events =
      { balance := balance, alive := false } := by
  induction events with
  | nil => rfl
  | cons delta rest ih =>
      simp only [runEvents, List.foldl_cons]
      rw [dead_state_is_absorbing]
      exact ih

/-- On any realized path that remains viable, sequential resource updates
    equal the additive ledger. The conclusion fails to determine paths that
    cross the threshold; the counterexample below shows why. -/
theorem viable_path_matches_additive_ledger
    (threshold : Int) (initial : ViabilityState) (events : List Int)
    (initiallyAlive : initial.alive = true)
    (remainsAlive : (runEvents threshold initial events).alive = true) :
    (runEvents threshold initial events).balance = initial.balance + events.sum := by
  induction events generalizing initial with
  | nil => simp [runEvents]
  | cons delta rest ih =>
      simp only [runEvents, List.foldl_cons] at remainsAlive ⊢
      simp only [applyEvent, initiallyAlive, ite_true] at remainsAlive ⊢
      by_cases hThreshold : threshold ≤ initial.balance + delta
      · simp only [hThreshold, ite_true] at remainsAlive ⊢
        have hTail := ih
          { balance := initial.balance + delta, alive := true }
          rfl remainsAlive
        simp only [Int.add_assoc, List.sum_cons] at hTail ⊢
        exact hTail
      · simp only [hThreshold, ite_false] at remainsAlive
        change (runEvents threshold { balance := 0, alive := false } rest).alive = true
          at remainsAlive
        rw [dead_run_is_absorbing] at remainsAlive
        simp at remainsAlive

/-- Same initial energy and same net ledger flow do not identify survival once
    the execution rule applies a threshold between events. -/
theorem equal_net_flow_can_produce_different_survival :
    ([(-2 : Int), 2].sum = ([2, -2] : List Int).sum) ∧
    ResourceLedger.endingPool 1
      [.operatingCost 2, .verifiedProduction 2] =
        ResourceLedger.endingPool 1
          [.verifiedProduction 2, .operatingCost 2] ∧
    (runEvents 1 { balance := 1, alive := true } [-2, 2]).alive = false ∧
    (runEvents 1 { balance := 1, alive := true } [2, -2]).alive = true ∧
    (runEvents 1 { balance := 1, alive := true } [-2, 2]).balance = 0 ∧
    (runEvents 1 { balance := 1, alive := true } [2, -2]).balance = 1 := by
  decide

end AgentMicrofoundations.ResourceThresholdPath
