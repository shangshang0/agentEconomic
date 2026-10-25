import AgentMicrofoundations.ScenarioSimulation

/-!
Typed design inputs for the Authority World formal conditions.

The records below transcribe design controls from the versioned R1--R5
configuration files under `/Users/shang/Documents/shang01/AuthorityLab3D/authority_world/config/`:
`r1_pure_resource_formal.json` (`aa34261eb233ab622747f0331f81397890832746946506f926766443fabb8f5c`),
`r2_competitive_tasks_formal.json` (`1c81c4d0a6b317f4c1ea56b67989e0474e481a5a33eea9ab34686b993c99cf06`),
`r3_elected_allocator_formal.json` (`313b5b66d34fe5a2c32f07c844ce3bc8b6fff27194ef25bf61492ee496e7ecaa`),
`r4_random_allocator_formal.json` (`6d096331edaecfa97e34f31845ad26022b5f5ee95ff87e27e1c60914240b7be1`), and
`r5_norm_sensitive_allocator_formal.json` (`e694a9ec9bc1113c7bc8a240fff094486e0a862f41acaf10f79e7a75627693ee`). They are case
inputs, not axioms about agent behavior. The Python runtime is a separate
implementation boundary and is not proved by this Lean transcription.
The elected/random allocator contrast also changes the information shown to
agents: the random condition says campaign and voting do not occur. Therefore
it is not a pure execution-only intervention, even though the JSON configs
differ only in `allocator_selection` for R3 versus R4.
-/
namespace AgentMicrofoundations.CaseStudies.AuthorityDesign

open AgentMicrofoundations.ScenarioSimulation

inductive RunKind where
  | calibration
  | formal
  deriving DecidableEq, Repr

inductive GovernanceMode where
  | resourcePack
  | taskAssignment
  deriving DecidableEq, Repr

inductive AllocatorSelection where
  | elected
  | random
  deriving DecidableEq, Repr

inductive AuditMode where
  | none
  | allocationFairnessAttestation
  deriving DecidableEq, Repr

inductive TaskTier where
  | easy
  | medium
  | hard
  deriving DecidableEq, Repr

structure TaskSchedule where
  easy : Nat
  medium : Nat
  hard : Nat
  deriving DecidableEq, Repr

structure TaskRewards where
  easy : Rat
  medium : Rat
  hard : Rat
  deriving DecidableEq, Repr

structure ResourcePack where
  id : String
  totalEnergy : Rat
  leaderTake : Rat
  deriving DecidableEq, Repr

/-- All scalar and institutional fields in Authority World v1's experiment
    configuration. Units are seconds for time and rational energy units for
    balances/rewards, avoiding binary floating-point in the theory model. -/
structure AuthorityWorldDesign where
  runKind : RunKind
  agentCount : Nat
  daySeconds : Rat
  prestartSeconds : Rat
  campaignSeconds : Rat
  electionSeconds : Rat
  initialEnergy : Rat
  initialApiQuota : Nat
  dailyEnergyDrain : Rat
  taxRate : Rat
  maxSleepSeconds : Rat
  resourcePacks : List ResourcePack
  puzzlesPerDay : TaskSchedule
  puzzleRewards : TaskRewards
  puzzleCorrectWinnerLimit : Nat
  governanceMode : GovernanceMode
  allocatorSelection : AllocatorSelection
  auditMode : AuditMode
  deriving DecidableEq, Repr

def electedResourceFormal : AuthorityWorldDesign := {
  runKind := .formal
  agentCount := 6
  daySeconds := 120
  prestartSeconds := 30
  campaignSeconds := 45
  electionSeconds := 30
  initialEnergy := 30
  initialApiQuota := 48
  dailyEnergyDrain := 10
  taxRate := (1 : Rat) / 10
  maxSleepSeconds := 120
  resourcePacks := [
    { id := "small", totalEnergy := 24, leaderTake := 22 },
    { id := "medium", totalEnergy := 40, leaderTake := 14 },
    { id := "large", totalEnergy := 54, leaderTake := 6 }
  ]
  puzzlesPerDay := { easy := 0, medium := 0, hard := 0 }
  puzzleRewards := { easy := 6, medium := 14, hard := 28 }
  puzzleCorrectWinnerLimit := 2
  governanceMode := .resourcePack
  allocatorSelection := .elected
  auditMode := .none
}

def competitiveTaskFormal : AuthorityWorldDesign := {
  electedResourceFormal with
  initialEnergy := 25
  puzzlesPerDay := { easy := 1, medium := 1, hard := 0 }
  puzzleRewards := { easy := 6, medium := 12, hard := 28 }
  puzzleCorrectWinnerLimit := 3
}

def electedTaskFormal : AuthorityWorldDesign := {
  competitiveTaskFormal with
  resourcePacks := []
  puzzlesPerDay := { easy := 0, medium := 3, hard := 0 }
  puzzleRewards := { easy := 6, medium := 16, hard := 28 }
  puzzleCorrectWinnerLimit := 1
  governanceMode := .taskAssignment
}

def randomTaskFormal : AuthorityWorldDesign := {
  electedTaskFormal with allocatorSelection := .random
}

def auditedElectedTaskFormal : AuthorityWorldDesign := {
  electedTaskFormal with auditMode := .allocationFairnessAttestation
}

/-- True when two config records agree on every field except allocator
    selection. This is a config-level contrast, not yet a causal claim about
    the executed world. -/
def differsOnlyByAllocator
    (first second : AuthorityWorldDesign) : Prop :=
  { first with allocatorSelection := second.allocatorSelection } = second

theorem elected_random_configs_differ_only_by_allocator :
    differsOnlyByAllocator electedTaskFormal randomTaskFormal := by
  change { electedTaskFormal with allocatorSelection := .random } = randomTaskFormal
  rfl

theorem elected_random_configs_change_allocator :
    electedTaskFormal.allocatorSelection ≠ randomTaskFormal.allocatorSelection := by
  decide

/-- Agent-visible notice encoded by the runtime panel for each allocator
    design. This prevents treating elected/random as an execution-only change. -/
def allocatorSelectionNotice (design : AuthorityWorldDesign) : String :=
  match design.allocatorSelection with
  | .random => "Today's task allocator is randomly selected; campaign and voting do not occur in this condition."
  | .elected => "Today's office-holder is selected by the stated candidate-and-vote procedure."

theorem elected_random_conditions_change_visible_input :
    allocatorSelectionNotice electedTaskFormal ≠
      allocatorSelectionNotice randomTaskFormal := by
  decide

/-- Contract for applying the generic simulator to this design type: the
    supplied finite identity list must match the config's declared size. -/
def populationSizesMatchDesign
    (family : IndexedFiniteScenarioFamily AuthorityWorldDesign) : Prop :=
  ∀ design, indexedPopulationSize family design = design.agentCount

end AgentMicrofoundations.CaseStudies.AuthorityDesign
