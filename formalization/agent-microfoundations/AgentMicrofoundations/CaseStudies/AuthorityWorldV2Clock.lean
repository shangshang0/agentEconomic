import AgentMicrofoundations.CaseStudies.CTFParameterizedSimulation

/-!
Exact opportunity timing for Authority World v2.

The backend uses a daily cycle, with allocation at the beginning of days >= 2,
work after allocation closes, and elected-office registration/voting in the
final 120 seconds. This module formalizes the execution clock only. It does not
infer when an agent acts, votes, solves, or sleeps; those remain response and
production laws.
-/
namespace AgentMicrofoundations.CaseStudies.AuthorityWorldV2Clock

open AgentMicrofoundations.CaseStudies.CTFParameterizedSimulation

structure V2ClockConfig where
  daySeconds : Rat
  allocationSeconds : Rat
  workEndSeconds : Rat
  registrationOpenSeconds : Rat
  taskLifetimeDays : Nat
  maxWorldDays : Nat
  allocatorSelection : CTFOfficeSelection
  institutionSemantics : CTFInstitutionSemantics

def validV2Clock (config : V2ClockConfig) : Prop :=
  0 < config.allocationSeconds ∧
  config.allocationSeconds < config.workEndSeconds ∧
  config.workEndSeconds ≤ config.registrationOpenSeconds ∧
  config.registrationOpenSeconds < config.daySeconds ∧
  config.registrationOpenSeconds + 120 = config.daySeconds ∧
  0 < config.taskLifetimeDays ∧ 2 ≤ config.maxWorldDays

structure V2ClockPoint where
  day : Nat
  secondInDay : Rat

inductive V2Phase where
  | scheduled
  | orientation
  | allocation
  | work
  | politics
  | selection
  | interaction
  deriving DecidableEq, Repr

def finalPhase (config : V2ClockConfig) : V2Phase :=
  if config.allocatorSelection == .none then .interaction
  else if config.institutionSemantics == .humanFramed then .politics
  else .selection

/-- Actual backend phase labels abstracted to the phase distinctions used by
    agent-facing opportunities. Day one has orientation until registration;
    later days expose allocation, then work, then the final daily phase. -/
def phaseAt (config : V2ClockConfig) (point : V2ClockPoint) : V2Phase :=
  if point.day == 1 then
    if point.secondInDay < config.registrationOpenSeconds then .orientation
    else finalPhase config
  else if point.secondInDay < config.allocationSeconds then .allocation
  else if point.secondInDay < config.workEndSeconds then .work
  else finalPhase config

def validClockPoint (config : V2ClockConfig) (point : V2ClockPoint) : Prop :=
  point.day ≤ config.maxWorldDays ∧
    0 ≤ point.secondInDay ∧ point.secondInDay < config.daySeconds

/-- The executable allocator window is the opening interval on days after day 1. -/
def assignmentOpportunityOpen (config : V2ClockConfig) (point : V2ClockPoint) : Prop :=
  2 ≤ point.day ∧ validClockPoint config point ∧
    point.secondInDay < config.allocationSeconds

/-- Assigned work is available only after allocation and strictly before the
    configured work cutoff. -/
def productionOpportunityOpen (config : V2ClockConfig) (point : V2ClockPoint) : Prop :=
  2 ≤ point.day ∧ validClockPoint config point ∧
    config.allocationSeconds ≤ point.secondInDay ∧
    point.secondInDay < config.workEndSeconds

def electionOpportunityOpen (config : V2ClockConfig) (point : V2ClockPoint) : Prop :=
  config.allocatorSelection = .elected ∧ validClockPoint config point ∧
    config.registrationOpenSeconds ≤ point.secondInDay

/-- Backend task expiry uses inclusive day counting: a task offered on day d
    expires at the close of day d + lifetime - 1. -/
def taskExpired (config : V2ClockConfig) (offeredDay currentDay : Nat) : Prop :=
  offeredDay ≤ currentDay ∧ currentDay - offeredDay + 1 ≥ config.taskLifetimeDays

theorem assignment_and_production_windows_disjoint
    (config : V2ClockConfig) (point : V2ClockPoint)
    (assignmentOpen : assignmentOpportunityOpen config point)
    (productionOpen : productionOpportunityOpen config point) : False := by
  exact (Rat.not_lt.mpr productionOpen.2.2.1) assignmentOpen.2.2

theorem no_production_before_allocation_closes
    (config : V2ClockConfig) (point : V2ClockPoint)
    (productionOpen : productionOpportunityOpen config point) :
    config.allocationSeconds ≤ point.secondInDay := productionOpen.2.2.1

theorem work_cutoff_precedes_election_window
    (config : V2ClockConfig) (valid : validV2Clock config)
    (point : V2ClockPoint)
    (electionOpen : electionOpportunityOpen config point) :
    config.workEndSeconds ≤ point.secondInDay := by
  exact Rat.le_trans valid.2.2.1 electionOpen.2.2

theorem expiry_day_is_exact
    (config : V2ClockConfig) (valid : validV2Clock config)
    (offeredDay : Nat) :
    taskExpired config offeredDay (offeredDay + config.taskLifetimeDays - 1) := by
  unfold taskExpired
  have lifeAtLeastOne : 1 ≤ config.taskLifetimeDays :=
    Nat.succ_le_iff.mpr valid.2.2.2.2.2.1
  constructor
  · omega
  · omega

theorem not_expired_before_lifetime
    (config : V2ClockConfig) (offeredDay currentDay : Nat)
    (withinLifetime : currentDay - offeredDay + 1 < config.taskLifetimeDays) :
    ¬ taskExpired config offeredDay currentDay := by
  unfold taskExpired
  omega

/-- Frozen v2 formal configuration used for executable boundary checks. The
    parameters match the checked-in elected/discretion formal design. -/
def electedDiscretionFormalClock : V2ClockConfig where
  daySeconds := 900
  allocationSeconds := 60
  workEndSeconds := 780
  registrationOpenSeconds := 780
  taskLifetimeDays := 3
  maxWorldDays := 25
  allocatorSelection := .elected
  institutionSemantics := .humanFramed

theorem elected_discretion_clock_is_valid :
    validV2Clock electedDiscretionFormalClock := by
  unfold validV2Clock electedDiscretionFormalClock
  exact ⟨by decide, by decide, by decide, by decide,
    by rw [Rat.add_def]; decide, by decide, by decide⟩

theorem allocation_open_on_last_second :
    assignmentOpportunityOpen electedDiscretionFormalClock
      ⟨2, 59⟩ := by
  unfold assignmentOpportunityOpen validClockPoint electedDiscretionFormalClock
  decide

theorem allocation_closed_at_cutoff :
    ¬ assignmentOpportunityOpen electedDiscretionFormalClock
      ⟨2, 60⟩ := by
  unfold assignmentOpportunityOpen validClockPoint electedDiscretionFormalClock
  decide

theorem work_opens_at_allocation_cutoff :
    productionOpportunityOpen electedDiscretionFormalClock
      ⟨2, 60⟩ := by
  unfold productionOpportunityOpen validClockPoint electedDiscretionFormalClock
  decide

theorem work_closed_at_cutoff :
    ¬ productionOpportunityOpen electedDiscretionFormalClock
      ⟨2, 780⟩ := by
  unfold productionOpportunityOpen validClockPoint electedDiscretionFormalClock
  decide

theorem election_opens_at_registration_cutoff :
    electionOpportunityOpen electedDiscretionFormalClock
      ⟨2, 780⟩ := by
  unfold electionOpportunityOpen validClockPoint electedDiscretionFormalClock
  decide

theorem task_lifetime_three_expires_on_third_day :
    taskExpired electedDiscretionFormalClock 4 6 := by
  unfold taskExpired electedDiscretionFormalClock
  decide

theorem task_lifetime_three_not_expired_on_second_day :
    ¬ taskExpired electedDiscretionFormalClock 4 5 := by
  unfold taskExpired electedDiscretionFormalClock
  decide

end AgentMicrofoundations.CaseStudies.AuthorityWorldV2Clock
