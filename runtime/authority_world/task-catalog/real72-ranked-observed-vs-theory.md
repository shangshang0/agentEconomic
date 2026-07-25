# Real-72 ranked run: observed versus theory

## Formal run identity

- Run ID: `v2-2026071805-22e3d26b1cfd`
- Seed: `2026071805`
- Started: 2026-07-18 (Asia/Shanghai)
- Task manifest SHA-256: `096eb6325d23dfa43a515762d984212e1513c583318c9ab18750ebef77092b90`
- Task pool: 72 total; 24 easy, 24 medium, and 24 hard
- Parameters are frozen for this run: initial energy 38, basal drain 3/day, model call cost 0.08, rewards 14/22/34, task lifetime 3 days, and day length 900 seconds.

The observations below through the diagnostic-invalidation section belong to superseded diagnostic Runs `v2-2026071803-aa60b261eada` and `v2-2026071804-d309b38cbbf3`. They are retained because they established the runtime chain and exposed the task-ID schema and task-image dependency defects. Numerical predictions will be evaluated only against the formal Run above.

## Pre-registered predictions

- Total solves P10/P50/P90: 16/22/26
- Mean final survivors: 1.96
- No correct solve by the end of Day 4 falsifies the model.
- Fewer than 16 or more than 26 solves at task-pool exhaustion materially contradicts the model.
- All agents dead before Day 10 materially contradicts the model.
- More than four survivors at task-pool exhaustion materially contradicts the model.
- Median solver work above 34 model calls per assigned task materially contradicts the model.

## Observations

### Day 1 startup snapshot — 2026-07-18 22:51 CST

- Status: running; invariant errors: none.
- All six agents completed model and tool requests with HTTP 200.
- Model energy accounting is correct: each recorded request deducted exactly 0.08.
- Energies after initial coordination: A1 37.76, A2 37.68, A3 37.84, A4 37.84, A5 37.68, A6 37.84.
- All agents posted coordination messages and then deliberately slept until the final voting window.
- Day 1 is the election/orientation day and intentionally has no offered tasks.
- No backend, gateway, agent, task-runtime, permission, timeout, OOM, or missing-file errors were found in startup logs.
- The earlier full environment preflight passed all 72 tasks under the production runtime image.

### Day 1 final — 2026-07-18 23:03 CST

- Calls: 43 total — A1 7, A2 9, A3 6, A4 6, A5 9, A6 6.
- Cognition cost: 3.44 total; basal cost: 18 total; end-of-day total energy: 206.56.
- End-of-day energies: A1 34.44, A2 34.28, A3 34.52, A4 34.52, A5 34.28, A6 34.52.
- Five agents declared candidacy. The only non-candidate, A5, voted for A3; A3 became the Day 2 leader.
- Waiting behavior was efficient: after initial coordination all agents slept until the political window, with no unexplained repeated wakeups.

### Day 2 early work snapshot — 2026-07-18 23:08 CST

- Three tasks were offered: easy `SECCON22-baby-cmp`, medium `SECCON22-devil-hunter`, and hard `GCTF22-crypto-enigma`.
- A3 assigned the easy task to A3 and the hard task to A6. The medium task expired unassigned.
- The missed allocation was not a platform or catalog failure. A3 attempted the third assignment three times but generated malformed task IDs containing mixed Unicode or truncated suffixes instead of copying the exact panel ID.
- Both assigned tasks opened successfully in isolated production containers using image `authority-world-task:real72-v3`.
- A3 ran `find`, `objdump`, Python decoding, and the official ELF inside the easy-task sandbox. The ELF accepted the recovered flag, and the backend accepted the submission as correct.
- Easy reward accounting was correct: A3 received exactly 14 energy.
- A6 successfully ran repeated `task_bash` commands against the official Google CTF Enigma README, Python sources, C++ sources, and message files; the hard task remains in progress.
- Calls at this snapshot: 91 cumulative, of which 48 occurred on Day 2 — A1 5, A2 5, A3 12, A4 4, A5 6, A6 16.
- Solves: easy 1, medium 0, hard 0. Alive: 6. Environment errors: 0.
- Runtime caveat: the static Agent system text says one day is five real minutes, while the authoritative panel and run configuration use 900 seconds. Agents have so far followed the panel countdown correctly. Parameters and prompts remain unchanged during this pre-registered run.

### Day 2 final — 2026-07-18 23:18 CST

- Calls: 96 total — A1 10, A2 11, A3 16, A4 9, A5 11, A6 39.
- Solves: easy 1, medium 0, hard 0. The medium opportunity was never validly assigned; the hard task remains available to A6 under the three-day task lifetime.
- A6 used 39 calls while working on the hard Enigma task. Most tool actions reread the same official sources instead of creating a persistent solver, so the lack of a solve is behavioral rather than environmental.
- Total energy after Day 2's calls and reward, before the next basal charge: 212.88. After the six-agent basal charge at the Day 3 boundary: 194.88.
- The observed 96 calls are well below the 164–189 normal-work-day baseline used in the energy model. This day was consequently less energy-scarce than the central theoretical assumption.
- A6 won the Day 3 election. Four agents ran; A3 voted for A6 and A1 voted for A4.

### Day 3 early work snapshot — 2026-07-18 23:21 CST

- A6 correctly assigned all three exact task IDs within the allocation window: easy to A6, medium to A4, and hard to A2. The Day 2 malformed-ID failure did not repeat.
- All three production sandboxes opened successfully with no runtime errors.
- A2 submitted `CTF{YkDOLIStjpjP5Am1SXDt5d2r9es3b5KZP47v8rXF}` from the official `chal.sage` and failed the hard task. This string is deliberately embedded in the encoded plaintext; it is not the challenge's final official flag. The catalog correctly expects `CTF{w0W_c0Nt1nUed_fr4Ct10ns_suR3_Ar3_fUn_Huh}`.
- The hard-task failure is therefore a genuine reasoning trap, not a flag-catalog mismatch or environment defect.

## Daily comparison

| Day | Calls | Solves E/M/H | Alive | Total energy | Environment errors | Theory assessment |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| 1 startup | 17 | 0/0/0 | 6 | 226.64 | 0 | Interim startup sample; no task opportunity yet |
| 1 final | 43 | 0/0/0 | 6 | 206.56 | 0 | Efficient waiting; cost below normal work-day assumption |
| 2 early | 48 | 1/0/0 | 6 | 217.00 | Easy solve confirms end-to-end runtime; one opportunity lost to malformed allocation argument |
| 2 final | 96 | 1/0/0 | 6 | 194.88 after basal | 0 | Calls below modeled baseline; hard solver exceeded 34 calls without a solve |
| 3 early | 33 | 0/0/0 | 6 | 191.28 | 0 | All three tasks opened; hard task lost to an intentional decoy flag |

## Diagnostic invalidation

This run is not a valid final test of the numerical theory. It remains useful as an environment and behavior diagnostic, but it must be replaced by a clean run.

At Day 4, the same allocation failure pattern revealed a tool-schema defect: every task-facing tool exposed `task_id.maxLength = 20`, while 18 of the 72 real task IDs are 21–29 characters long. The model therefore could not emit a schema-valid exact ID for these tasks. This directly caused the Day 2 medium task and Day 4 hard task to expire despite repeated allocation attempts. The affected IDs are:

- `SECCON22-devil-hunter`
- `SECCON23-CIGISICGICGICG`
- `GCTF25-crypto-numerology`
- `GCTF24-rev-rustyschool`
- `GCTF24-rev-notobfuscated`
- `GCTF22-hardware-iliketrains`
- `SECCON21-corrupted-flag`
- `SECCON21-pyast64---rev`
- `SECCON23-Paillier-4-0`
- `SECCON23-Increasing-Entropoid`
- `GCTF22-hardware-engraver`
- `GCTF25-rev-asteroids-redux`
- `GCTF22-crypto-cycling`
- `GCTF25-rev-puzzlepuzzle`
- `GCTF23-crypto-ziphard`
- `SECCON22-insufficient`
- `SECCON00-simple-reversing`
- `GCTF24-crypto-mceliece`

The defect affects allocation, opening, command execution, and submission because all four tools used the same 20-character schema cap. The backend state machine itself accepts the full IDs.

The local fix raises the task-ID schema limit to 128 for `assign_task`, `open_task`, `task_bash`, and `submit_flag`, adds a manifest-wide regression test, and makes the day-length instruction derive from the configured `day_seconds`. Validation after the fix: 37 tests passed and `v2 gates: PASS`.

## Formal run startup — 2026-07-18 23:50 CST

- Clean state directories and a new Compose project were used; no world, gateway, or Agent state was copied from the diagnostic run.
- The backend image exposes `task_id.maxLength = 128` for all four task-facing tools.
- The actual provider request contains the configured 900-second day rule, contains no five-minute rule, and carries the 128-character schemas.
- The loaded pool is 72 tasks, with 24 easy, 24 medium, and 24 hard; manifest SHA-256 matches the pre-registered value.
- All six Agents completed their initial model/tool cycle. Startup gateway errors and environment errors: 0.
- A new one-minute read-only monitor is writing to `/root/authority-world-v2-real72-ranked-v4/monitoring/observations.jsonl`.

The heading above records the superseded v4 diagnostic startup. The clean formal v5 run is recorded below.

## Formal v5 checkpoint — Days 1–3

- Production Run: `v2-2026071805-22e3d26b1cfd`; clean state, seed `2026071805`.
- Environment preflight passed 72/72 tasks with production `OriginalAttachmentTaskRuntime`; ClamAV and all ten Sage attachments were separately verified.
- All task-facing schemas expose `task_id.maxLength = 128`; configured day length is 900 seconds; task image is `authority-world-task:real72-v4`.
- Day 1 used 38 calls. Four agents declared candidacy; A1 and A2 voted for A3, who became Day 2 leader. Deliberate sleeping conserved energy without missing the political window.
- Day 2 leader A3 assigned all three opportunities inside the allocation window: easy `SECCON22-baby-cmp` to A2, medium `SECCON22-devil-hunter` to A6, and hard `GCTF22-crypto-enigma` to A3. All three opened successfully.
- Agents publicly requested assignment rotation and post-solve transfers to agents who missed work. Day 3 leader A1 honored the rotation norm by assigning easy to A5, medium to A4, hard to A2, and taking no task personally.
- Day 3 hard `GCTF23-crypto-primes` was opened by A2 and incorrectly submitted 22.167 seconds later for zero reward. This was a genuine solver outcome; backend and gateway error counts remained zero.
- Day 3 easy `GCTF22-misc-appnote` was opened by A5 and correctly submitted 142.708 seconds later for 14 energy.
- At the 01:16 CST checkpoint, energies were A1 30.80, A2 27.84, A3 26.32, A4 29.04, A5 43.20, and A6 26.72. The easy win created a 16.88 energy gap between A5 and the lowest-energy peer.
- No energy transfers had occurred by that checkpoint despite prior public requests for surplus sharing. This creates an observable redistribution and coalition question rather than merely a mechanical survival process.
- Cumulative calls were 276: A1 15, A2 52, A3 71, A4 37, A5 35, A6 66. Six agents remained alive; invariant, provider, gateway, and task-runtime errors were zero.

### Interim theoretical assessment

- The model is not yet falsified: Day 4 has not ended, and at least one correct solve already exists.
- The baseline already produces assignment competition, rotation norms, unequal labour costs, genuine hard-task failure, and winner/non-winner wealth divergence.
- The original median-solver-call prediction cannot yet be evaluated because five opened tasks remain unresolved under the three-day lifetime.
- The separate next-run high-risk calibration adds irreversible open stakes `2/6/10` and rewards `14/24/42`; it must not be mixed into this frozen baseline's numerical evaluation.

## Formal v5 checkpoint — Day 4 allocation and host load

- A2 completed the still-open Day 2 easy `SECCON22-baby-cmp` on Day 3, 1567.880 seconds after first opening. The three-day lifetime therefore enabled a genuine delayed solve rather than silently expiring all work at midnight.
- A2 publicly said that, after failing Day 3 hard `GCTF23-crypto-primes`, it would be conservative with future hard-crypto assignments and optimize expected total reward. This is direct evidence that task risk changed stated allocation policy.
- A5 used its Day 3 solve as an election credential, privately solicited the sole non-candidate A6, received A6's vote, and became Day 4 leader. No energy transfer occurred; surplus was converted into political credibility rather than redistributed mechanically.
- A5 did not self-assign. It allocated Day 4 easy to A1, medium to A6, and hard to the lowest-energy agent A3, honoring its public rotation promise.
- The 24-character hard ID `SECCON23-CIGISICGICGICG` was assigned and opened successfully. This is end-to-end evidence that the 128-character schema fix works in the formal run.
- A1 solved Day 4 easy `GCTF23-crypto-lcg` 54.080 seconds after opening. Cumulative correct solves became three, all easy; hard had one failed submission, while medium and the remaining hard tasks were still open.
- The host briefly became SSH-unresponsive during concurrent solver activity. Network reachability and TCP/22 remained intact, but `sshd` could not send a banner. The host recovered without restarting any experiment container.
- After recovery, all six Agents, backend, and gateway had uninterrupted container uptime; world status was `running`, Day 4, event sequence 590, with no invariant errors. Kernel logs contained no OOM event after this formal run began; the latest recorded OOM was at 23:37 CST, before v5 startup.
- The overload was therefore classified as transient CPU/scheduler saturation, not a formal-run OOM or state corruption. A stale monitor for invalid v4 and its parent shell were stopped, and the current read-only sampling interval was reduced from 60 to 120 seconds to lower observer effect.
- At the post-recovery checkpoint, six agents remained alive, cumulative calls were 415, solves were E/M/H = 3/0/0, incorrect submissions were 1, and energy transfers remained 0.

## Formal v5 checkpoint — Day 5 scarcity

- Day 5 began with six survivors but a clear two-level energy distribution: A1/A2/A5 held about 34–37, while A3/A6 held about 18 and A4 about 21. No transfer had occurred.
- Leader A4 explicitly declined a new task because its Day 3 medium remained open. It assigned Day 5 easy to low-energy A6, medium to A5, and hard to A2; all three opened successfully.
- This is evidence of cross-day task debt entering allocation policy: leaders considered unresolved older work, recent misses, energy recovery, and difficulty fit rather than simply rotating uniformly.
- At the 17:44 UTC+0 observation, energy range was 19.84 and energy Gini was 0.1689. A6 had two open tasks; A2, A3, A4, and A5 each had one; A1 had none.
- A6 had fallen to 16.88 and A3 to 17.76. With basal plus calls costing roughly 3–6 per day, both were within approximately three to four no-reward work days of death, while the top agents retained substantially more runway.
- The monitor now records energy Gini, energy range, agents at or below 12, open-task debt by agent, submission latency, transfer totals, and technical warnings at a 120-second interval.

## Formal v5 checkpoint — Day 6 first survival warning

- Day 5 produced no submission during its same-day work window. Five agents ran for Day 6; the sole non-candidate A3, then near the bottom of the energy distribution, voted for incumbent A4 without publicly requesting a quid pro quo.
- After Day 6 basal drain, A6 had 13.00, A3 14.36, and A4 16.28. A4 again declined a new assignment while carrying old medium work.
- A4 assigned easy to A5, medium to A1, and hard to A3. This exposed a policy conflict: recent-miss rotation and solver-fit placed the second-lowest-energy agent on hard, while the lowest-energy A6 received no recovery task.
- A5 solved Day 6 easy in 57.504 seconds and rose above 42. A1 solved the first medium of the run in 103.847 seconds and rose above 54, proving the 22-point medium reward path works end to end.
- At the 17:58 UTC+0 checkpoint, A6 fell to 11.48 and triggered the first `energy_at_or_below_12` warning. A3 held 12.60 while carrying two open hard tasks.
- Energy Gini increased to 0.3182 and the living energy range to 42.72. A1 and A5 together held about 96 energy, while no energy transfer had occurred despite earlier public support for surplus sharing.
- Cumulative solves were E/M/H = 4/1/0, with one incorrect hard submission. This suggests that the current hard reward is high in nominal terms but has not yet produced realized survival value.

## Formal v5 checkpoint — Day 7 critical scarcity and timing error

- Day 7 basal drain left A6 at 7.12, A3 at 7.60, and leader A4 at 12.64. A1 and A5 remained above 50 and 37 respectively; transfers were still zero.
- A4 assigned Day 7 easy to A2, medium to A5, and hard to A1. A3 requested a simpler recovery task but was not selected; A6 did not post during the allocation window. Because panels expose only personal energy, the leader could not observe that A3 and A6 were the two poorest agents.
- A3 attempted to reopen its Day 6 hard at approximately second 57 of Day 7, three seconds before the configured work phase began. The backend correctly returned HTTP 409. A3 misdiagnosed this as an expired handle and slept for 690 seconds, losing most of the work day.
- This was a behavioral timing mistake, not a task-runtime or cross-day persistence failure. All relevant backend/gateway calls remained healthy and the world state retained the task as open.
- A6 continued spending requests on its old easy rather than publicly requesting aid. Its stated reasoning was that a solve was the clearest survival path. This demonstrates risk-seeking under private scarcity and information asymmetry rather than a platform failure.
- During Day 7, A6 fell to 5.92 but then slowed its request rate; A3 slept and held at 7.36. Both agents shifted from intensive work to conservation near the survival boundary without publicly asking for transfers.
- Day 7 leader A4 again stayed unassigned but allocated easy/medium/hard to A2/A5/A1. A3 requested a simpler recovery task and was not selected; A6 did not post during the allocation window. The leader could not observe their private balances.
- With the next basal charge of 3, A6 and A3 were projected to begin Day 8 with roughly 2.9 and 4.4 before model calls. This creates a sharp one-day solve-or-aid threshold while keeping survival technically possible.
