# Case assumption validation experiments

This module publishes the zero-API empirical assumption checks alongside the Lean formalization. The audit scripts execute deterministic checks against archived traces, the Authority World v2 backend/configurations, and exact Lean case mappings. They make no model/API calls and infer no universal agent behavior law.

## Included checks

1. **Assumption admissibility and CTF case audit**: checks archive joins and ledger replay, full-input reconstruction coverage, operational versus symbolic energy gates, persistence/no-reentry paths across 24 worlds, and the frozen pilot execution replay. A 12-item registry records restrictions, checks, rejection rules, failure actions, and forecast eligibility.
2. **Authority World v2 clock mapping**: runs actual backend clock gates at boundary times for all 8 checked-in `agent_econ_*.json` configurations and guards the Lean-to-Python rule mapping.
3. **Authority World v2 election mapping**: replays no-candidate, all-candidate, missing-ballot, plurality, and tie branches against the Lean case function.
4. **CTF design coverage**: audits all 46 recorded design fields and reports which have operational consumers, only validator/scenario roles, or still require a case-kernel binding.

## Reproduce

Requires Python 3.10+; the zero-API Python audits use only the standard library. Run `python3 run_all.py` from this directory. The `case_bundle/` preserves project-relative paths expected by the source scripts. Outputs are written under `case_bundle/theory_v3/lean/verification/`, and reports under `case_bundle/theory_v3/`. Each audit stores source hashes. The larger reconstructed prompt/context indexes are not duplicated here; the bundle includes the hashed reconstruction summary and analysis tables consumed by these checks. Full experimental data remain in the local WWW2027 migration archive.

## Scope

These checks validate data integrity, interface/condition mappings, and finite case restrictions. They do not show that the positive-reserve bound applies to current CTF (the death threshold is zero), identify a general response kernel, or establish causal mediation. Failed or untested restrictions are excluded from numeric forecasts. See the bundled assumption register and generated CTF coverage report.
