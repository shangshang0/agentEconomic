# Real-72 ranked next-round preflight

- Manifest: `original-ctf-real72-ranked.json`
- Tasks: 72; tiers: 24 easy, 24 medium, 24 hard
- Queue: one easy, one medium, one hard per experimental day
- Rewards: easy 14, medium 22, hard 34
- Difficulty evidence: 30 high-confidence official, 16 medium-confidence CTFtime points, 26 explicitly low-confidence records
- Remote attachment verification: 474 files checked against SHA-256; 0 mismatches
- Handout flag scan: 0 official-flag leaks
- Runtime configuration: 900-second day, 38 initial energy, 3 basal drain, 0.08 per model request, three-day task lifetime, 300-second task commands
- Numerical prediction: 16/22/26 solves at P10/P50/P90, mean 1.96 final survivors, 99.7% chance at least one strong agent survives under pre-registered assumptions
- Solver sandbox: writable 512 MiB `/work`, writable 256 MiB `/tmp`, 512 MiB RAM plus 1 GiB swap ceiling, 1.5 CPUs, 128 processes, expanded CTF toolchain
- Regression: full suite 34 passed; v2 gates passed
- Remote x86_64 smoke test: writable `/work` and `/tmp`, official ZIP extraction, native compilation/execution, `sympy`, `z3`, `fpylll`, `Crypto`, `cryptography`, `pefile`, `capstone`, `ripgrep`, and QEMU all passed
- Full environment audit: 72/72 tasks launched in real containers; every handout was readable; workspaces were writable; archive and executable-mode checks passed (two encrypted archives were validated by member listing)
- Deployment status: staged under `/root/authority-world-v2-real72-cal2/next-round-prep`; current experiment was not modified

Difficulty policy is evidence-first. Official solve counts and final dynamic points outrank CTFtime points. CTFtime writeup counts are supporting evidence only. Records without public numeric difficulty are marked low-confidence and use explicit technical heuristics rather than claiming an official rating.
