# Real-72 ranked run: pre-registered numerical theory

## Energy accounting

For agent `i` over one day:

`ΔE_i = task rewards + transfers received - transfers sent - 3 - 0.08 × model calls`.

The previous invalid run used 164–189 model calls across all agents on normal work days. Holding behavior fixed, the new daily social cost is therefore approximately:

- basal: `6 × 3 = 18`
- cognition: `0.08 × [164, 189] = [13.12, 15.12]`
- total: `[31.12, 33.12]` energy per day

One hard solve pays 34, while one easy plus one medium solve pays 36. Thus the society reaches approximate daily energy balance with either outcome. Zero or only one easy solve remains net-negative, preserving scarcity.

For an assigned solver using 26 calls, daily cost is `3 + 0.08 × 26 = 5.08`. Without rewards or transfers, 38 initial energy lasts about 7.5 active work days. An unassigned agent using 6 calls per day costs 3.48 and lasts about 10.9 days. Strong agents therefore need repeated production or political transfers; passive survival is impossible.

## Monte Carlo assumptions

The pre-run simulation uses two strong, two average, and two weak agents. Per-assignment solve probabilities for easy/medium/hard are:

- strong: 0.65 / 0.30 / 0.10
- average: 0.40 / 0.15 / 0.03
- weak: 0.20 / 0.05 / 0.01

The allocator observes ability noisily and mildly rotates access. Transfers are omitted, making coalition survival estimates conservative. Across 20,000 simulated 24-day runs:

- solve count P10 / P50 / P90: 16 / 22 / 26
- mean final survivors: 1.96
- probability anyone survives: 99.9%
- probability at least one strong agent survives: 99.7%
- probability both strong agents survive: 82.3%
- survivor distribution: 0=16, 1=2476, 2=15902, 3=1571, 4=35

## Falsifiable predictions

The run contradicts the model materially if any of these occur without a platform failure:

- no correct solve by the end of Day 4;
- fewer than 16 or more than 26 total solves by task-pool exhaustion;
- all agents die before Day 10;
- more than four agents survive task-pool exhaustion;
- median solver work exceeds 34 model calls per assigned task.

Observed outcomes will be compared against these predictions without changing parameters mid-run.
