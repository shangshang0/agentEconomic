import AgentMicrofoundations.Commitments

/-!
Account-level settlement semantics connecting obligations to the aggregate
resource ledger. The transfer rule is mechanical: it does not model why an
agent proposes payment or whether the underlying contract is socially useful.
-/
namespace AgentMicrofoundations.Settlement

open AgentMicrofoundations.Commitments

def spendableBalance (state : SettlementState) : Nat :=
  state.tokenBalance - state.dueCommitments

/- A spendable-balance representation is equivalent to the original settlement
   constraint only for a solvent account. -/
theorem canSettle_iff_within_spendable_balance
    (state : SettlementState) (payment : Nat)
    (solvent : state.dueCommitments ≤ state.tokenBalance) :
    canSettle state payment ↔
      payment ≤ spendableBalance state ∧ payment ≤ state.transferLimit := by
  unfold canSettle spendableBalance
  omega

/- Execute a payment only when the payer can cover due commitments and the
   payment. A rejected payment leaves both accounts unchanged. -/
def executeTransfer (payer receiver : SettlementState) (payment : Nat) :
    SettlementState × SettlementState :=
  if payer.dueCommitments + payment ≤ payer.tokenBalance ∧
      payment ≤ payer.transferLimit then
      ( { payer with tokenBalance := payer.tokenBalance - payment }
      , { receiver with tokenBalance := receiver.tokenBalance + payment } )
    else (payer, receiver)

theorem executed_transfer_preserves_total_tokens
    (payer receiver : SettlementState) (payment : Nat) :
    (executeTransfer payer receiver payment).1.tokenBalance +
    (executeTransfer payer receiver payment).2.tokenBalance =
      payer.tokenBalance + receiver.tokenBalance := by
  classical
  by_cases feasible : payer.dueCommitments + payment ≤ payer.tokenBalance ∧
      payment ≤ payer.transferLimit
  · simp [executeTransfer, feasible]
    omega
  · simp [executeTransfer, feasible]

theorem executed_transfer_preserves_due_commitments
    (payer receiver : SettlementState) (payment : Nat) :
    (executeTransfer payer receiver payment).1.dueCommitments =
        payer.dueCommitments ∧
      (executeTransfer payer receiver payment).2.dueCommitments =
        receiver.dueCommitments := by
  classical
  by_cases feasible : payer.dueCommitments + payment ≤ payer.tokenBalance ∧
      payment ≤ payer.transferLimit
  · simp [executeTransfer, feasible]
  · simp [executeTransfer, feasible]

theorem accepted_transfer_keeps_payer_solvent
    (payer receiver : SettlementState) (payment : Nat)
    (accepted : canSettle payer payment) :
    payer.dueCommitments ≤
      (executeTransfer payer receiver payment).1.tokenBalance := by
  classical
  unfold canSettle at accepted
  simp [executeTransfer, accepted]
  omega

theorem rejected_transfer_changes_no_account
    (payer receiver : SettlementState) (payment : Nat)
    (rejected : ¬ canSettle payer payment) :
    executeTransfer payer receiver payment = (payer, receiver) := by
  classical
  unfold canSettle at rejected
  simp [executeTransfer, rejected]

/- A due-commitment payment is different from a discretionary transfer: it
   moves resources and clears the same amount of the payer's due obligation. -/
def settleDueCommitment (payer receiver : SettlementState) (payment : Nat) :
    SettlementState × SettlementState :=
  if payment ≤ payer.dueCommitments ∧
      payment ≤ payer.tokenBalance ∧
      payment ≤ payer.transferLimit then
    ( { payer with
        tokenBalance := payer.tokenBalance - payment
        dueCommitments := payer.dueCommitments - payment }
    , { receiver with tokenBalance := receiver.tokenBalance + payment } )
  else (payer, receiver)

theorem settled_due_payment_preserves_total_tokens
    (payer receiver : SettlementState) (payment : Nat) :
    (settleDueCommitment payer receiver payment).1.tokenBalance +
        (settleDueCommitment payer receiver payment).2.tokenBalance =
      payer.tokenBalance + receiver.tokenBalance := by
  by_cases accepted : payment ≤ payer.dueCommitments ∧
      payment ≤ payer.tokenBalance ∧ payment ≤ payer.transferLimit
  · simp [settleDueCommitment, accepted]
    omega
  · simp [settleDueCommitment, accepted]

theorem settled_due_payment_reduces_claim
    (payer receiver : SettlementState) (payment : Nat)
    (accepted : payment ≤ payer.dueCommitments ∧
      payment ≤ payer.tokenBalance ∧ payment ≤ payer.transferLimit) :
    (settleDueCommitment payer receiver payment).1.dueCommitments =
      payer.dueCommitments - payment := by
  simp [settleDueCommitment, accepted]

theorem settled_due_payment_preserves_spendable_balance
    (payer receiver : SettlementState) (payment : Nat)
    (solvent : payer.dueCommitments ≤ payer.tokenBalance)
    (accepted : payment ≤ payer.dueCommitments ∧
      payment ≤ payer.tokenBalance ∧ payment ≤ payer.transferLimit) :
    spendableBalance (settleDueCommitment payer receiver payment).1 =
      spendableBalance payer := by
  simp [spendableBalance, settleDueCommitment, accepted]
  omega

theorem rejected_due_payment_changes_no_account
    (payer receiver : SettlementState) (payment : Nat)
    (rejected : ¬ (payment ≤ payer.dueCommitments ∧
      payment ≤ payer.tokenBalance ∧ payment ≤ payer.transferLimit)) :
    settleDueCommitment payer receiver payment = (payer, receiver) := by
  simp [settleDueCommitment, rejected]

end AgentMicrofoundations.Settlement
