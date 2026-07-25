# Security policy

Do not open a public issue for a suspected credential, personal-data, or
provider-authentication leak. Contact the repository owner privately through
GitHub's security advisory interface.

Public traces are transformed by `scripts/redact_export.py` and must pass
`scripts/scan_secrets.py`. Release publication fails closed on a high-confidence
match. The source `.env` files are never release inputs. Stable placeholders
preserve joinability without preserving the secret value.

If a leak is confirmed, the affected asset will be withdrawn, credentials will
be rotated, and a replacement release plus a signed redaction amendment will
be published. Git history is not considered an acceptable secret store.

