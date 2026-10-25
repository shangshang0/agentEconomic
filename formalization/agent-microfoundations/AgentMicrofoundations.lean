import Std
import AgentMicrofoundations.GroupProbability
import AgentMicrofoundations.Ontology
import AgentMicrofoundations.AutoregressiveResponse
import AgentMicrofoundations.AutoregressiveIdentification
import AgentMicrofoundations.PopulationTransport
import AgentMicrofoundations.ComputationalEconomy
import AgentMicrofoundations.TokenAccounting
import AgentMicrofoundations.ResponseIdentification
import AgentMicrofoundations.CouplingComparativeStatics
import AgentMicrofoundations.AutoregressiveCouplingSensitivity
import AgentMicrofoundations.ContextualResponse
import AgentMicrofoundations.AutoregressiveContext
import AgentMicrofoundations.PopulationInputShift
import AgentMicrofoundations.ResourceBudgetComparativeStatics
import AgentMicrofoundations.OntologyExamples
import AgentMicrofoundations.FiniteDynamics
import AgentMicrofoundations.ScenarioSimulation
import AgentMicrofoundations.MechanismCounterfactual
import AgentMicrofoundations.SequentialBounds
import AgentMicrofoundations.AnonymousAllocation
import AgentMicrofoundations.AllocationFeedback
import AgentMicrofoundations.ResourceOpportunityCascade
import AgentMicrofoundations.GroupPrediction
import AgentMicrofoundations.Accounting
import AgentMicrofoundations.Commitments
import AgentMicrofoundations.Liquidity
import AgentMicrofoundations.ResourceLedger
import AgentMicrofoundations.SurvivalCurrency
import AgentMicrofoundations.ResourceSurvivalBound
import AgentMicrofoundations.TemporalIntersectionBounds
import AgentMicrofoundations.Settlement
import AgentMicrofoundations.CausalInterface
import AgentMicrofoundations.FiniteCoalitions
import AgentMicrofoundations.Symmetry
import AgentMicrofoundations.Specialization
import AgentMicrofoundations.OpportunitySpecialization
import AgentMicrofoundations.ResourceThresholdPersistence
import AgentMicrofoundations.ResourceThresholdPath
import AgentMicrofoundations.OpportunityRationing
import AgentMicrofoundations.MechanismFeedback
import AgentMicrofoundations.AllocationIdentification
import AgentMicrofoundations.CaseAnalysis
import AgentMicrofoundations.CaseStudies.CTFAllocation
import AgentMicrofoundations.CaseStudies.CTFModel
import AgentMicrofoundations.CaseStudies.CTFTraceModel
import AgentMicrofoundations.CaseStudies.CTFArchive
import AgentMicrofoundations.CaseStudies.CTFParameterizedSimulation
import AgentMicrofoundations.CaseStudies.CTFResourceSimulation
import AgentMicrofoundations.CaseStudies.AuthorityDesign
import AgentMicrofoundations.CaseStudies.AuthorityMechanics
import AgentMicrofoundations.CaseStudies.AuthorityWorldV2Clock
import AgentMicrofoundations.CaseStudies.AuthorityWorldV2Election
import AgentMicrofoundations.CaseStudies.ResourceSignalPilot

/-!
Microfoundations for agent-centered economics.

The results are conditional arithmetic consequences of an explicit resource
ledger and a finite-resolution success probability. No optimality or human
utility axiom is used. The module also refutes the claim that nonnegative
expected drift guarantees pathwise survival.
-/
namespace AgentMicrofoundations

/- A surviving agent must hold at least `minimumReserve`. -/
def IndividuallyViable (minimumReserve : Nat) (reserve : Nat) : Prop :=
  minimumReserve ≤ reserve

/- Total reserve is bounded by the pool available to these agents. -/
theorem reserves_cover_viable_population
    (minimumReserve totalPool : Nat) (reserves : List Nat)
    (positive : 0 < minimumReserve)
    (eachViable : ∀ reserve ∈ reserves, IndividuallyViable minimumReserve reserve)
    (poolBound : reserves.sum ≤ totalPool) :
    reserves.length * minimumReserve ≤ totalPool := by
  have lower : reserves.length * minimumReserve ≤ reserves.sum := by
    induction reserves with
    | nil => simp
    | cons reserve rest ih =>
        have hReserve : minimumReserve ≤ reserve := eachViable reserve (by simp)
        have hRest : ∀ x ∈ rest, minimumReserve ≤ x := by
          intro x hx
          exact eachViable x (by simp [hx])
        have hTailBound : rest.sum ≤ totalPool := by
          have h := poolBound
          simp only [List.sum_cons] at h
          omega
        have hTail : rest.length * minimumReserve ≤ rest.sum := ih hRest hTailBound
        simp only [List.length_cons, List.sum_cons]
        simp only [Nat.add_mul, Nat.one_mul]
        omega
  omega

/- A success probability is represented as `successUnits / probabilityScale`.
   Resource and reward quantities share the same integer unit. -/
def expectedNetNumerator (probabilityScale successUnits reward calls callCost upkeep : Nat) : Int :=
  (successUnits : Int) * (reward : Int) -
    (probabilityScale : Int) * ((calls * callCost + upkeep : Nat) : Int)

theorem expected_net_nonnegative_iff
    (probabilityScale successUnits reward calls callCost upkeep : Nat)
    (validScale : 0 < probabilityScale)
    (validProbability : successUnits ≤ probabilityScale) :
    0 ≤ expectedNetNumerator probabilityScale successUnits reward calls callCost upkeep ↔
      probabilityScale * (calls * callCost + upkeep) ≤ successUnits * reward := by
  have _ := validScale
  have _ := validProbability
  unfold expectedNetNumerator
  omega

theorem capability_improves_expected_gross_output
    (pLow pHigh reward : Nat)
    (probabilityOrdered : pLow ≤ pHigh) :
    pLow * reward ≤ pHigh * reward := by
  exact Nat.mul_le_mul_right reward probabilityOrdered

theorem capability_improves_expected_net_output_at_fixed_cost
    (probabilityScale pLow pHigh reward calls callCost upkeep : Nat)
    (validScale : 0 < probabilityScale)
    (validProbability : pHigh ≤ probabilityScale)
    (probabilityOrdered : pLow ≤ pHigh) :
    expectedNetNumerator probabilityScale pLow reward calls callCost upkeep ≤
      expectedNetNumerator probabilityScale pHigh reward calls callCost upkeep := by
  have _ := validScale
  have _ := validProbability
  unfold expectedNetNumerator
  have hGross : (pLow : Int) * (reward : Int) ≤ (pHigh : Int) * (reward : Int) := by
    exact_mod_cast (Nat.mul_le_mul_right reward probabilityOrdered)
  omega

/- One additional unit of compute can improve success probability, but it is
   resource-positive only when its expected reward gain covers its cost. -/
def marginalComputeNetNumerator
    (probabilityScale probabilityGain reward callCost : Nat) : Int :=
  (probabilityGain : Int) * (reward : Int) -
    (probabilityScale : Int) * (callCost : Int)

theorem extra_compute_is_resource_positive_iff
    (probabilityScale probabilityGain reward callCost : Nat)
    (validScale : 0 < probabilityScale)
    (validProbabilityGain : probabilityGain ≤ probabilityScale) :
    0 ≤ marginalComputeNetNumerator probabilityScale probabilityGain reward callCost ↔
      probabilityScale * callCost ≤ probabilityGain * reward := by
  have _ := validScale
  have _ := validProbabilityGain
  unfold marginalComputeNetNumerator
  omega

/- A period spends upkeep, then receives the task reward on success. -/
def afterOutcome (balance upkeep reward : Int) (success : Bool) : Int :=
  balance - upkeep + if success then reward else 0

def runOutcomes (balance upkeep reward : Int) : List Bool → Int
  | [] => balance
  | outcome :: rest =>
      runOutcomes (afterOutcome balance upkeep reward outcome) upkeep reward rest

def survivesOutcomes (balance upkeep reward : Int) : List Bool → Bool
  | [] => 0 < balance
  | outcome :: rest =>
      let nextBalance := afterOutcome balance upkeep reward outcome
      (0 < nextBalance) && survivesOutcomes nextBalance upkeep reward rest

def pathSucceedsAt (period : Nat) (path : List Bool) : Bool :=
  match path[period]? with
  | some success => success
  | none => false

def pathSuccessCountAt (paths : List (List Bool)) (period : Nat) : Nat :=
  (paths.filter (pathSucceedsAt period)).length

def pathSurvivalCount (paths : List (List Bool)) (balance upkeep reward : Int) : Nat :=
  (paths.filter (fun path => survivesOutcomes balance upkeep reward path)).length

def independentThreePeriodPaths : List (List Bool) :=
  [ [false, false, false], [false, false, true],
    [false, true, false], [false, true, true],
    [true, false, false], [true, false, true],
    [true, true, false], [true, true, true] ]

def persistentThreePeriodPaths : List (List Bool) :=
  [ [true, true, true], [true, true, true], [true, true, true], [true, true, true],
    [false, false, false], [false, false, false], [false, false, false], [false, false, false] ]

/- Equal per-period success probabilities do not identify survival probability.
   IID contexts and a context drawn once then held fixed both give a 1/2 success
   rate in every period, but induce different temporal dependence and survival. -/
theorem same_marginal_success_different_context_persistence_changes_survival :
    (∀ period, period < 3 →
      pathSuccessCountAt independentThreePeriodPaths period = 4 ∧
        pathSuccessCountAt persistentThreePeriodPaths period = 4) ∧
      pathSurvivalCount independentThreePeriodPaths 1 1 2 = 3 ∧
      pathSurvivalCount persistentThreePeriodPaths 1 1 2 = 4 := by
  decide

/- A symmetric two-context Markov model over three periods. `persistence`
   is the integer weight assigned to staying in the same context; switching
   receives `scale - persistence`. The initial context is represented with
   equal weight for true and false. This is a conditional model, not an axiom
   about real agents. -/
def contextMarkovPaths : List (List Bool) :=
  [ [false, false, false], [false, false, true],
    [false, true, false], [false, true, true],
    [true, false, false], [true, false, true],
    [true, true, false], [true, true, true] ]

def contextTransitionWeight (scale persistence : Nat) (sourceContext targetContext : Bool) : Nat :=
  if sourceContext == targetContext then persistence else scale - persistence

def contextMarkovPathWeight (scale persistence : Nat) (path : List Bool) : Nat :=
  match path with
  | [first, second, third] =>
      contextTransitionWeight scale persistence first second *
        contextTransitionWeight scale persistence second third
  | _ => 0

def contextMarkovTotalWeight (scale persistence : Nat) : Nat :=
  (contextMarkovPaths.map (contextMarkovPathWeight scale persistence)).sum

def contextMarkovSuccessWeight (scale persistence period : Nat) : Nat :=
  ((contextMarkovPaths.filter (pathSucceedsAt period)).map
    (contextMarkovPathWeight scale persistence)).sum

def contextMarkovSurvivalWeight (scale persistence : Nat) : Nat :=
  ((contextMarkovPaths.filter (fun path => survivesOutcomes 1 1 2 path)).map
    (contextMarkovPathWeight scale persistence)).sum

/- The exact unnormalized mass of surviving paths is the sum of three paths:
   success-success-success, success-success-failure, and success-failure-success.
   The admissible parameter range `persistence ≤ scale` makes the switching
   weight nonnegative and the weights a valid finite Markov model. -/
theorem three_period_markov_survival_mass
    (scale persistence : Nat) :
    contextMarkovSurvivalWeight scale persistence =
      persistence * persistence +
        persistence * (scale - persistence) +
        (scale - persistence) * (scale - persistence) := by
  simp [contextMarkovSurvivalWeight, contextMarkovPaths,
    contextMarkovPathWeight, contextTransitionWeight, survivesOutcomes,
    afterOutcome]
  omega

/- At scale 2, independent contexts (`persistence = 1`), perfect alternation
   (`0`), and perfect persistence (`2`) all have the same 1/2 success marginal
   in each period. Yet the iid case has lower survival mass (3/8) than either
   dependence extreme (4/8). This is a model-specific, falsifiable result:
   survival is not monotone in context persistence. -/
theorem same_marginals_nonmonotone_survival_across_context_dynamics :
    contextMarkovTotalWeight 2 0 = 8 ∧
      contextMarkovSuccessWeight 2 0 0 = 4 ∧
      contextMarkovSuccessWeight 2 0 1 = 4 ∧
      contextMarkovSuccessWeight 2 0 2 = 4 ∧
      contextMarkovSurvivalWeight 2 0 = 4 ∧
      contextMarkovTotalWeight 2 1 = 8 ∧
      contextMarkovSuccessWeight 2 1 0 = 4 ∧
      contextMarkovSuccessWeight 2 1 1 = 4 ∧
      contextMarkovSuccessWeight 2 1 2 = 4 ∧
      contextMarkovSurvivalWeight 2 1 = 3 ∧
      contextMarkovTotalWeight 2 2 = 8 ∧
      contextMarkovSuccessWeight 2 2 0 = 4 ∧
      contextMarkovSuccessWeight 2 2 1 = 4 ∧
      contextMarkovSuccessWeight 2 2 2 = 4 ∧
      contextMarkovSurvivalWeight 2 2 = 4 := by
  simp [contextMarkovTotalWeight, contextMarkovSuccessWeight,
    contextMarkovSurvivalWeight, contextMarkovPaths, contextMarkovPathWeight,
    contextTransitionWeight, pathSucceedsAt, survivesOutcomes, afterOutcome]

/- Conjecture refuted: positive expected resource drift does not imply survival
   on every possible path. At success probability 1/2, reward 6, upkeep 2,
   expected net gain is +1 per period; from reserve 3, two failures still
   exhaust the reserve. -/
theorem positive_expected_drift_does_not_guarantee_pathwise_survival :
    0 < expectedNetNumerator 2 1 6 0 0 2 ∧
    runOutcomes 3 2 6 [false, false] ≤ 0 := by
  decide



/- A transfer-only mechanism changes who holds the resource, not the aggregate
   pool, when transfers are budget-balanced and have no execution fee. -/
def transferOnlyPool (pool inflow outflow : Nat) : Nat := pool + inflow - outflow

theorem balanced_transfers_preserve_aggregate_resource
    (pool inflow outflow : Nat)
    (balanced : inflow = outflow) :
    transferOnlyPool pool inflow outflow = pool := by
  unfold transferOnlyPool
  omega

theorem balanced_transfers_cannot_cross_population_viability_boundary
    (pool inflow outflow population minimumReserve : Nat)
    (balanced : inflow = outflow)
    (resourceShortfall : pool < population * minimumReserve) :
    ¬ population * minimumReserve ≤ transferOnlyPool pool inflow outflow := by
  unfold transferOnlyPool
  omega

/- An allocation is feasible when it assigns one reserve to every member,
   keeps each at the viability threshold, and does not spend more than the pool. -/
def FeasibleAllocation (minimumReserve population pool : Nat) (reserves : List Nat) : Prop :=
  reserves.length = population ∧
    (∀ reserve ∈ reserves, minimumReserve ≤ reserve) ∧
    reserves.sum ≤ pool

theorem sum_replicate_nat (population amount : Nat) :
    (List.replicate population amount).sum = population * amount := by
  induction population with
  | zero => simp
  | succ n ih =>
      change amount + (List.replicate n amount).sum = (n + 1) * amount
      rw [ih, Nat.add_mul, Nat.one_mul]
      omega

theorem population_viability_iff_pool_covers_threshold
    (minimumReserve population pool : Nat)
    (positive : 0 < minimumReserve) :
    (∃ reserves, FeasibleAllocation minimumReserve population pool reserves) ↔
      population * minimumReserve ≤ pool := by
  constructor
  · rintro ⟨reserves, hLength, hViable, hPool⟩
    have hCover := reserves_cover_viable_population minimumReserve pool reserves positive hViable hPool
    rw [hLength] at hCover
    exact hCover
  · intro hEnough
    refine ⟨List.replicate population minimumReserve, ?_, ?_, ?_⟩
    · simp
    · intro reserve hReserve
      simp only [List.mem_replicate] at hReserve
      omega
    · have hSum := sum_replicate_nat population minimumReserve
      rw [hSum]
      exact hEnough

/- In a two-context finite experiment, changing only the context mixture can
   change the count of a binary event by no more than the number of contexts
   reassigned. This is the deterministic two-context case of the TV bound. -/
def binaryContextOutcomeCount (scale contextAWeight : Nat)
    (outcomeA outcomeB : Bool) : Nat :=
  (if outcomeA then contextAWeight else 0) +
    (if outcomeB then scale - contextAWeight else 0)

theorem binary_context_shift_bound
    (scale weight1 weight2 : Nat)
    (weight1Bound : weight1 ≤ scale)
    (weight2Bound : weight2 ≤ scale)
    (weightsOrdered : weight2 ≤ weight1)
    (outcomeA outcomeB : Bool) :
    -((weight1 : Int) - (weight2 : Int)) ≤
        (binaryContextOutcomeCount scale weight1 outcomeA outcomeB : Int) -
          (binaryContextOutcomeCount scale weight2 outcomeA outcomeB : Int) ∧
      (binaryContextOutcomeCount scale weight1 outcomeA outcomeB : Int) -
          (binaryContextOutcomeCount scale weight2 outcomeA outcomeB : Int) ≤
        (weight1 : Int) - (weight2 : Int) := by
  cases outcomeA <;> cases outcomeB <;>
    simp [binaryContextOutcomeCount] <;> omega

/- Identification boundary for mechanism design: observing no executed event
   does not distinguish an agent that did not propose the action from an agent
   whose proposed action was blocked by the mechanism. Opening the gate separates
   these two structural explanations. -/
def executeIntent (feasible intended : Bool) : Bool := feasible && intended

def noIntent (_feasible : Bool) : Bool := false

def intendsAction (_feasible : Bool) : Bool := true

def outcomeNoIntent (feasible : Bool) : Bool := executeIntent feasible (noIntent feasible)

def outcomeBlockedIntent (feasible : Bool) : Bool := executeIntent feasible (intendsAction feasible)

theorem no_executed_event_does_not_identify_intention :
    outcomeNoIntent false = outcomeBlockedIntent false := by
  decide

theorem opening_execution_gate_separates_intentions :
    outcomeNoIntent true ≠ outcomeBlockedIntent true := by
  decide

/- Individual success marginals do not identify team success. Two agents each
   succeed in half of the cases under both joint laws, but correlation changes
   the probability that at least one member succeeds. -/
def independentPairOutcomes : List (Bool × Bool) :=
  [(true, true), (true, false), (false, true), (false, false)]

def correlatedPairOutcomes : List (Bool × Bool) :=
  [(true, true), (true, true), (false, false), (false, false)]

def firstSuccessCount (outcomes : List (Bool × Bool)) : Nat :=
  (outcomes.filter (fun outcome => outcome.1)).length

def secondSuccessCount (outcomes : List (Bool × Bool)) : Nat :=
  (outcomes.filter (fun outcome => outcome.2)).length

def anyTeamSuccessCount (outcomes : List (Bool × Bool)) : Nat :=
  (outcomes.filter (fun outcome => outcome.1 || outcome.2)).length

theorem individual_marginals_do_not_identify_team_success_probability :
    firstSuccessCount independentPairOutcomes = 2 ∧
      secondSuccessCount independentPairOutcomes = 2 ∧
      firstSuccessCount correlatedPairOutcomes = 2 ∧
      secondSuccessCount correlatedPairOutcomes = 2 ∧
      anyTeamSuccessCount independentPairOutcomes = 3 ∧
      anyTeamSuccessCount correlatedPairOutcomes = 2 := by
  decide

end AgentMicrofoundations
