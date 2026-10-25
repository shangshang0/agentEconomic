import AgentMicrofoundations.Ontology
import AgentMicrofoundations.AutoregressiveResponse
import AgentMicrofoundations.TokenAccounting
import AgentMicrofoundations.Accounting
import AgentMicrofoundations.ComputationalEconomy
import AgentMicrofoundations.FiniteDynamics
import AgentMicrofoundations.CausalInterface
import AgentMicrofoundations.AllocationIdentification
import AgentMicrofoundations.AllocationFeedback
import AgentMicrofoundations.ResourceThresholdPath
import AgentMicrofoundations.ResourceSurvivalBound

/-!
Curated theory-core import surface. This file deliberately excludes generic
two-event coupling tools, experiment protocols, pilot data, and case-specific
backend mappings. It includes the general response non-identification result
because that result marks a foundational limit on what structure alone can
predict. It introduces no assumptions of rational choice, stable preferences,
independence, anonymity, or cross-context invariance.

The core is a modeling language plus conditional derivations, not a closed
behavioral theory. Model kernels remain unrestricted unless a named theorem's
explicit premises constrain them. See `../FOUNDATION_BOUNDARY.md` for the
primitive commitments and the status of each premise.
-/
