import Std

/-!
Intertemporal liquidity for agents with dated receipts, due commitments, and
inference/operation costs. A flow is settled at its date; later receipts cannot
be used retroactively to meet an earlier hard payment deadline.
-/
namespace AgentMicrofoundations.Liquidity

structure PeriodFlow where
  receipts : Nat
  dueCommitments : Nat
  operatingCost : Nat
  deriving DecidableEq, Repr

def nextBalance (balance : Int) (flow : PeriodFlow) : Int :=
  balance + (flow.receipts : Int) - (flow.dueCommitments : Int) - (flow.operatingCost : Int)

def timelineSolvent (balance : Int) : List PeriodFlow → Prop
  | [] => 0 ≤ balance
  | flow :: rest =>
      let next := nextBalance balance flow
      0 ≤ next ∧ timelineSolvent next rest

def terminalBalance (balance : Int) : List PeriodFlow → Int
  | [] => balance
  | flow :: rest => terminalBalance (nextBalance balance flow) rest

theorem solvent_timeline_implies_nonnegative_terminal_balance
    (balance : Int) (flows : List PeriodFlow)
    (solvent : timelineSolvent balance flows) :
    0 ≤ terminalBalance balance flows := by
  induction flows generalizing balance with
  | nil => simpa [timelineSolvent, terminalBalance] using solvent
  | cons flow rest ih =>
      simpa [timelineSolvent, terminalBalance] using ih (nextBalance balance flow) solvent.2

/- Positive end-of-horizon balance does not imply that all dated commitments
   were payable when due. Starting with 3, a payment of 5 due now, and a receipt
   of 10 arriving next period yields terminal balance 8 but defaults now. -/
theorem later_receipt_cannot_retroactively_prevent_default :
    terminalBalance 3 [⟨0, 5, 0⟩, ⟨10, 0, 0⟩] = 8 ∧
      ¬ timelineSolvent 3 [⟨0, 5, 0⟩, ⟨10, 0, 0⟩] := by
  simp [terminalBalance, timelineSolvent, nextBalance]

end AgentMicrofoundations.Liquidity
