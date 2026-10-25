import Std

/-!
An event-level resource ledger shared by token economies with different
institutions. A token is an accounting unit here; no conversion to money,
utility, or compute is assumed. Production, external finance, consumption,
and internal transfers are kept as distinct event types.

`transfer` records the aggregate effect of an internal, budget-balanced
transfer across all agents. It is zero at the aggregate level, while its
distributional effects require account-level data.
-/
namespace AgentMicrofoundations.ResourceLedger

inductive Event where
  | verifiedProduction (amount : Nat)
  | externalSupply (amount : Nat)
  | externalDrain (amount : Nat)
  | operatingCost (amount : Nat)
  | internalTransfer (amount : Nat)
  deriving DecidableEq, Repr

def resourceDelta : Event → Int
  | .verifiedProduction amount => amount
  | .externalSupply amount => amount
  | .externalDrain amount => -(amount : Int)
  | .operatingCost amount => -(amount : Int)
  | .internalTransfer _ => 0

def productionAmount : Event → Nat
  | .verifiedProduction amount => amount
  | _ => 0

def eventResourceChange : List Event → Int
  | [] => 0
  | event :: rest => resourceDelta event + eventResourceChange rest

def verifiedOutput (events : List Event) : Nat :=
  events.foldl (fun total event => total + productionAmount event) 0

def endingPool (initialPool : Int) (events : List Event) : Int :=
  initialPool + eventResourceChange events

theorem internal_transfer_does_not_change_aggregate_pool (amount : Nat) :
    resourceDelta (.internalTransfer amount) = 0 := by
  rfl

theorem appending_internal_transfer_preserves_aggregate_pool
    (initialPool : Int) (events : List Event) (amount : Nat) :
    endingPool initialPool (events ++ [.internalTransfer amount]) =
      endingPool initialPool events := by
  simp only [endingPool]
  have h : eventResourceChange (events ++ [.internalTransfer amount]) =
      eventResourceChange events := by
    induction events with
    | nil => simp [eventResourceChange, resourceDelta]
    | cons event rest ih =>
        simp only [List.cons_append, eventResourceChange]
        rw [ih]
  rw [h]

theorem terminal_pool_is_invariant_to_two_event_order
    (initialPool : Int) (first second : Event) :
    endingPool initialPool [first, second] =
      endingPool initialPool [second, first] := by
  simp [endingPool, eventResourceChange, resourceDelta, Int.add_comm]

/- A balance observation identifies a net resource change, not its source.
   Identifying productive capacity therefore requires event provenance, such as
   a validated task result, instead of balance changes alone. -/
theorem balance_change_does_not_identify_production_source :
    endingPool 0 [.verifiedProduction 3] =
        endingPool 0 [.externalSupply 3] ∧
      verifiedOutput [.verifiedProduction 3] = 3 ∧
      verifiedOutput [.externalSupply 3] = 0 := by
  decide

/- Token denomination is conventional: scaling every event and the initial
   pool by the same positive integer scales the ending pool by that integer.
   This is an accounting invariance, not a claim that tokens have a stable
   external price or equal compute value. -/
def scaleEvent (factor : Nat) : Event → Event
  | .verifiedProduction amount => .verifiedProduction (factor * amount)
  | .externalSupply amount => .externalSupply (factor * amount)
  | .externalDrain amount => .externalDrain (factor * amount)
  | .operatingCost amount => .operatingCost (factor * amount)
  | .internalTransfer amount => .internalTransfer (factor * amount)

def scaleEvents (factor : Nat) (events : List Event) : List Event :=
  events.map (scaleEvent factor)

theorem scale_resource_delta (factor : Nat) (event : Event) :
    resourceDelta (scaleEvent factor event) =
      (factor : Int) * resourceDelta event := by
  cases event <;> simp [scaleEvent, resourceDelta, Int.mul_neg]

theorem event_resource_change_scales
    (factor : Nat) (events : List Event) :
    eventResourceChange (scaleEvents factor events) =
      (factor : Int) * eventResourceChange events := by
  induction events with
  | nil => simp [eventResourceChange, scaleEvents]
  | cons event rest ih =>
      change resourceDelta (scaleEvent factor event) +
        eventResourceChange (scaleEvents factor rest) =
        (factor : Int) * (resourceDelta event + eventResourceChange rest)
      rw [scale_resource_delta, ih, ← Int.mul_add]

theorem denomination_scaling_preserves_ending_pool
    (factor : Nat) (initialPool : Int) (events : List Event) :
    endingPool ((factor : Int) * initialPool) (scaleEvents factor events) =
      (factor : Int) * endingPool initialPool events := by
  simp only [endingPool, event_resource_change_scales]
  rw [Int.mul_add]

end AgentMicrofoundations.ResourceLedger
