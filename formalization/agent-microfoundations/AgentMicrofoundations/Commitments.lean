import Std
import AgentMicrofoundations.Ontology

/-!
Contract and liquidity primitives for persistent agent economies.

The same token balance can imply different feasible actions when current
balances are already encumbered by due commitments. Commitments are claims on
resources, not resources themselves.
-/
namespace AgentMicrofoundations.Commitments

structure SettlementState where
  tokenBalance : Nat
  dueCommitments : Nat
  transferLimit : Nat
  deriving DecidableEq, Repr

/-- Optional contract-state extension of the core agent state. The core
    ontology stays applicable to cases without contracts; when due claims
    constrain future execution, this extension makes them explicit instead
    of hiding them in an unrestricted internal-state field. -/
structure CommitmentAugmentedAgentState (InternalState : Type) where
  base : AgentMicrofoundations.Ontology.AgentState InternalState Nat
  dueCommitments : Nat
  transferLimit : Nat

/-- The account view consumed by the settlement rule, preserving the
    obligation coordinate in addition to the core agent state. -/
def settlementView {InternalState : Type}
    (state : CommitmentAugmentedAgentState InternalState) : SettlementState :=
  ⟨state.base.resources, state.dueCommitments, state.transferLimit⟩

def canSettle (state : SettlementState) (payment : Nat) : Prop :=
  state.dueCommitments + payment ≤ state.tokenBalance ∧
    payment ≤ state.transferLimit

/- A balance-only state representation cannot identify whether a payment is
   feasible: two agents with the same tokens and transfer limit differ only in
   already-due obligations. -/
theorem same_base_agent_state_different_commitments_change_payment_feasibility :
    let unencumbered : CommitmentAugmentedAgentState Unit :=
      ⟨⟨(), 10⟩, 0, 10⟩
    let committed : CommitmentAugmentedAgentState Unit :=
      ⟨⟨(), 10⟩, 5, 10⟩
    unencumbered.base = committed.base ∧
      canSettle (settlementView unencumbered) 6 ∧
      ¬ canSettle (settlementView committed) 6 := by
  simp [canSettle, settlementView]

end AgentMicrofoundations.Commitments
