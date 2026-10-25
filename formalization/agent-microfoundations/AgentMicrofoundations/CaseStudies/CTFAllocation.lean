import AgentMicrofoundations.OpportunityRationing
import AgentMicrofoundations.AllocationIdentification

/-!
Case instantiations for the CTF experiment.

These declarations instantiate general capacity and group-exposure results
using the experiment's configuration. They are not axioms of the theory and
must not be used to motivate or validate those axioms by themselves.
-/
namespace AgentMicrofoundations.CaseStudies.CTFAllocation

open AgentMicrofoundations.OpportunityRationing
open AgentMicrofoundations.AllocationIdentification

/-- If all three offered tasks are assigned to distinct recipients among six
    agents, at least three agents receive no task that day. -/
theorem six_agents_three_exclusive_tasks_leave_three_unassigned
    (assigned : Nat) (atMostThreeRecipients : assigned ≤ 3) :
    3 ≤ rationedCount 6 assigned := by
  unfold rationedCount
  omega

/-- If the clock permits at most two assignments, at least four of six agents
    are left without a task. This is conditional on the measured capacity. -/
theorem clock_can_increase_daily_rationing
    (assigned clockCapacity : Nat)
    (withinClock : assigned ≤ clockCapacity)
    (clockOnlyAllowsTwo : clockCapacity ≤ 2) :
    4 ≤ rationedCount 6 assigned := by
  unfold rationedCount
  omega

/-- The 4+2 bloc case, conditional on exactly three distinct recipients. -/
theorem six_agents_three_assignments_four_bloc
    (q : Nat)
    (feasible : FeasibleGroupExposure 6 4 3 q) :
    1 ≤ q ∧ q ≤ 3 := by
  rcases sharp_group_exposure_bounds 6 4 3 q feasible with ⟨lower, upper⟩
  omega

theorem six_agents_three_assignments_two_bloc
    (q : Nat)
    (feasible : FeasibleGroupExposure 6 2 3 q) :
    0 ≤ q ∧ q ≤ 2 := by
  rcases sharp_group_exposure_bounds 6 2 3 q feasible with ⟨lower, upper⟩
  omega

theorem four_two_bloc_counts_sum_to_three
    (qFour qTwo : Nat)
    (fourFeasible : FeasibleGroupExposure 6 4 3 qFour)
    (twoFeasible : FeasibleGroupExposure 6 2 3 qTwo)
    (allAssignmentsInPartition : qFour + qTwo = 3) :
    1 ≤ qFour ∧ qFour ≤ 3 ∧ 0 ≤ qTwo ∧ qTwo ≤ 2 ∧ qFour + qTwo = 3 := by
  have fourBounds := six_agents_three_assignments_four_bloc qFour fourFeasible
  have twoBounds := six_agents_three_assignments_two_bloc qTwo twoFeasible
  exact ⟨fourBounds.1, fourBounds.2, twoBounds.1, twoBounds.2, allAssignmentsInPartition⟩

end AgentMicrofoundations.CaseStudies.CTFAllocation
