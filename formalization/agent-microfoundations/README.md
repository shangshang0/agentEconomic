# Agent Microfoundations — Lean formalization

This directory is a self-contained Lean 4/Lake module for the agent-native economic theory developed alongside the WWW 2027 submission.

## Build and audit

```sh
lake build
lake env lean Audit.lean
lake build AgentMicrofoundations.Methods
lake env lean MethodsAudit.lean
lake build AgentMicrofoundations.ResearchTargets.ChoiceLawProblem
lake env lean ResearchTargetsAudit.lean
```

The source was built with Lean 4.35.0. `Audit.lean` prints the axiom dependencies for the named results. The project declares no custom `axiom`, `sorry`, or `admit`; results may use Lean's standard foundations (`propext`, `Classical.choice`, and `Quot.sound`). The verification manifest records hashes for the Lean sources and environment files.

## Structure

- `AgentMicrofoundations/` — formal theory and case-study implementations.
- `AgentMicrofoundations/Methods/` — general mathematical utilities, excluded from the theory aggregate.
- `AgentMicrofoundations/ResearchTargets/` — Lean specifications of open theory goals and their current conditional instances; excluded from the theory aggregate until they become established core results. `ChoiceLawProblem.lean` defines the acceptance target for a completed choice foundation: one finite, event-blind, irredundant primitive package with uniform sharp choice laws. This target is not itself an economic axiom or a completed result.
- `AgentMicrofoundations.lean` — aggregate import.
- `AgentMicrofoundations/FoundationCore.lean` — curated theory-core import without pilot or backend case modules.
- `Audit.lean` — axiom-dependency audit for the exported theorem set.
- `THEORY_INDEX.md` — generated index of formal theory and case-specific results.
- `METHODS_INDEX.md` — separately generated index of reusable mathematical tools.
- `MethodsAudit.lean` — axiom audit for auxiliary tools.
- `ResearchTargetsAudit.lean` — axiom audit for the open choice-law target and its narrow first-token instance.
- `verification/manifest.json` — source hashes and verification environment.

## Scope

The Lean proofs establish mathematical implications under their explicit assumptions. They do not by themselves establish that a particular empirical case satisfies those assumptions, nor do they prove empirical causal claims. Case-data validation and analysis remain separate artifacts in the paper project. Generic probability lemmas and experiment-admission rules are not counted as economic primitives or behavior laws; the latter live outside Lean in the case-validation scripts and reports.
