import AgentMicrofoundations.Ontology

/-!
Currency as a survival-bearing resource.

This module isolates a narrow mechanism-design fact: when the same fungible
balance is both transferable currency and the resource required for continued
operation, a balanced transfer can change who remains viable without creating
aggregate currency. The result is about the execution technology only. It
does not assume or predict that an agent will offer, accept, or prefer such a
transfer.
-/
namespace AgentMicrofoundations.SurvivalCurrency

/-- Number of viable agents in a two-agent society when each needs at least
    `reserve` units of the common currency to continue. -/
def viableCount (reserve first second : Nat) : Nat :=
  (if reserve ≤ first then 1 else 0) +
    (if reserve ≤ second then 1 else 0)

/-- A zero-fee internal transfer from the first account to the second. -/
def transferFirstToSecond (amount : Nat) (balances : Nat × Nat) : Nat × Nat :=
  (balances.1 - amount, balances.2 + amount)

/-- Count identities whose balances meet the common continuation reserve.
    Positions in the list are identities; no labels are assumed exchangeable. -/
def viableCurrencyCount (reserve : Nat) (balances : List Nat) : Nat :=
  (balances.filter (fun balance => decide (reserve ≤ balance))).length

/-- Rational-valued counterpart for environments with fractional resource
    costs. Each record stores `(threshold, balance)` for one identity. -/
def viableRatThresholdLoad (records : List (Rat × Rat)) : Rat :=
  records.foldr
    (fun record total => if record.1 ≤ record.2 then record.1 + total else total) 0

def recordedRatResourceStock (records : List (Rat × Rat)) : Rat :=
  records.foldr (fun record total => record.2 + total) 0

/-- The heterogeneous survival-capacity bound for rational ledgers, matching
    CTF settings with fractional call costs. Nonnegative balances are explicit;
    no symmetry, independence, or allocation rule is assumed. -/
theorem viable_rat_threshold_load_le_stock
    (records : List (Rat × Rat))
    (nonnegative : ∀ record ∈ records, 0 ≤ record.2) :
    viableRatThresholdLoad records ≤ recordedRatResourceStock records := by
  induction records with
  | nil => simp [viableRatThresholdLoad, recordedRatResourceStock]
  | cons record rest ih =>
      rcases record with ⟨threshold, balance⟩
      have hBalance : 0 ≤ balance := nonnegative (threshold, balance) (by simp)
      have hRestNonnegative : ∀ current ∈ rest, 0 ≤ current.2 := by
        intro current hMem
        exact nonnegative current (by simp [hMem])
      have hRest : viableRatThresholdLoad rest ≤ recordedRatResourceStock rest :=
        ih hRestNonnegative
      change (if threshold ≤ balance then
          threshold + viableRatThresholdLoad rest else viableRatThresholdLoad rest) ≤
        balance + recordedRatResourceStock rest
      by_cases viable : threshold ≤ balance
      · simp [viable]
        exact Rat.le_trans
          ((Rat.add_le_add_right (c := viableRatThresholdLoad rest)).mpr viable)
          ((Rat.add_le_add_left (c := balance)).mpr hRest)
      · simp [viable]
        have hBalanceAdd : viableRatThresholdLoad rest ≤
            balance + viableRatThresholdLoad rest := by
          have h := (Rat.add_le_add_right (c := viableRatThresholdLoad rest)).mpr hBalance
          simpa only [Rat.zero_add] using h
        have hRestAdd : balance + viableRatThresholdLoad rest ≤
            balance + recordedRatResourceStock rest :=
          (Rat.add_le_add_left (c := balance)).mpr hRest
        exact Rat.le_trans hBalanceAdd hRestAdd

/-- Rational-valued all-agent viability requires the sum of heterogeneous
    continuation thresholds to fit within the aggregate resource stock. -/
theorem all_viable_rat_requirements_fit_stock
    (records : List (Rat × Rat))
    (nonnegative : ∀ record ∈ records, 0 ≤ record.2)
    (allViable : ∀ record ∈ records, record.1 ≤ record.2) :
    (records.map Prod.fst).sum ≤ recordedRatResourceStock records := by
  have hLoad : viableRatThresholdLoad records = (records.map Prod.fst).sum := by
    induction records with
    | nil => simp [viableRatThresholdLoad]
    | cons record rest ih =>
        rcases record with ⟨threshold, balance⟩
        have hHead := allViable (threshold, balance) (by simp)
        have hTail : ∀ current ∈ rest, current.1 ≤ current.2 := by
          intro current hMem
          exact allViable current (by simp [hMem])
        have hTailNonnegative : ∀ current ∈ rest, 0 ≤ current.2 := by
          intro current hMem
          exact nonnegative current (by simp [hMem])
        change (if threshold ≤ balance then
            threshold + viableRatThresholdLoad rest else viableRatThresholdLoad rest) =
          threshold + (List.map Prod.fst rest).sum
        simp [hHead]
        rw [ih hTailNonnegative hTail]
  rw [← hLoad]
  exact viable_rat_threshold_load_le_stock records nonnegative

def bilateralRatContinuationCount
    (recipientThreshold donorThreshold recipientBalance donorBalance : Rat) : Int :=
  (if recipientThreshold ≤ recipientBalance then 1 else 0) +
    (if donorThreshold ≤ donorBalance then 1 else 0)

def ratTransferContinuationDelta
    (recipientThreshold donorThreshold recipientBalance donorBalance amount : Rat) : Int :=
  (if recipientBalance < recipientThreshold ∧
      recipientThreshold ≤ recipientBalance + amount then 1 else 0) -
    (if donorBalance - amount < donorThreshold ∧
      donorThreshold ≤ donorBalance then 1 else 0)

theorem rat_upward_threshold_crossing_identity
    (threshold balance increment : Rat) (incrementNonnegative : 0 ≤ increment) :
    (if threshold ≤ balance + increment then (1 : Int) else 0) -
        (if threshold ≤ balance then 1 else 0) =
      (if balance < threshold ∧ threshold ≤ balance + increment then 1 else 0) := by
  have balanceMonotone : balance ≤ balance + increment := by
    have h := (Rat.add_le_add_left (c := balance)).mpr incrementNonnegative
    simpa [Rat.add_zero] using h
  by_cases before : threshold ≤ balance
  · have after : threshold ≤ balance + increment := Rat.le_trans before balanceMonotone
    have noBelow : ¬ balance < threshold := Rat.not_lt.mpr before
    simp [before, after, noBelow]
  · by_cases after : threshold ≤ balance + increment
    · have below : balance < threshold := Rat.not_le.mp before
      simp [before, after, below]
    · simp [before, after]

theorem rat_downward_threshold_crossing_identity
    (threshold balance decrement : Rat) (decrementNonnegative : 0 ≤ decrement) :
    (if threshold ≤ balance - decrement then (1 : Int) else 0) -
        (if threshold ≤ balance then 1 else 0) =
      - (if balance - decrement < threshold ∧ threshold ≤ balance then 1 else 0) := by
  have balanceMonotone : balance - decrement ≤ balance := by
    have addMonotone : balance ≤ balance + decrement := by
      have h := (Rat.add_le_add_left (c := balance)).mpr decrementNonnegative
      simpa [Rat.add_zero] using h
    exact Rat.sub_right_le_iff_le_add.mpr addMonotone
  by_cases after : threshold ≤ balance - decrement
  · have before : threshold ≤ balance := Rat.le_trans after balanceMonotone
    have noBelow : ¬ balance - decrement < threshold := Rat.not_lt.mpr after
    simp [before, after, noBelow]
  · by_cases before : threshold ≤ balance
    · have crossed : balance - decrement < threshold := Rat.not_le.mp after
      simp [before, after, crossed]
    · simp [before, after]

/-- Exact threshold accounting for a rational-valued ledger, including
    fractional costs such as CTF's per-request energy charge. -/
theorem executed_rat_transfer_continuation_change
    (recipientThreshold donorThreshold recipientBalance donorBalance amount : Rat)
    (amountNonnegative : 0 ≤ amount)
    (_affordable : amount ≤ donorBalance) :
    bilateralRatContinuationCount recipientThreshold donorThreshold
        (recipientBalance + amount) (donorBalance - amount) -
        bilateralRatContinuationCount recipientThreshold donorThreshold
          recipientBalance donorBalance =
      ratTransferContinuationDelta recipientThreshold donorThreshold
        recipientBalance donorBalance amount := by
  unfold bilateralRatContinuationCount ratTransferContinuationDelta
  have hRecipient := rat_upward_threshold_crossing_identity
    recipientThreshold recipientBalance amount amountNonnegative
  have hDonor := rat_downward_threshold_crossing_identity
    donorThreshold donorBalance amount amountNonnegative
  have hSplit :
      ((if recipientThreshold ≤ recipientBalance + amount then (1 : Int) else 0) +
          (if donorThreshold ≤ donorBalance - amount then 1 else 0)) -
        ((if recipientThreshold ≤ recipientBalance then 1 else 0) +
          (if donorThreshold ≤ donorBalance then 1 else 0)) =
      ((if recipientThreshold ≤ recipientBalance + amount then 1 else 0) -
          (if recipientThreshold ≤ recipientBalance then 1 else 0)) +
        ((if donorThreshold ≤ donorBalance - amount then 1 else 0) -
          (if donorThreshold ≤ donorBalance then 1 else 0)) := by omega
  rw [hSplit, hRecipient, hDonor]
  omega

/-- For any finite population, every agent whose currency balance meets the
    common survival reserve consumes at least that reserve from the aggregate
    stock. Hence transfers, unequal balances, and arbitrary identity labels
    cannot make the number of viable agents exceed the resource bound. -/
theorem viable_count_times_reserve_le_total_stock
    (reserve : Nat) (balances : List Nat) :
    viableCurrencyCount reserve balances * reserve ≤ balances.sum := by
  induction balances with
  | nil => simp [viableCurrencyCount]
  | cons balance rest ih =>
      have hRest :
          (rest.filter (fun current => decide (reserve ≤ current))).length * reserve ≤
            rest.sum := by
        simpa [viableCurrencyCount] using ih
      by_cases meetsReserve : reserve ≤ balance
      · simp [viableCurrencyCount, meetsReserve]
        rw [Nat.add_mul]
        omega
      · simp [viableCurrencyCount, meetsReserve]
        omega

/-- Feasible internal transfer preserves the total stock of survival currency. -/
theorem internal_transfer_preserves_currency_stock
    (first second amount : Nat) (affordable : amount ≤ first) :
    let after := transferFirstToSecond amount (first, second)
    after.1 + after.2 = first + second := by
  simp [transferFirstToSecond]
  omega

/-- A transfer can raise the number of viable agents when resources are
    initially concentrated. With two agents and a common reserve `d`, moving
    `d` units from an account holding `2d` to an empty account raises the viable
    count from one to two, while preserving total currency `2d`. This is a
    constructive feasibility result, not an equilibrium or choice prediction.
-/
theorem redistribution_can_restore_a_viable_subject
    (reserve : Nat) (positive : 0 < reserve) :
    viableCount reserve (2 * reserve) 0 = 1 ∧
      viableCount reserve
        (transferFirstToSecond reserve (2 * reserve, 0)).1
        (transferFirstToSecond reserve (2 * reserve, 0)).2 = 2 ∧
      (transferFirstToSecond reserve (2 * reserve, 0)).1 +
        (transferFirstToSecond reserve (2 * reserve, 0)).2 = 2 * reserve := by
  cases reserve with
  | zero => omega
  | succ reserve =>
      simp [viableCount, transferFirstToSecond]
      omega

/-- If the society's currency stock is below the reserve required by every
    member, no zero-fee transfer arrangement can make the whole population
    viable. This is the aggregate feasibility boundary, independent of the
    transfer protocol and of agents' response laws. -/
theorem aggregate_shortfall_rules_out_full_viability
    (reserve first second : Nat)
    (shortfall : first + second < 2 * reserve) :
    ¬ (reserve ≤ first ∧ reserve ≤ second) := by
  omega

end AgentMicrofoundations.SurvivalCurrency
