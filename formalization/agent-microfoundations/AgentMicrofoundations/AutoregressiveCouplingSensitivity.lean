import AgentMicrofoundations.AutoregressiveResponse
import AgentMicrofoundations.CouplingComparativeStatics

/-!
Quantitative response comparison under context change.

An agent's response law may vary arbitrarily across contexts. A case can
nevertheless obtain a finite sensitivity bound by (i) approximating each
full parser with a common prefix parser and auditing its disagreement mass,
and (ii) coupling the two prefix-output laws. The resulting contrast bound is
conditional on that measured/justified coupling; it adds no rationality,
preference-stability, or cross-agent-independence assumption.
-/
namespace AgentMicrofoundations.AutoregressiveCouplingSensitivity

open AgentMicrofoundations.Ontology
open AgentMicrofoundations.AutoregressiveResponse
open AgentMicrofoundations.CouplingComparativeStatics

/-- Proposal law obtained by parsing a fixed-length prefix of the generated
    trace. -/
def prefixProposalLaw {Context Token Proposal : Type}
    (constitution : AutoregressiveConstitution Context Token Proposal)
    (context : Context) (budget prefixLength : Nat)
    (prefixParser : List Token → Proposal) : FiniteDistribution Proposal :=
  mapDistribution prefixParser
    (mapDistribution (fun trace : BudgetedTokenTrace Token budget =>
      trace.tokens.take prefixLength)
      (generatedTokenTrace constitution.nextToken constitution.stopToken budget
        (constitution.prompt context)))

/-- For two contexts under the same fixed constitution, the proposal-event
    probability contrast is bounded by the two parser-versus-prefix errors and
    the event disagreement mass in any coupling of the two parsed-prefix laws.
    This is the positive, case-computable counterpart to the unrestricted
    cross-context non-identification result: if the full parser is prefix
    stable and the coupled prefix outputs rarely disagree, the response effect
    must be small. -/
theorem autoregressive_context_event_shift_bounded_by_prefix_coupling
    {Context Token Proposal : Type} [DecidableEq Proposal]
    (constitution : AutoregressiveConstitution Context Token Proposal)
    (firstContext secondContext : Context)
    (budget prefixLength : Nat)
    (prefixParser : List Token → Proposal)
    (prefixCoupling : FiniteCoupling
      (prefixProposalLaw constitution firstContext budget prefixLength prefixParser)
      (prefixProposalLaw constitution secondContext budget prefixLength prefixParser))
    (event : Proposal → Bool) :
    (eventMass (proposalLaw constitution firstContext budget) event ≤
      eventMass (proposalLaw constitution secondContext budget) event +
        prefixParserDisagreementMass constitution firstContext budget prefixLength prefixParser +
        coupledEventDisagreement prefixCoupling.joint event event +
        prefixParserDisagreementMass constitution secondContext budget prefixLength prefixParser) ∧
    (eventMass (proposalLaw constitution secondContext budget) event ≤
      eventMass (proposalLaw constitution firstContext budget) event +
        prefixParserDisagreementMass constitution firstContext budget prefixLength prefixParser +
        coupledEventDisagreement prefixCoupling.joint event event +
        prefixParserDisagreementMass constitution secondContext budget prefixLength prefixParser) := by
  let firstPrefix := prefixProposalLaw constitution firstContext budget prefixLength prefixParser
  let secondPrefix := prefixProposalLaw constitution secondContext budget prefixLength prefixParser
  let firstError := prefixParserDisagreementMass constitution firstContext budget prefixLength prefixParser
  let secondError := prefixParserDisagreementMass constitution secondContext budget prefixLength prefixParser
  let couplingError := coupledEventDisagreement prefixCoupling.joint event event
  have firstApprox := proposal_event_within_prefix_parser_disagreement constitution
    firstContext budget prefixLength prefixParser event
  have secondApprox := proposal_event_within_prefix_parser_disagreement constitution
    secondContext budget prefixLength prefixParser event
  have prefixContrast := event_probability_difference_bounded_by_coupling_disagreement
    prefixCoupling event event
  have firstBound : eventMass (proposalLaw constitution firstContext budget) event ≤
      eventMass (proposalLaw constitution secondContext budget) event +
        firstError + couplingError + secondError := by
    have approximateFirst :
        eventMass (proposalLaw constitution firstContext budget) event ≤
          eventMass firstPrefix event + firstError := by
      simpa [firstPrefix, firstError, prefixProposalLaw] using firstApprox.1
    have coupledPrefixes :
        eventMass firstPrefix event ≤ eventMass secondPrefix event + couplingError := by
      simpa [firstPrefix, secondPrefix, couplingError] using prefixContrast.1
    have approximateSecond :
        eventMass secondPrefix event ≤
          eventMass (proposalLaw constitution secondContext budget) event + secondError := by
      simpa [secondPrefix, secondError, prefixProposalLaw] using secondApprox.2
    calc
      eventMass (proposalLaw constitution firstContext budget) event ≤
          eventMass firstPrefix event + firstError := approximateFirst
      _ ≤ (eventMass secondPrefix event + couplingError) + firstError := by
        exact Rat.add_le_add_right.mpr coupledPrefixes
      _ ≤ (eventMass (proposalLaw constitution secondContext budget) event + secondError) +
          couplingError + firstError := by
        have shiftCoupling :
            eventMass secondPrefix event + couplingError ≤
              (eventMass (proposalLaw constitution secondContext budget) event + secondError) +
                couplingError := Rat.add_le_add_right.mpr approximateSecond
        have shiftError :
            (eventMass secondPrefix event + couplingError) + firstError ≤
              ((eventMass (proposalLaw constitution secondContext budget) event + secondError) +
                couplingError) + firstError := Rat.add_le_add_right.mpr shiftCoupling
        simpa [Rat.add_assoc] using shiftError
      _ = eventMass (proposalLaw constitution secondContext budget) event +
          firstError + couplingError + secondError := by ac_rfl
  have secondBound : eventMass (proposalLaw constitution secondContext budget) event ≤
      eventMass (proposalLaw constitution firstContext budget) event +
        firstError + couplingError + secondError := by
    have approximateSecond :
        eventMass (proposalLaw constitution secondContext budget) event ≤
          eventMass secondPrefix event + secondError := by
      simpa [secondPrefix, secondError, prefixProposalLaw] using secondApprox.1
    have coupledPrefixes :
        eventMass secondPrefix event ≤ eventMass firstPrefix event + couplingError := by
      simpa [firstPrefix, secondPrefix, couplingError] using prefixContrast.2
    have approximateFirst :
        eventMass firstPrefix event ≤
          eventMass (proposalLaw constitution firstContext budget) event + firstError := by
      simpa [firstPrefix, firstError, prefixProposalLaw] using firstApprox.2
    calc
      eventMass (proposalLaw constitution secondContext budget) event ≤
          eventMass secondPrefix event + secondError := approximateSecond
      _ ≤ (eventMass firstPrefix event + couplingError) + secondError := by
        exact Rat.add_le_add_right.mpr coupledPrefixes
      _ ≤ (eventMass (proposalLaw constitution firstContext budget) event + firstError) +
          couplingError + secondError := by
        have shiftCoupling :
            eventMass firstPrefix event + couplingError ≤
              (eventMass (proposalLaw constitution firstContext budget) event + firstError) +
                couplingError := Rat.add_le_add_right.mpr approximateFirst
        have shiftError :
            (eventMass firstPrefix event + couplingError) + secondError ≤
              ((eventMass (proposalLaw constitution firstContext budget) event + firstError) +
                couplingError) + secondError := Rat.add_le_add_right.mpr shiftCoupling
        simpa [Rat.add_assoc] using shiftError
      _ = eventMass (proposalLaw constitution firstContext budget) event +
          firstError + couplingError + secondError := by ac_rfl
  exact ⟨by simpa [firstError, couplingError, secondError] using firstBound,
    by simpa [firstError, couplingError, secondError] using secondBound⟩

end AgentMicrofoundations.AutoregressiveCouplingSensitivity
