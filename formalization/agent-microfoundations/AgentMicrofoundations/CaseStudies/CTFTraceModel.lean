import AgentMicrofoundations.Accounting
import AgentMicrofoundations.CaseAnalysis

/-!
The CTF case is represented as an arbitrary population and an observed joint
day record. It stores menus, allocator proposals, executed assignments,
verified production, resource changes, and next-period activity separately.
No fixed population size, 4+2 partition, anonymous allocation, or independent
agent law is built into this representation. The finite archive in
`CTFArchive` supplies observed slot frequencies for a small held-out case
forecast; these records provide the reusable data interface for other group
queries and other CTF-like mechanisms.
-/
namespace AgentMicrofoundations.CaseStudies.CTFTraceModel

structure DayRecord (Agent Task : Type) where
  activeAtStart : Agent → Bool
  opportunityMenu : Agent → List Task
  /-- (allocator, intended recipient, task) before mechanism execution. -/
  allocationProposals : List (Agent × Agent × Task)
  /-- (recipient, task) after the mechanism executes. -/
  executedAssignments : List (Agent × Task)
  /-- (agent, task, checker result); absence is distinct from a failed check. -/
  verifiedSubmissions : List (Agent × Task × Bool)
  recordedResourceChange : Agent → Int
  activeNextPeriod : Agent → Bool

def assignmentsToGroup {Agent Task : Type} [DecidableEq Agent]
    (group : List Agent) (record : DayRecord Agent Task) : Nat :=
  (record.executedAssignments.filter fun assignment =>
    decide (assignment.1 ∈ group)).length

def assignmentsOutsideGroup {Agent Task : Type} [DecidableEq Agent]
    (group : List Agent) (record : DayRecord Agent Task) : Nat :=
  (record.executedAssignments.filter fun assignment =>
    !(decide (assignment.1 ∈ group))).length

def productiveSubmissionsToGroup {Agent Task : Type} [DecidableEq Agent]
    (group : List Agent) (record : DayRecord Agent Task) : Nat :=
  (record.verifiedSubmissions.filter fun submission =>
    decide (submission.1 ∈ group) && submission.2.2).length

def failedSubmissionsToGroup {Agent Task : Type} [DecidableEq Agent]
    (group : List Agent) (record : DayRecord Agent Task) : Nat :=
  (record.verifiedSubmissions.filter fun submission =>
    decide (submission.1 ∈ group) && !submission.2.2).length

theorem filter_bool_complement_partition {α : Type} (items : List α)
    (predicate : α → Bool) :
    (items.filter predicate).length +
      (items.filter (fun item => !(predicate item))).length = items.length := by
  induction items with
  | nil => simp
  | cons item rest ih =>
      cases h : predicate item <;> simp [h] <;> omega

theorem filter_bool_refinement_partition {α : Type} (items : List α)
    (selected result : α → Bool) :
    (items.filter (fun item => selected item && result item)).length +
      (items.filter (fun item => selected item && !(result item))).length =
        (items.filter selected).length := by
  induction items with
  | nil => simp
  | cons item rest ih =>
      cases hSelected : selected item <;>
        cases hResult : result item <;>
          simp [hSelected, hResult] <;> omega

/-- For every chosen subset of identities, its assigned tasks and the
    complement's assigned tasks partition the executed allocation record.
    This supports arbitrary post-hoc partitions without assuming that the
    population was experimentally split into those groups. -/
theorem arbitrary_group_assignment_partition
    {Agent Task : Type} [DecidableEq Agent]
    (group : List Agent) (record : DayRecord Agent Task) :
    assignmentsToGroup group record + assignmentsOutsideGroup group record =
      record.executedAssignments.length := by
  unfold assignmentsToGroup assignmentsOutsideGroup
  exact filter_bool_complement_partition record.executedAssignments
    (fun assignment => decide (assignment.1 ∈ group))

/-- Successful and unsuccessful checker results partition recorded
    submissions to any selected group. Unsubmitted assignments are absent from
    both sides and remain a separate state in the record. -/
theorem arbitrary_group_verified_output_partition
    {Agent Task : Type} [DecidableEq Agent]
    (group : List Agent) (record : DayRecord Agent Task) :
    productiveSubmissionsToGroup group record +
      failedSubmissionsToGroup group record =
        (record.verifiedSubmissions.filter fun submission =>
          decide (submission.1 ∈ group)).length := by
  unfold productiveSubmissionsToGroup failedSubmissionsToGroup
  exact filter_bool_refinement_partition record.verifiedSubmissions
    (fun submission => decide (submission.1 ∈ group))
    (fun submission => submission.2.2)

end AgentMicrofoundations.CaseStudies.CTFTraceModel
