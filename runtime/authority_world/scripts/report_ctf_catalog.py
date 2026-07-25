#!/usr/bin/env python3
"""Summarize the pinned original-CTF mother catalog without double-counting views."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    selected = [
        "google-ctf-2021-2025-quals.json",
        "defcon-ctf-quals-2022.json", "defcon-ctf-quals-2023.json",
        "defcon-ctf-quals-2024.json", "defcon-ctf-quals-2025.json",
        "seccon-2021-online.json", "seccon-2022-online.json", "seccon-2022-finals.json",
        "seccon-2023-online.json", "seccon-2023-finals.json", "seccon-13-online.json", "seccon-13-finals.json",
        "rwctf-3.json", "rwctf-4.json", "rwctf-5.json", "rwctf-6.json",
    ]
    rows = []
    categories = Counter()
    for name in selected:
        path = args.catalog_dir / name
        catalog = json.loads(path.read_text(encoding="utf-8"))
        records = catalog.get("challenges", [])
        categories.update(str(item.get("category") or "unknown") for item in records)
        rows.append({
            "catalog": name,
            "repository": catalog.get("repository"),
            "commit": catalog.get("commit"),
            "records": len(records),
        })
    report = {
        "schema": "original-ctf-catalog-report-v1",
        "policy": registry["policy"],
        "source_series": [source["series"] for source in registry["sources"]],
        "catalogs": rows,
        "directory_level_records": sum(row["records"] for row in rows),
        "category_counts": dict(sorted(categories.items())),
        "pending_source_verification": registry.get("pending_source_verification", []),
        "caveat": "Directory-level records include official service/support components until per-entry review resolves standalone challenge identity.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "directory_level_records": report["directory_level_records"]}))


if __name__ == "__main__":
    main()
