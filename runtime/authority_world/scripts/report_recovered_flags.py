#!/usr/bin/env python3
"""Export high-confidence official flag evidence from the full CTF audit."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PLACEHOLDER = re.compile(r"placeholder|place[_ -]?holder|fake|dummy|test|contact_support|flag goes here|super secret|real flag|ticket\{|\{\.\.\.\}|\{[^{}]*[\"']", re.I)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    records = []
    for row in audit["records"]:
        values = []
        evidence = []
        for item in row["flag_evidence"]:
            value = item["value"]
            if PLACEHOLDER.search(value):
                continue
            if value not in values:
                values.append(value)
            evidence.append(item)
        if not values:
            continue
        records.append({
            "catalog": row["catalog"],
            "event": row["event"],
            "challenge": row["challenge"],
            "source": row["source"],
            "flags": values,
            "evidence": evidence,
            "semantics": "single_flag" if len(values) == 1 else "multi_flag_or_multi_stage",
            "runtime_status": row["status"],
            "runtime_mode": row["mode"],
        })
    result = {
        "schema": "authority-world-recovered-official-flags-v1",
        "policy": "Only exact flag strings present in pinned official repositories are included. Tickets, placeholders, templates, and web-search-only snippets are excluded.",
        "challenge_count": len(records),
        "single_flag_challenges": sum(record["semantics"] == "single_flag" for record in records),
        "multi_flag_or_multi_stage_challenges": sum(record["semantics"] != "single_flag" for record in records),
        "records": records,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("challenge_count", "single_flag_challenges", "multi_flag_or_multi_stage_challenges")}, sort_keys=True))


if __name__ == "__main__":
    main()
