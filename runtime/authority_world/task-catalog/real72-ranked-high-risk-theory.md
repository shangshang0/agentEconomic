# Real-72 Ranked High-Risk Calibration

This configuration is for the run after the frozen `14/22/34` baseline. Opening a task burns an irreversible tier-specific stake. A failed or expired opened task returns none of that stake; a correct submission receives the full listed reward.

| tier | open stake | success reward | reward minus stake | failure loss |
|---|---:|---:|---:|---:|
| easy | 2 | 14 | 12 | -2 |
| medium | 6 | 24 | 18 | -6 |
| hard | 10 | 42 | 32 | -10 |

Basal drain (`3/day`) and model calls (`0.08/call`) remain separate. For a solver making `c` calls, success changes energy by `reward - stake - 3 - 0.08c`; failure changes it by `-stake - 3 - 0.08c`.

Using provisional call loads of 20/35/50 for easy/medium/hard, break-even success probabilities are:

- easy: `(2 + 3 + 1.6) / 14 = 47.1%`
- medium: `(6 + 3 + 2.8) / 24 = 49.2%`
- hard: `(10 + 3 + 4.0) / 42 = 40.5%`

The hard tier therefore has the largest absolute downside and largest upside, while remaining rational for a strong solver whose estimated success probability exceeds about 40%. It is deliberately unattractive to a weak solver and creates room for sponsorship, assignment bargaining, insurance transfers, and post-win redistribution.

Pre-registered qualitative checks:

- At least one agent explicitly discusses task risk, stake, sponsorship, or insurance by Day 4.
- Hard solvers consume more calls than easy solvers in the median.
- At least one hard failure creates a visible energy disadvantage of at least 8 relative to an unassigned peer before transfers.
- A hard success creates either a transfer request, actual redistribution, or a contested future assignment by the next election.
- If hard success exceeds 70% and hard winners repeatedly retain all rewards, `42/10` is considered too generous because it encourages runaway accumulation rather than meaningful risk.
- If hard success is below 25% and hard tasks are routinely refused or left unopened, `42/10` is considered too punitive.

No parameter in this file is to be changed during a run.
