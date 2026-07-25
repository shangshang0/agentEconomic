# Strict Direct Control Protocol

This control estimates task-solving performance after removing Authority World governance, scarcity, survival, and social interaction while holding the task-solving interface as close as practical to the production Real-72 run.

## Paired constants

- Model and gateway: the same gateway deployment and default model profile as the production run.
- Tasks: all 72 records from `original-ctf-real72-ranked.json`, grouped easy, medium, then hard, preserving manifest order within each tier.
- Runtime: `authority-world-task:real72-v4`, 512 MiB, one CPU, 96 PIDs, no external network, 300-second command timeout, and 32 KiB command output limit.
- Submission: exactly one final flag; correct or incorrect immediately closes the task.
- Context: at most 36 recent semantic events and 12,000 serialized characters, matching `agent/runner_v2.py`.
- Work budget: 720 real seconds per task, matching the production daily work window from second 60 through second 780.
- Compute scheduling: one task and one command execute at a time. The strict control does not run concurrently with the idealized direct baseline.
- Failure accounting: provider/runtime failures are technical failures and are reported separately from wrong flags, no-submission timeouts, and successful solves.

## Removed mechanisms

- No energy costs, basal drain, death, transfers, elections, allocation decisions, messages, or sleep decisions.
- Every task is assigned to the sole solver automatically.
- No competition between agents for a task or its reward.

## Interpretation

This is a mechanism-ablated control, not a claim that the prompts are textually identical. The production system prompt necessarily describes the mechanisms being removed. Compare paired task outcomes and resource use; keep the existing 18-task, 2,700-second direct run only as an idealized upper-bound condition.
