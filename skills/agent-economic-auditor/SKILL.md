---
name: agent-economic-auditor
description: Audit, query, reproduce, or interpret Agent Economic multi-agent world evidence, including public release manifests, run provenance, event/dialogue traces, evidence-tier eligibility, recovered or failed worlds, and paper claim/data consistency. Use when working with this repository's worlds.jsonl, public-data release assets, run IDs, gateway/audit JSONL, watchdog amendments, registered world-level analysis, or experimental-result claims.
---

# Agent Economic Auditor

Use the repository's executable gates; do not infer evidence eligibility from
folder names or narrative descriptions.

## Locate the repository

Use `$AGENT_ECONOMIC_REPO` when set. Otherwise locate a checkout containing
both `data/catalog/worlds.jsonl` and `scripts/audit_catalog.py`. Read
[the public data schema](references/data-schema.md) before querying traces.

## Choose the workflow

- For a run ID or result question, first read its single catalog row, then its
  registry/state/evidence files. Report tier, eligibility, recovery status,
  provider, condition, seed, and provenance before interpreting outcomes.
- For release integrity, run
  `skills/agent-economic-auditor/scripts/verify_evidence.py REPO`; then inspect
  any exact path/line/rule failures. Never display suspected credential values.
- For dialogue or event questions, query the redacted public gateway, agent
  audit, and event JSONL. Cite run ID, relative file, line/event sequence, day,
  actor, and redaction status. Do not present reference-tier dialogue as
  confirmatory evidence.
- For paper reproduction, download all cataloged release parts, run
  `make reproduce`, then `make paper` and `make audit`. Compare generated
  claims with committed tables/macros and the dated results memo.

## Enforce scientific boundaries

Read [the audit rules](references/audit-rules.md). The experimental unit is a
world. Never treat messages, agents, task calls, or event records as
independent experimental replicates. Keep confirmatory, mechanism, discovery,
recovered, and reference evidence visibly separate. A technical-failed,
contaminated, infrastructure-invalid, partial, or uncommitted-recovery world
may explain a failure mode but cannot silently enter a registered estimate.

When a world has committed recovery amendments, validate each amendment hash
and disclose it. Run both the registered inclusion and the frozen recovered-
world sensitivity; do not choose between them based on effect direction.

## Report an auditable answer

Separate these categories:

1. Quantitative registered result: world dots, estimand, pairing/blocking,
   uncertainty, exact test, and frozen robustness results.
2. Manipulation check: operational/symbolic treatment realization and trace
   evidence, without upgrading it to an outcome.
3. Exploratory evidence: provider strata, qualitative dialogue, failed-world
   lessons, or unregistered semantic summaries.

For every numeric claim, include the analysis artifact and run IDs needed to
recompute it. State missing data or unavailable release parts explicitly.
