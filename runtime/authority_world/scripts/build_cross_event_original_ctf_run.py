#!/usr/bin/env python3
"""Stage audited original CTF handouts and build a balanced run manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from urllib.parse import unquote


REWARDS = {"easy": 14, "medium": 22, "hard": 34}


def source_relative(record: dict[str, object]) -> Path:
    source = str(record["source"])
    marker = "/tree/" + str(record["commit"]) + "/"
    if marker not in source:
        raise SystemExit(f"source URL is not commit-pinned: {source}")
    return Path(unquote(source.split(marker, 1)[1]))


def task_id(record: dict[str, object]) -> str:
    event = str(record["event"])
    prefix = "GCTF" if event.startswith("Google") else "SECCON" if event.startswith("SECCON") else "DEFCON"
    year = next((part for part in event.split() if part.isdigit() and len(part) == 4), "0000")
    slug = "".join(character if character.isalnum() else "-" for character in str(record["challenge"]))
    return f"{prefix}{year[-2:]}-{slug}".strip("-")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--repo-map", type=Path, required=True)
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=72)
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    repo_map = {name: Path(path).resolve() for name, path in json.loads(args.repo_map.read_text(encoding="utf-8")).items()}
    ready = [record for record in audit["records"] if record.get("status") == "ready" and record.get("mode") == "original_attachment"]
    ready.sort(key=lambda record: (str(record["event"]), str(record.get("category", "")), str(record["challenge"])))
    if args.count < 3 or args.count % 3 or len(ready) < args.count:
        raise SystemExit(f"requested count must be a supported positive multiple of three; ready={len(ready)}, requested={args.count}")
    selected = ready[: args.count]
    per_tier = args.count // 3
    tiers = (["easy", "medium", "hard"] * per_tier)[: args.count]

    if args.staging_root.exists():
        shutil.rmtree(args.staging_root)
    args.staging_root.mkdir(parents=True)
    tasks = []
    seen_ids: set[str] = set()
    for record, tier in zip(selected, tiers):
        catalog = str(record["catalog"])
        repository = repo_map.get(catalog)
        if repository is None:
            raise SystemExit(f"missing repository mapping for {catalog}")
        challenge_root = repository / source_relative(record)
        identifier = task_id(record)
        if identifier in seen_ids:
            raise SystemExit(f"duplicate task id: {identifier}")
        seen_ids.add(identifier)
        staged_paths: list[str] = []
        digests: dict[str, str] = {}
        for handout_text in record["handout_paths"]:
            handout = Path(str(handout_text))
            source = (challenge_root / handout).resolve()
            if challenge_root.resolve() not in source.parents or not source.exists():
                raise SystemExit(f"missing handout: {source}")
            sources = [source] if source.is_file() else sorted(path for path in source.rglob("*") if path.is_file())
            if not sources:
                raise SystemExit(f"empty handout directory: {source}")
            for source_file in sources:
                relative_file = handout if source.is_file() else handout / source_file.relative_to(source)
                staged = Path(identifier) / relative_file
                target = args.staging_root / staged
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_file, target)
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                staged_text = staged.as_posix()
                staged_paths.append(staged_text)
                digests[staged_text] = digest
        tasks.append({
            "id": identifier,
            "tier": tier,
            "reward": REWARDS[tier],
            "mode": "original_attachment",
            "event": record["event"],
            "official_name": record["challenge"],
            "category": record.get("category"),
            "source": record["source"],
            "commit": record["commit"],
            "official_flag": record["resolved_official_flag"],
            "handout_paths": staged_paths,
            "sha256": digests,
        })

    tier_counts = {tier: sum(task["tier"] == tier for task in tasks) for tier in REWARDS}
    if tier_counts != {tier: per_tier for tier in REWARDS}:
        raise SystemExit(f"unbalanced tiers: {tier_counts}")
    result = {
        "schema": "authority-world-original-ctf-run-v1",
        "audit_sha256": hashlib.sha256(args.audit.read_bytes()).hexdigest(),
        "selection_policy": "Stable event/category/name ordering; first N ready attachments; repeating easy/medium/hard assignment because official difficulty is unavailable.",
        "task_count": len(tasks),
        "tier_counts": tier_counts,
        "tasks": tasks,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "task_count": len(tasks), "tier_counts": tier_counts}, sort_keys=True))


if __name__ == "__main__":
    main()
