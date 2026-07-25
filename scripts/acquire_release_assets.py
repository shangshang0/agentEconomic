#!/usr/bin/env python3
"""Acquire explicitly selected evidence roots with resumable, old-rsync-safe calls."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def mapping(values: list[str], option: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"{option} requires SOURCE_ID=VALUE")
        key, item = value.split("=", 1)
        if not key or not item:
            raise SystemExit(f"{option} requires SOURCE_ID=VALUE")
        result[key] = item
    return result


def tree_facts(root: Path) -> tuple[int, int]:
    files = 0
    size = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            files += 1
            size += path.stat().st_size
    return files, size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("selection", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source", action="append", default=[], metavar="ID=SSH_HOST")
    parser.add_argument("--ssh-option", action="append", default=[], metavar="ID=OPTION_STRING")
    parser.add_argument("--only-source", action="append", default=[])
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--bwlimit-kib", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sources = mapping(args.source, "--source")
    ssh_options = mapping(args.ssh_option, "--ssh-option")
    wanted = set(args.only_source)
    rows = [json.loads(line) for line in args.selection.read_text().splitlines() if line.strip()]
    rows = [row for row in rows if not wanted or row["source_id"] in wanted]
    args.destination.mkdir(parents=True, exist_ok=True)
    args.ledger.parent.mkdir(parents=True, exist_ok=True)
    completed_assets: set[str] = set()
    if args.ledger.is_file():
        for line in args.ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if not record.get("dry_run") and record.get("rsync_exit") == 0:
                completed_assets.add(str(record["asset_id"]))
    for index, row in enumerate(rows, 1):
        source_id = row["source_id"]
        if source_id not in sources:
            raise SystemExit(f"no SSH host mapping for {source_id}")
        asset_id = row["asset_id"]
        destination = args.destination / asset_id
        if asset_id in completed_assets and destination.is_dir():
            print(
                json.dumps(
                    {"kind": "acquire_skip_completed", "asset_id": asset_id, "source_id": source_id},
                    sort_keys=True,
                ),
                flush=True,
            )
            continue
        destination.mkdir(parents=True, exist_ok=True)
        remote_shell = ["ssh", "-o", "BatchMode=yes"]
        if source_id in ssh_options:
            remote_shell.extend(ssh_options[source_id].split())
        command = [
            "rsync",
            "-a",
            "-z",
            "--compress-level=1",
            "--partial",
            "--progress",
            "--rsync-path=sudo -n rsync",
            "-e",
            " ".join(remote_shell),
        ]
        if args.bwlimit_kib:
            command.append(f"--bwlimit={args.bwlimit_kib}")
        for pattern in row.get("acquisition_excludes", []):
            command.append(f"--exclude={pattern}")
        if args.dry_run:
            command.append("--dry-run")
        if any(any(character.isspace() or ord(character) < 32 for character in value) for value in (row["source_path"], asset_id)):
            raise SystemExit(f"old-rsync-unsafe whitespace/control character in path for {asset_id}")
        command.extend(
            [
                "--",
                f"{sources[source_id]}:{row['source_path'].rstrip('/')}/",
                str(destination) + "/",
            ]
        )
        print(
            json.dumps(
                {
                    "kind": "acquire_start",
                    "position": index,
                    "total": len(rows),
                    "asset_id": asset_id,
                    "source_id": source_id,
                    "expected_evidence_bytes": row.get("evidence_bytes"),
                    "dry_run": args.dry_run,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        started = time.time()
        completed = subprocess.run(command, check=False)
        if completed.returncode:
            raise SystemExit(f"rsync failed for {asset_id}: exit {completed.returncode}")
        files, size = tree_facts(destination)
        record = {
            "schema_version": 1,
            "asset_id": asset_id,
            "run_id": row["run_id"],
            "source_id": source_id,
            "source_path": row["source_path"],
            "destination": str(destination),
            "files": files,
            "bytes": size,
            "expected_evidence_bytes": row.get("evidence_bytes"),
            "dry_run": args.dry_run,
            "elapsed_seconds": round(time.time() - started, 3),
            "rsync_exit": completed.returncode,
        }
        if not args.dry_run:
            with args.ledger.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        print(json.dumps({"kind": "acquire_complete", **record}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
