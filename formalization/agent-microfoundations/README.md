# Agent Microfoundations — Lean formalization

This directory is a self-contained Lean 4/Lake module for the agent-native economic theory developed alongside the WWW 2027 submission.

## Build and audit

```sh
lake build
lake env lean Audit.lean
```

The source was built with Lean 4.35.0. `Audit.lean` prints the axiom dependencies for the named results. The project declares no custom `axiom`, `sorry`, or `admit`; results may use Lean's standard foundations (`propext`, `Classical.choice`, and `Quot.sound`). The verification manifest records hashes for the Lean sources and environment files.

## Structure

- `AgentMicrofoundations/` — definitions, propositions, proofs, and case-study formalizations.
- `AgentMicrofoundations.lean` — aggregate import.
- `Audit.lean` — axiom-dependency audit for the exported theorem set.
- `THEORY_INDEX.md` — map from the formal results to the theory.
- `verification/manifest.json` — source hashes and verification environment.

## Scope

The Lean proofs establish mathematical implications under their explicit assumptions. They do not by themselves establish that a particular empirical case satisfies those assumptions, nor do they prove empirical causal claims. Case-data validation and analysis remain separate artifacts in the paper project.
