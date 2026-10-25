import Std

/-!
Scarce, time-bounded production opportunities.

The lemmas separate (i) mechanical rationing imposed by exclusive slots and
the allocation clock from (ii) persistent behavioral specialization. The
clock-capacity input is the maximum number of assignments feasible before the
deadline; it may be measured from traces or derived from a lower bound on
decision duration. No agent rationality assumption is used.
-/
namespace AgentMicrofoundations.OpportunityRationing

def effectiveCapacity (jobSlots clockCapacity : Nat) : Nat :=
  min jobSlots clockCapacity

def rationedCount (population assigned : Nat) : Nat :=
  population - assigned

theorem effective_capacity_bounds_assignments
    (jobSlots clockCapacity assigned : Nat)
    (withinJobSlots : assigned ≤ jobSlots)
    (withinClock : assigned ≤ clockCapacity) :
    assigned ≤ effectiveCapacity jobSlots clockCapacity := by
  exact Nat.le_min.mpr ⟨withinJobSlots, withinClock⟩

/-- With one recipient per opportunity, the joint job and clock capacity
     yields a lower bound on the number of agents left without a slot. -/
theorem exclusive_opportunity_rationing_bound
    (population jobSlots clockCapacity assigned : Nat)
    (withinPopulation : assigned ≤ population)
    (withinJobSlots : assigned ≤ jobSlots)
    (withinClock : assigned ≤ clockCapacity) :
    population - effectiveCapacity jobSlots clockCapacity ≤
      rationedCount population assigned := by
  have capacityBound := effective_capacity_bounds_assignments
    jobSlots clockCapacity assigned withinJobSlots withinClock
  unfold rationedCount effectiveCapacity
  omega

theorem scarcity_implies_at_least_one_unassigned
    (population jobSlots clockCapacity assigned : Nat)
    (withinJobSlots : assigned ≤ jobSlots)
    (withinClock : assigned ≤ clockCapacity)
    (scarcity : effectiveCapacity jobSlots clockCapacity < population) :
    0 < rationedCount population assigned := by
  have capacityBound := effective_capacity_bounds_assignments
    jobSlots clockCapacity assigned withinJobSlots withinClock
  unfold rationedCount effectiveCapacity at *
  omega

/- Verified output and differential compute cost turn a one-period allocation
   into a resource-state difference. This is accounting, not a claim that the
   recipient will be selected again. -/
def nextResource (resource upkeep computeCost verifiedOutput : Int) : Int :=
  resource - upkeep - computeCost + verifiedOutput

theorem task_allocation_resource_gap_is_output_minus_incremental_cost
    (resource upkeep recipientCost idleCost verifiedOutput : Int) :
    nextResource resource upkeep recipientCost verifiedOutput -
      nextResource resource upkeep idleCost 0 =
        verifiedOutput + idleCost - recipientCost := by
  simp [nextResource]
  omega

theorem positive_net_task_output_raises_recipient_resource
    (resource upkeep recipientCost idleCost verifiedOutput : Int)
    (positiveNet : recipientCost < verifiedOutput + idleCost) :
    nextResource resource upkeep idleCost 0 <
      nextResource resource upkeep recipientCost verifiedOutput := by
  unfold nextResource
  omega

end AgentMicrofoundations.OpportunityRationing
