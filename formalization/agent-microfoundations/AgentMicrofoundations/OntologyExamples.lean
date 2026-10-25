import AgentMicrofoundations.Ontology

/-!
Small countermodels clarify the ontology predicates: a resource variable can
change a menu across mathematically possible states while no transition in a
given model-mechanism pair ever changes it.
-/
namespace AgentMicrofoundations.OntologyExamples

open AgentMicrofoundations.Ontology

def staticOnlyResourceModel :
    AgentEconomyModel Unit Unit Bool Unit Unit Unit Bool Bool Unit where
  observe := fun _ _ _ => ()
  opportunityMenu := fun _ state _ => if state.resources then [true] else []
  individualResponse := fun _ _ _ _ _ _ => pureDistribution false
  jointResponse := fun _ _ _ _ _ => pureDistribution (fun _ => false)
  responseMarginalsAgree := by
    intro agent condition states observations institutionalSignals menus action
    simp [eventMass, pureDistribution]
  feasibleExecution := fun _ _ _ => True
  jointProduction := fun _ _ _ _ => pureDistribution (fun _ => none)
  resourceAfter := fun _ state _ _ _ => state.resources
  internalStateAfter := fun _ _ _ _ _ _ => ()
  continues := fun _ _ => True

def staticOnlyResourceMechanism : MechanismRule Unit Unit Bool Unit Unit Unit Bool Bool Unit where
  institutionalSignal := fun _ _ _ => ()
  execute := fun _ _ _ => pureDistribution (fun _ => none)

/-- Static resource relevance alone does not imply kernel-supported feedback.
    Here the menu differs between two possible resource values, but the
    resource transition is the identity, so no execution/production event can
    change the menu through the ledger. -/
theorem static_resource_relevance_does_not_imply_kernel_supported_feedback :
    ResourceRelevant staticOnlyResourceModel ∧
      ¬ KernelSupportedResourceFeedback staticOnlyResourceModel
        staticOnlyResourceMechanism := by
  constructor
  · refine ⟨(), (), (), true, false, ?_⟩
    intro sameMenus
    have impossible := (sameMenus true).mp (by simp [staticOnlyResourceModel])
    simp [staticOnlyResourceModel] at impossible
  · intro feedback
    rcases feedback with
      ⟨condition, states, proposals, execution, production, agent,
        _proposalSupported, _executionSupported, _productionSupported, menusChange⟩
    have menusSame : sameOpportunitySet
        (staticOnlyResourceModel.opportunityMenu agent (states agent) condition)
        (staticOnlyResourceModel.opportunityMenu agent
          (resourceOnlyUpdatedState staticOnlyResourceModel agent (states agent) proposals
            execution production) condition) := by
      intro opportunity
      simp [staticOnlyResourceModel, resourceOnlyUpdatedState]
    exact menusChange menusSame

def lowResourceState : StateProfile Unit Unit Bool :=
  fun _ => ⟨(), false⟩

def highResourceState : StateProfile Unit Unit Bool :=
  fun _ => ⟨(), true⟩

/-- Resource relevance changes the feasible menu, but does not force an agent
    to change its proposal law. This model presents the menu to the response
    interface while its fixed response kernel ignores that input. Therefore
    the opportunity channel is real, yet resources alone imply no behavioral
    comparative static without an independently testable response restriction.
    This countermodel blocks rationality or resource-sensitive preference from
    entering through an unstated assumption. -/
theorem resource_relevance_does_not_imply_resource_sensitive_proposals :
    ResourceRelevant staticOnlyResourceModel ∧
      proposalDistribution staticOnlyResourceModel staticOnlyResourceMechanism ()
        lowResourceState =
      proposalDistribution staticOnlyResourceModel staticOnlyResourceMechanism ()
        highResourceState := by
  constructor
  · exact static_resource_relevance_does_not_imply_kernel_supported_feedback.1
  · simp [proposalDistribution, staticOnlyResourceModel,
      staticOnlyResourceMechanism, lowResourceState, highResourceState]

end AgentMicrofoundations.OntologyExamples
