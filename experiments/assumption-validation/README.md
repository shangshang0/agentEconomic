# Case assumption validation experiments

Reproducible zero-API checks against archived traces and the exact Authority World v2 backend/Lean mappings. The audits make no model/API calls and do not infer universal behavior laws.

- `run_all.py` runs the CTF 46-field design coverage audit and consolidated assumption audit (which runs clock and election checks).
- The assumption register records 12 restrictions with explicit tests, rejection rules, failure actions, and forecast eligibility.
- Clock audit covers 8 checked-in `agent_econ_*.json` configurations; election audit covers seeded no-candidate, all-candidate, missing-ballot, plurality, and tie branches.
- Case checks include ledger/event joins, input reconstruction summary, alive-path persistence across 24 worlds, and the frozen execution replay pilot.

Run `python3 run_all.py` from this directory (Python 3.10+, standard library only). Outputs are written beneath `case_bundle/theory_v3/`; the bundle preserves original project-relative paths. Large full-context indexes are not duplicated here; compact case tables and hashed reconstruction summary are included.

These checks validate finite-case restrictions and implementation mappings. Current CTF has a zero death threshold, no accepted frozen response kernel, and no point forecast from behavioral law; those restrictions remain explicitly excluded.
