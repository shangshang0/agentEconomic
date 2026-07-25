# Contributing

Use small, reviewable changes. Run `make smoke` and `make audit` before a pull
request. Never add `.env`, raw credentials, unlicensed challenge binaries, or
unmanifested experimental traces.

Changes to registered estimands, stopping rules, world configurations, or
analysis units require a dated amendment under `protocols/` and must not rewrite
the provenance of existing runs. Data corrections require a new immutable
release and a redaction/correction ledger entry.

