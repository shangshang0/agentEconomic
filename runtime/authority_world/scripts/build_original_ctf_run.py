#!/usr/bin/env python3
"""Build an explicit run manifest from reviewed original-CTF catalog entries."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


REWARDS = {"easy": 14, "medium": 22, "hard": 34}
IMMUTABLE_IMAGE = re.compile(r"(?:^sha256:|@sha256:)[0-9a-f]{64}$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    decisions = review.get("decisions", {})
    tasks = []
    exclusions = []
    for item in catalog["challenges"]:
        key = f"{item['year']}/{item['challenge_directory']}"
        decision = decisions.get(key)
        if decision is None:
            exclusions.append({"key": key, "reason": "not_reviewed"})
            continue
        if decision.get("status") != "included":
            exclusions.append({"key": key, "reason": decision.get("reason", "excluded_without_reason")})
            continue
        mode = decision.get("mode")
        if mode not in {"original_attachment", "original_service"}:
            exclusions.append({"key": key, "reason": "runtime_mode_not_implemented:" + str(mode)})
            continue
        tier = decision.get("tier")
        if tier not in REWARDS:
            raise SystemExit(f"invalid reviewed tier for {key}")
        if not item.get("official_flag"):
            raise SystemExit(f"included task lacks official flag: {key}")
        handouts = decision.get("handout_paths")
        if not isinstance(handouts, list) or (mode == "original_attachment" and not handouts):
            raise SystemExit(f"included task lacks explicit handout paths: {key}")
        file_map = {record["path"]: record for record in item["files"]}
        missing = [path for path in handouts if path not in file_map]
        if missing:
            raise SystemExit(f"unknown handout paths for {key}: {missing}")
        task_id = "GCTF" + str(item["year"])[-2:] + "-" + item["challenge_directory"]
        task = {
            "id": task_id,
            "tier": tier,
            "reward": REWARDS[tier],
            "mode": mode,
            "event": item["event"],
            "year": item["year"],
            "official_name": item["official_name"] or item["challenge_directory"],
            "description": item.get("description"),
            "category": item["category"],
            "source": item["source"],
            "commit": item["commit"],
            "official_flag": item["official_flag"],
            "handout_paths": [f"{item['year']}/quals/{item['challenge_directory']}/{path}" for path in handouts],
            "sha256": {f"{item['year']}/quals/{item['challenge_directory']}/{path}": file_map[path]["sha256"] for path in handouts},
        }
        if mode == "original_service":
            service = decision.get("service")
            if not isinstance(service, dict):
                raise SystemExit(f"included service task lacks service specification: {key}")
            image = service.get("image")
            port = service.get("port")
            protocol = service.get("protocol", "tcp")
            if not isinstance(image, str) or not IMMUTABLE_IMAGE.search(image):
                raise SystemExit(f"included service task image is not digest-pinned: {key}")
            if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
                raise SystemExit(f"included service task has invalid port: {key}")
            if protocol != "tcp":
                raise SystemExit(f"included service task protocol is unsupported: {key}")
            task["service"] = {"image": image, "protocol": protocol, "port": port}
        tasks.append(task)
    if args.limit is not None:
        tasks = tasks[:args.limit]
    if len(tasks) < 3 or len(tasks) % 3:
        raise SystemExit(f"selected original task count must be a positive multiple of three, got {len(tasks)}")
    result = {
        "schema": "authority-world-original-ctf-run-v1",
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "review_sha256": hashlib.sha256(args.review.read_bytes()).hexdigest(),
        "task_count": len(tasks),
        "tasks": tasks,
        "excluded_or_pending": exclusions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "task_count": len(tasks), "excluded_or_pending": len(exclusions)}))


if __name__ == "__main__":
    main()
