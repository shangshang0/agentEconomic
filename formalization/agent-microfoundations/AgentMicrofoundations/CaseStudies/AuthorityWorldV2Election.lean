import AgentMicrofoundations.CaseStudies.AuthorityWorldV2Clock

/-!
Exact execution semantics for Authority World v2's next-day office selection.

The module takes the recorded candidate and explicit-vote profile as inputs.
It does not assume how an agent decides to run or vote. Missing ballots and
plurality ties are resolved by the seed-conditioned choice functions supplied
by the backend. Once these choices are fixed, the institution is a finite,
exactly computable mapping.
-/
namespace AgentMicrofoundations.CaseStudies.AuthorityWorldV2Election

variable {Agent : Type} [DecidableEq Agent]

structure ElectionInput (Agent : Type) where
  alive : List Agent
  candidates : List Agent
  explicitVotes : List (Agent × Agent)
  /-- Runtime's seed-conditioned completion of an eligible missing ballot. -/
  missingVoteChoice : Agent → Agent
  /-- Runtime's seed-conditioned branch for no candidates. -/
  noCandidateChoice : Option Agent
  /-- Runtime's seed-conditioned branch when every living agent is a candidate. -/
  allCandidateChoice : Option Agent
  /-- Runtime's seed-conditioned tie breaker for plurality leaders. -/
  tieBreak : List Agent → Option Agent

def missingEligibleVoters (input : ElectionInput Agent) : List Agent :=
  input.alive.filter fun voter =>
    !(input.candidates.contains voter) &&
      !(input.explicitVotes.map Prod.fst |>.contains voter)

def completedVotes (input : ElectionInput Agent) : List (Agent × Agent) :=
  input.explicitVotes ++
    (missingEligibleVoters input).map fun voter =>
      (voter, input.missingVoteChoice voter)

def tally (input : ElectionInput Agent) (candidate : Agent) : Nat :=
  ((completedVotes input).map Prod.snd).count candidate

def maximumTally (input : ElectionInput Agent) : Nat :=
  input.candidates.foldl (fun high candidate => max high (tally input candidate)) 0

def pluralityLeaders (input : ElectionInput Agent) : List Agent :=
  input.candidates.filter fun candidate => tally input candidate == maximumTally input

/-- The exact backend branch structure, with seeded hash choices abstracted as
    explicit functions. Election behavior itself is not inserted as an axiom. -/
def nextOfficeHolder (input : ElectionInput Agent) : Option Agent :=
  if input.candidates.isEmpty then input.noCandidateChoice
  else if input.candidates.length == input.alive.length then input.allCandidateChoice
  else input.tieBreak (pluralityLeaders input)

def ChoiceRespectsMenu (choose : List Agent → Option Agent) : Prop :=
  ∀ menu winner, choose menu = some winner → winner ∈ menu

theorem plurality_output_is_a_candidate
    (input : ElectionInput Agent)
    (tieChoiceValid : ChoiceRespectsMenu input.tieBreak)
    (winner : Agent)
    (nonemptyCandidates : input.candidates ≠ [])
    (notAllCandidates : input.candidates.length ≠ input.alive.length)
    (selected : nextOfficeHolder input = some winner) :
    winner ∈ input.candidates := by
  unfold nextOfficeHolder at selected
  simp [nonemptyCandidates, notAllCandidates] at selected
  have inLeaders := tieChoiceValid (pluralityLeaders input) winner selected
  unfold pluralityLeaders at inLeaders
  exact (List.mem_filter.mp inLeaders).1

theorem no_candidate_branch_is_seed_choice
    (input : ElectionInput Agent)
    (noCandidates : input.candidates = []) :
    nextOfficeHolder input = input.noCandidateChoice := by
  simp [nextOfficeHolder, noCandidates]

theorem all_candidates_branch_is_seed_choice
    (input : ElectionInput Agent)
    (candidatesNonempty : input.candidates ≠ [])
    (allRun : input.candidates.length = input.alive.length) :
    nextOfficeHolder input = input.allCandidateChoice := by
  simp [nextOfficeHolder, candidatesNonempty, allRun]

/-- A concrete four-agent calculation: one explicit vote, one missing eligible
    ballot imputed to candidate 1, and candidate 0 wins the plurality 1–1 tie
    only when the supplied seed tie-breaker selects candidate 0. This example
    makes the dependency on the seed choice visible instead of assuming it away. -/
def fourAgentTieInput : ElectionInput Nat where
  alive := [0, 1, 2, 3]
  candidates := [0, 1]
  explicitVotes := [(2, 0)]
  missingVoteChoice := fun _ => 1
  noCandidateChoice := some 0
  allCandidateChoice := some 0
  tieBreak := fun leaders => if leaders == [0, 1] then some 0 else leaders.head?

example : completedVotes fourAgentTieInput = [(2, 0), (3, 1)] := by
  rfl

example : tally fourAgentTieInput 0 = 1 ∧ tally fourAgentTieInput 1 = 1 := by
  decide

example : nextOfficeHolder fourAgentTieInput = some 0 := by
  decide

end AgentMicrofoundations.CaseStudies.AuthorityWorldV2Election
