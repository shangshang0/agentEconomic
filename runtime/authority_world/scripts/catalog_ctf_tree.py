#!/usr/bin/env python3
"""Build a transparent original-challenge catalog from one checked-out event tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


SKIP_NAMES = {".git", ".github", "competition", "competition-domestic", "competition-international", "welcome", "_images"}
CATEGORY_NAMES = {"blockchain", "crypto", "hardware", "hw", "jail", "jeopardy", "misc", "pwn", "pwnable", "reversing", "rev", "sandbox", "web"}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def challenge_dirs(root: Path) -> list[tuple[str, Path]]:
    result = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name in SKIP_NAMES:
            continue
        if entry.name.lower() in CATEGORY_NAMES:
            for child in sorted(entry.iterdir()):
                if child.is_dir() and child.name not in SKIP_NAMES:
                    result.append((entry.name.lower(), child))
        else:
            result.append((entry.name.split("-", 1)[0].lower(), entry))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "-C", str(args.repo), "rev-parse", "HEAD"], text=True).strip()
    rows = []
    for category, directory in challenge_dirs(args.repo):
        files = sorted(path for path in directory.rglob("*") if path.is_file() and ".git" not in path.parts)
        names = "\n".join(str(path.relative_to(directory)).lower() for path in files)
        flags = []
        if any(token in names for token in ("qemu", "vmlinuz", "bzimage", "kernel")):
            flags.append("requires_vm_or_kernel_isolation_review")
        if any(token in names for token in ("chrome", "firefox", "playwright", "bot.")):
            flags.append("requires_browser_bot_service_review")
        if not any(Path(name).name.lower().startswith(("readme", "description", "challenge")) for name in names.splitlines()):
            flags.append("challenge_description_location_requires_review")
        relative = str(directory.relative_to(args.repo))
        rows.append({
            "event": args.event,
            "challenge": directory.name,
            "category": category,
            "source": f"{args.source_url}/tree/{commit}/{relative}",
            "commit": commit,
            "files": [{"path": str(path.relative_to(directory)), "sha256": sha256(path), "bytes": path.stat().st_size} for path in files],
            "review_flags": flags,
            "status": "pending_manual_review",
            "exclusion_reason": None
        })
    result = {"schema": "original-ctf-catalog-v1", "event": args.event, "repository": args.source_url, "commit": commit, "challenge_count": len(rows), "challenges": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"event": args.event, "challenge_count": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
