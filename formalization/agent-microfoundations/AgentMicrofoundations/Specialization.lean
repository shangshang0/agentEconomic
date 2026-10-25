import Std

/-!
Sufficient conditions for persistent role differentiation without preference
or policy drift. A fixed policy maps context to a role; experience changes
context. If each role's context region is forward invariant, agents placed in
different regions keep choosing different roles.

The abstract theorem states the empirical conditions that must be checked.
The integer example is only a transparent instance of reinforcing context,
not a claim that real agents follow this update rule.
-/
namespace AgentMicrofoundations.Specialization

def evolve {Context : Type} (update : Context → Context) : Nat → Context → Context
  | 0, context => context
  | n + 1, context => evolve update n (update context)

theorem role_persists_in_forward_invariant_region
    {Context Role : Type}
    (update : Context → Context)
    (choose : Context → Role)
    (region : Context → Prop)
    (role : Role)
    (closed : ∀ context, region context → region (update context))
    (choosesRole : ∀ context, region context → choose context = role)
    (context : Context)
    (hcontext : region context) :
    ∀ n, choose (evolve update n context) = role := by
  intro n
  induction n generalizing context hcontext with
  | zero => exact choosesRole context hcontext
  | succ n ih =>
      simpa [evolve] using ih (update context) (closed context hcontext)

theorem two_invariant_regions_imply_persistent_role_split
    {Context Role : Type}
    (update : Context → Context)
    (choose : Context → Role)
    (regionA regionB : Context → Prop)
    (roleA roleB : Role)
    (roleDistinct : roleA ≠ roleB)
    (closedA : ∀ context, regionA context → regionA (update context))
    (closedB : ∀ context, regionB context → regionB (update context))
    (choosesA : ∀ context, regionA context → choose context = roleA)
    (choosesB : ∀ context, regionB context → choose context = roleB)
    (contextA contextB : Context)
    (startsA : regionA contextA)
    (startsB : regionB contextB) :
    ∀ n, choose (evolve update n contextA) ≠ choose (evolve update n contextB) := by
  intro n
  have persistA := role_persists_in_forward_invariant_region
    update choose regionA roleA closedA choosesA contextA startsA n
  have persistB := role_persists_in_forward_invariant_region
    update choose regionB roleB closedB choosesB contextB startsB n
  rw [persistA, persistB]
  exact roleDistinct

/- A minimal reinforcement dynamic: the same fixed response rule selects role A
   at nonnegative context and role B at negative context. Doing the selected
   role adds one unit of corresponding experience to context. -/
def choosesA (context : Int) : Bool := decide (0 ≤ context)

def reinforcedUpdate (context : Int) : Int :=
  if choosesA context then context + 1 else context - 1

def reinforcedPath : Nat → Int → Int
  | 0, context => context
  | n + 1, context => reinforcedPath n (reinforcedUpdate context)

def firstExposure (baseline : Int) (assignedA : Bool) : Int :=
  if assignedA then baseline + 1 else baseline - 1

theorem positive_context_stays_positive (context : Int) (positive : 0 < context) :
    ∀ n, 0 < reinforcedPath n context := by
  intro n
  induction n generalizing context positive with
  | zero => simpa [reinforcedPath] using positive
  | succ n ih =>
      simpa [reinforcedPath] using ih (reinforcedUpdate context) (by
      by_cases h : 0 ≤ context
      · simp [reinforcedUpdate, choosesA, h]
        omega
      · simp [reinforcedUpdate, choosesA, h]
        omega)

theorem negative_context_stays_negative (context : Int) (negative : context < 0) :
    ∀ n, reinforcedPath n context < 0 := by
  intro n
  induction n generalizing context negative with
  | zero => simpa [reinforcedPath] using negative
  | succ n ih =>
      simpa [reinforcedPath] using ih (reinforcedUpdate context) (by
      by_cases h : 0 ≤ context
      · simp [reinforcedUpdate, choosesA, h]
        omega
      · simp [reinforcedUpdate, choosesA, h]
        omega)

theorem opposite_first_exposures_create_persistent_role_split :
    ∀ n, choosesA (reinforcedPath n (firstExposure 0 true)) = true ∧
      choosesA (reinforcedPath n (firstExposure 0 false)) = false := by
  intro n
  constructor
  · have h := positive_context_stays_positive 1 (by decide) n
    change decide (0 ≤ reinforcedPath n 1) = true
    exact decide_eq_true (by omega)
  · have h := negative_context_stays_negative (-1) (by decide) n
    change decide (0 ≤ reinforcedPath n (-1)) = false
    exact decide_eq_false (by omega)

end AgentMicrofoundations.Specialization
