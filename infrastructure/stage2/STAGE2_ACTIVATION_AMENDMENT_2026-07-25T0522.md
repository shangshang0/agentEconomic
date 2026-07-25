# Stage 2 pre-outcome Compose-isolation activation amendment

Recorded at 2026-07-25T05:22:15+08:00. No Stage 2 active marker, run ID, durable world state, or experimental event existed when this amendment was made.

The first simultaneous launcher invocation at 05:19:59 passed all four provider probes but all four launchers exited before backend startup. The copied Stage 1 Compose files contained fixed top-level project names, so independent filesystem roots still attempted to claim the same Docker project. No world-control start request was accepted and no scientific outcome was generated. The failed launcher and watchdog logs are retained under `/data/authoritylab/minimal-confirmatory-stage2-v1/logs`.

Before retry, only the top-level Compose `name:` was changed in each new Stage 2 root. Service definitions, images/build contexts, networks, volumes, environment, resource limits, world config, runner, and protocol remain otherwise unchanged:

| Cell | Unique Compose project | Compose SHA256 |
|---|---|---|
| I1--GPT | `al-minconf2-i1-gpt-4003` | `3fbcc07527d706cc07d4547ee6458874961b6ffa29d47be926cf447b5a3ee846` |
| I3--GPT | `al-minconf2-i3-gpt-4203` | `940a86461aa0d00d3bc81ed30a81de017867cdb389d49feb7bdf1a95b2c0a0f6` |
| I1--DeepSeek | `al-minconf2-i1-ds-4103` | `8c72b4882e1bff681dde4cac6f5b278222a6cfd4a5b68477cf8250587b6282a0` |
| I3--DeepSeek | `al-minconf2-i3-ds-4303` | `182311df749d235a70d938b5cbe2172307ec10ae6ed4b30c5b603dbb608edacd` |

This is an infrastructure isolation correction made without access to results. The four frozen cells, seeds, configs, providers, endpoint, stopping rule, and full-block analysis remain unchanged.
