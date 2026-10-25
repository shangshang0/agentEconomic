# Formalization and case validation

- [`agent-microfoundations/`](agent-microfoundations/) contains the latest Lean 4 theory, case formalizations, three axiom audits, source manifest, and successful Miao Linux verification log `lake_check_miao_20261025_140451.log`.
- [`../experiments/assumption-validation/`](../experiments/assumption-validation/) contains reproducible zero-API assumption and case-mapping experiments.

Lean 4.35.0 `lake build`, explicit auxiliary-module builds, Linux `lake check`, and theory, methods, and research-target audits passed on 2026-10-25. `Audit.lean` now imports and audits `ResourceOpportunityCascade`.
