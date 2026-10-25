import Std

/-!
One cross-period causal bridge: an implemented opportunity changes verified
resource state; a fixed, empirically testable response rule maps that state to
the next action. The policy is not assumed to maximize utility. The threshold
rule below is a model restriction to test, not a universal axiom about agents.
-/
namespace AgentMicrofoundations.MechanismFeedback

def resourceAfter (resource upkeep computeCost verifiedOutput : Int) : Int :=
  resource - upkeep - computeCost + verifiedOutput

def thresholdResponse (threshold resource : Int) : Bool :=
  decide (threshold ≤ resource)

theorem verified_opportunity_changes_resource_by_net_output
    (resource upkeep taskCost idleCost verifiedOutput : Int) :
    resourceAfter resource upkeep taskCost verifiedOutput -
      resourceAfter resource upkeep idleCost 0 =
        verifiedOutput + idleCost - taskCost := by
  simp [resourceAfter]
  omega

/-- If a mechanism's net resource effect crosses a response boundary, the
    same fixed response rule changes the next-period action. -/
theorem net_opportunity_surplus_crossing_threshold_changes_response
    (threshold baselineResource netSurplus : Int)
    (baselineBelow : baselineResource < threshold)
    (crossesBoundary : threshold ≤ baselineResource + netSurplus) :
    thresholdResponse threshold baselineResource = false ∧
      thresholdResponse threshold (baselineResource + netSurplus) = true := by
  simp [thresholdResponse, baselineBelow, crossesBoundary]

/-- Away from a response boundary, the opportunity's resource effect may be
    economically real while leaving this next action unchanged. -/
theorem same_side_of_threshold_preserves_next_response
    (threshold baselineResource netSurplus : Int)
    (sameSide :
      (baselineResource < threshold ∧
        baselineResource + netSurplus < threshold) ∨
      (threshold ≤ baselineResource ∧
        threshold ≤ baselineResource + netSurplus)) :
    thresholdResponse threshold baselineResource =
      thresholdResponse threshold (baselineResource + netSurplus) := by
  have responseEquivalent : threshold ≤ baselineResource ↔
      threshold ≤ baselineResource + netSurplus := by
    rcases sameSide with ⟨baseBelow, nextBelow⟩ | ⟨baseAbove, nextAbove⟩
    · constructor <;> intro h <;> omega
    · constructor <;> intro h <;> omega
  simp [thresholdResponse, responseEquivalent]

/-- A concrete mechanism comparison: without a task the agent pays idle cost;
    with an executed, verified task it pays recipient compute cost and earns
    verified output. If this net difference crosses the stated response
    threshold, next-period actions differ even though the response rule stays
    fixed. -/
theorem task_assignment_feedback_changes_next_action
    (threshold resource upkeep recipientCost idleCost verifiedOutput : Int)
    (baseBelow : resourceAfter resource upkeep idleCost 0 < threshold)
    (crosses : threshold ≤
      resourceAfter resource upkeep idleCost 0 +
        (verifiedOutput + idleCost - recipientCost)) :
    thresholdResponse threshold (resourceAfter resource upkeep idleCost 0) = false ∧
      thresholdResponse threshold
        (resourceAfter resource upkeep recipientCost verifiedOutput) = true := by
  have gap := verified_opportunity_changes_resource_by_net_output
    resource upkeep recipientCost idleCost verifiedOutput
  have resourceEquality :
      resourceAfter resource upkeep recipientCost verifiedOutput =
        resourceAfter resource upkeep idleCost 0 +
          (verifiedOutput + idleCost - recipientCost) := by omega
  rw [resourceEquality]
  exact net_opportunity_surplus_crossing_threshold_changes_response
    threshold (resourceAfter resource upkeep idleCost 0)
    (verifiedOutput + idleCost - recipientCost)
    baseBelow (by omega)

end AgentMicrofoundations.MechanismFeedback
