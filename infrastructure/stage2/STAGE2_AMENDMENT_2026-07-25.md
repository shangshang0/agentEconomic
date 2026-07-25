# Minimal confirmatory Stage 2 balanced-block amendment

Frozen at 2026-07-25T05:11:12+08:00, before any Stage 2 world was launched or any Stage 2 outcome existed.

## Why Stage 2 is being run

Stage 1 contains two independent worlds in each I1/I3 by GPT/DeepSeek cell. The registered world-level economic-differentiation AUC contrast is positive within both providers, leave-one-world-out stable, and has a blocked bootstrap 95% interval of `[+0.008,+0.084]`, but the prespecified exact provider-blocked permutation test is `p=0.167`, above the frozen `p<=0.025` success threshold. With two worlds per cell, the smallest attainable two-sided provider-blocked permutation value is `2/36=0.0556`. The frozen stopping policy therefore calls for one complete balanced block, not selective sampling by observed cell direction.

Canonical policy: `/data/authoritylab/minimal-confirmatory-v1/STOPPING_POLICY.md`.

## Frozen Stage 2 block

| Cell | Provider/model | Seed | Config | Config SHA256 | Protocol SHA256 |
|---|---|---:|---|---|---|
| I1--GPT | `gpt55` | 2026074003 | `config/agent_econ_i1_elected_discretion_human.json` | `7958fef21db8834616318d544f2d260403276aba0795eef5022e4d322b004c8b` | `b8bc225495dcdc0650af0a902004a0a5c9141e678ce2131593a969c3ab0343d4` |
| I3--GPT | `gpt55` | 2026074203 | `config/agent_econ_i3_elected_backend_random_human.json` | `c534d446398c8271733b3ad97b92585c57d7a8f0fe7464faf4a4db03da6ef9dc` | `97423ccd39b62697d17a5ac5171df6aef00fedcfb74011d13653d7b19e8f2025` |
| I1--DeepSeek | `deepseek_v4_pro` | 2026074103 | `config/agent_econ_i1_elected_discretion_human.json` | `7958fef21db8834616318d544f2d260403276aba0795eef5022e4d322b004c8b` | `fe4052f3bedddb4394763b2353179c17f4b76385c1a77825d1c5dbc96711319d` |
| I3--DeepSeek | `deepseek_v4_pro` | 2026074303 | `config/agent_econ_i3_elected_backend_random_human.json` | `c534d446398c8271733b3ad97b92585c57d7a8f0fe7464faf4a4db03da6ef9dc` | `9111bd14b1f202ab18a8205ac1b2dd3465f44d8eea336fabd9bf66548e28c51f` |

All four worlds start concurrently after dry-run, provider preflight, source-hash, isolation, and capacity gates pass. Each has one independent filesystem root, Compose project/network, durable state tree, result tree, runner session, watchdog session, and recovery trail. No world is chained seed-to-seed.

Frozen runner SHA256 is `35bed8e494686454f7f63e8494642357d735721d904711c1f684e4c420467ce1`. Relative to the Stage 1 runner, it (1) recognizes exactly the frozen Stage 2 schema as a one-additional-world balanced block while retaining the initial-batch minimum of two, and (2) removes the runner's unaudited live-stack replacement after three failed backend health probes. After start, the runner observes; the fail-closed watchdog and audited clock-adjusting supervisor exclusively own recovery.

Provider environment provenance is frozen to the Stage 1 files without recording credentials: GPT `.env.gpt55` SHA256 `ac3c692c9735be2bd0ed17db738f4055d1007502faaf4a76fa06f129f6a57e23`; DeepSeek `.env.deepseek` SHA256 `d82ae626e005a4ab50f559416a28f30d271d2dd2a5ba42839dc5ecf4292a0bfa`.

## Frozen runtime and evidence rules

- Six Agents, 900 real seconds per world day, maximum 25 world days, and the Stage 1 task schedule/resources remain unchanged.
- A world is usable only after `terminal_status=complete`, removal of `agent-economics-active-run.json`, runner/watchdog exit, Compose count zero, and verified final evidence archive.
- Provider errors, watchdog trips, pauses, restarts, clock shifts, and recovery amendments are retained and disclosed. Recovery resumes the same run from durable state; it never creates a replacement result chosen by direction.
- No Stage 2 endpoint is inspected or analyzed until all four cells reach terminal evidence disposition. Infrastructure monitoring may inspect only operational health and progress fields needed to keep the worlds safe.
- A technical incident does not authorize selective resampling. The frozen recovery/exclusion policy applies, with leave-recovered-worlds-out sensitivity.

## Frozen reanalysis

After this whole block is terminal, combine Stage 1 and Stage 2 for three worlds per cell. Recompute the same world-level economic-differentiation AUC and provider-blocked I1-minus-I3 contrast, show all world dots, provider-specific effects, leave-one-world-out, blocked bootstrap interval, and the exact two-sided provider-blocked permutation test. The success gate remains: same effect direction in both providers, leave-one-world-out stability, pooled blocked 95% interval excluding zero, and exact blocked permutation `p<=0.025`. Report the staged interim look. Message-level observations are not independent replicates.

No Stage 3 launch is implied by this amendment. If Stage 2 does not meet the frozen gate, any decision about the final economical block (four worlds per cell) occurs only after the full outcome-blind Stage 2 block and a written evidence-gap audit.
