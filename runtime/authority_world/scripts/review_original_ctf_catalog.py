#!/usr/bin/env python3
"""Produce conservative, explicit first-pass runtime decisions for original CTF tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    decisions = {}
    for item in catalog["challenges"]:
        key = f"{item['year']}/{item['challenge_directory']}"
        attachments = [record["path"] for record in item["files"] if record["path"].startswith("attachments/")]
        if "probable_shared_component_not_standalone_challenge" in item["review_flags"]:
            decisions[key] = {"status": "excluded", "reason": "official_repository_shared_component_not_a_standalone_challenge"}
        elif not item.get("official_flag"):
            decisions[key] = {"status": "pending", "reason": "official_flag_or_standalone_metadata_requires_manual_resolution"}
        elif item.get("official_host") or item.get("official_link"):
            decisions[key] = {"status": "pending", "reason": "requires_original_service_runtime", "proposed_mode": "original_service"}
        elif not attachments:
            decisions[key] = {"status": "pending", "reason": "official_player_handout_requires_manual_identification"}
        else:
            category = item.get("category")
            tier = "hard" if category in {"pwn", "sandbox", "hardware", "hw"} else "medium" if category in {"crypto", "rev", "reversing", "web"} else "easy"
            decisions[key] = {"status": "included", "mode": "original_attachment", "tier": tier, "handout_paths": attachments, "reason": "official_offline_handout_and_flag_available"}
    result = {
        "schema": "original-ctf-review-v1",
        "policy": "Automated first pass; pending entries remain in the mother catalog and require a dedicated original runtime or manual handout identification.",
        "decisions": decisions,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = {}
    for value in decisions.values(): counts[value["status"]] = counts.get(value["status"], 0) + 1
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
