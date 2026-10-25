import AgentMicrofoundations.CaseStudies.AuthorityDesign

/-!
Executable, response-free mechanics for Authority World v1.

This module formalizes clock phases and the mechanical gate for task
assignment. It does not model why an agent runs, whom an allocator prefers,
or whether a solver answers correctly. Those remain response/production laws
in `AgentEconomyModel`; this module supplies the institutional feasibility
map to which those laws can be coupled.
-/
namespace AgentMicrofoundations.CaseStudies.AuthorityMechanics

open AgentMicrofoundations.CaseStudies.AuthorityDesign

inductive DailyPhase where
  | campaign
  | election
  | resourceDecision
  deriving DecidableEq, Repr

/-- Runtime phase rule: campaign occupies the first interval; election the
    next; resource/task decisions begin at campaign + election seconds. -/
def phaseAt (design : AuthorityWorldDesign) (elapsedSeconds : Rat) : DailyPhase :=
  if elapsedSeconds < design.campaignSeconds then .campaign
  else if elapsedSeconds < design.campaignSeconds + design.electionSeconds then .election
  else .resourceDecision

def campaignEnabled (design : AuthorityWorldDesign) : Prop :=
  design.allocatorSelection = .elected

def candidacyOpen (design : AuthorityWorldDesign) (elapsedSeconds : Rat) : Prop :=
  campaignEnabled design ∧ phaseAt design elapsedSeconds = .campaign

def electionVoteOpen (design : AuthorityWorldDesign) (elapsedSeconds : Rat) : Prop :=
  campaignEnabled design ∧ phaseAt design elapsedSeconds = .election

def taskAssignmentOpen (design : AuthorityWorldDesign) (elapsedSeconds : Rat) : Prop :=
  design.governanceMode = .taskAssignment ∧
    phaseAt design elapsedSeconds = .resourceDecision

theorem random_allocator_removes_campaign_and_election
    (elapsedSeconds : Rat) :
    ¬ candidacyOpen randomTaskFormal elapsedSeconds ∧
      ¬ electionVoteOpen randomTaskFormal elapsedSeconds := by
  simp [candidacyOpen, electionVoteOpen, campaignEnabled,
    randomTaskFormal, electedTaskFormal, competitiveTaskFormal,
    electedResourceFormal]

structure PuzzleAllocation (Agent : Type) where
  closed : Bool
  assignedTo : List Agent

/-- The backend accepts an assignment only when task-assignment governance is
    active, the day is in its decision phase, the actor is the named allocator,
    the puzzle remains open, the recipient has not already been assigned, and
    fewer than the configured winner-limit slots are assigned. -/
def canAssignTask {Agent : Type} [DecidableEq Agent]
    (design : AuthorityWorldDesign) (phase : DailyPhase)
    (leader actor recipient : Agent) (actorAlive recipientAlive puzzleExists : Bool)
    (puzzle : PuzzleAllocation Agent) : Bool :=
  decide (design.governanceMode = .taskAssignment) &&
  decide (phase = .resourceDecision) &&
  decide (leader = actor) &&
  actorAlive && recipientAlive && puzzleExists &&
  !puzzle.closed &&
  !puzzle.assignedTo.contains recipient &&
  decide (puzzle.assignedTo.length < design.puzzleCorrectWinnerLimit)

/-- Mechanical assignment transition. The allocator's choice of recipient is
    an input; this operation enforces only the platform's legality conditions. -/
def assignTask {Agent : Type} [DecidableEq Agent]
    (design : AuthorityWorldDesign) (phase : DailyPhase)
    (leader actor recipient : Agent) (actorAlive recipientAlive puzzleExists : Bool)
    (puzzle : PuzzleAllocation Agent) :
    Option (PuzzleAllocation Agent) := by
  exact if canAssignTask design phase leader actor recipient
      actorAlive recipientAlive puzzleExists puzzle then
    some { puzzle with assignedTo := puzzle.assignedTo ++ [recipient] }
  else none

theorem successful_assignment_obeys_platform_gate
    {Agent : Type} [DecidableEq Agent]
    (design : AuthorityWorldDesign) (phase : DailyPhase)
    (leader actor recipient : Agent) (actorAlive recipientAlive puzzleExists : Bool)
    (puzzle : PuzzleAllocation Agent)
    (next : PuzzleAllocation Agent)
    (success : assignTask design phase leader actor recipient actorAlive recipientAlive
      puzzleExists puzzle = some next) :
    canAssignTask design phase leader actor recipient actorAlive recipientAlive
      puzzleExists puzzle = true := by
  unfold assignTask at success
  by_cases legal : canAssignTask design phase leader actor recipient
      actorAlive recipientAlive puzzleExists puzzle = true
  · exact legal
  · simp [legal] at success

theorem successful_assignment_increments_recipient_count
    {Agent : Type} [DecidableEq Agent]
    (design : AuthorityWorldDesign) (phase : DailyPhase)
    (leader actor recipient : Agent) (actorAlive recipientAlive puzzleExists : Bool)
    (puzzle next : PuzzleAllocation Agent)
    (success : assignTask design phase leader actor recipient actorAlive recipientAlive
      puzzleExists puzzle = some next) :
    next.assignedTo.length = puzzle.assignedTo.length + 1 := by
  unfold assignTask at success
  by_cases legal : canAssignTask design phase leader actor recipient
      actorAlive recipientAlive puzzleExists puzzle = true
  · simp [legal] at success
    have assignedEquality := congrArg PuzzleAllocation.assignedTo success
    have lengthEquality := congrArg List.length assignedEquality
    simpa using lengthEquality.symm
  · simp [legal] at success

theorem successful_assignment_respects_winner_limit
    {Agent : Type} [DecidableEq Agent]
    (design : AuthorityWorldDesign) (phase : DailyPhase)
    (leader actor recipient : Agent) (actorAlive recipientAlive puzzleExists : Bool)
    (puzzle next : PuzzleAllocation Agent)
    (success : assignTask design phase leader actor recipient actorAlive recipientAlive
      puzzleExists puzzle = some next) :
    next.assignedTo.length ≤ design.puzzleCorrectWinnerLimit := by
  have legal := successful_assignment_obeys_platform_gate
    design phase leader actor recipient actorAlive recipientAlive puzzleExists puzzle next success
  have increment := successful_assignment_increments_recipient_count
    design phase leader actor recipient actorAlive recipientAlive puzzleExists puzzle next success
  have belowLimit : puzzle.assignedTo.length < design.puzzleCorrectWinnerLimit := by
    simp [canAssignTask] at legal
    rcases legal with ⟨_, belowLimitNat⟩
    omega
  omega

theorem elected_task_allocator_has_decision_phase
    (elapsedSeconds : Rat)
    (afterCampaign : ¬ elapsedSeconds < electedTaskFormal.campaignSeconds)
    (afterElection : ¬ elapsedSeconds <
      electedTaskFormal.campaignSeconds + electedTaskFormal.electionSeconds) :
    taskAssignmentOpen electedTaskFormal elapsedSeconds := by
  unfold taskAssignmentOpen
  constructor
  · rfl
  · change
      (if elapsedSeconds < (45 : Rat) then DailyPhase.campaign
       else if elapsedSeconds < (45 : Rat) + 30 then DailyPhase.election
       else DailyPhase.resourceDecision) = DailyPhase.resourceDecision
    have notCampaign : ¬ elapsedSeconds < (45 : Rat) := by
      simpa [electedTaskFormal, competitiveTaskFormal, electedResourceFormal] using afterCampaign
    have notElectionEnd : ¬ elapsedSeconds < (45 : Rat) + 30 := by
      simpa [electedTaskFormal, competitiveTaskFormal, electedResourceFormal] using afterElection
    rw [if_neg notCampaign, if_neg notElectionEnd]

end AgentMicrofoundations.CaseStudies.AuthorityMechanics
