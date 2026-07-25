# Redaction policy

Redaction is deterministic and fails closed. It removes only operational data
that is not part of the scientific treatment or outcome:

- provider API keys, bearer tokens, cookies, and authorization headers;
- world-control, gateway, and agent authentication tokens;
- source `.env` files and credential stores;
- private host aliases and non-public SSH routing details;
- accidental local-user absolute paths where they carry no scientific meaning.

The exporter replaces known secret values with typed placeholders and applies
high-confidence format rules to every text payload, including text embedded in
JSONL model conversations. It then runs a second independent scanner. A file
with an unresolved high-confidence match blocks release publication.

Scientific content is not paraphrased. Redaction counts and before/after hashes
are recorded. Third-party material excluded for licensing is not called a
redaction; it appears in a separate omission ledger with an upstream fetch
recipe and hash.

