#!/usr/bin/env python3
"""Catalog original Google CTF Quals releases without selecting or modifying them."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def metadata_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    match = re.search(r"^" + re.escape(key) + r":\s*['\"]?([^'\"\n]+)", path.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    return match.group(1).strip() if match else None


def metadata_description(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^description:\s*\|[+-]?\s*\n((?:[ \t]+.*\n?)*)", text, re.MULTILINE)
    if not match:
        return metadata_value(path, "description")
    lines = [line.strip() for line in match.group(1).splitlines()]
    return "\n".join(line for line in lines if line).strip() or None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "-C", str(args.repo), "rev-parse", "HEAD"], text=True).strip()
    challenges = []
    for year in args.years:
        root = args.repo / str(year) / "quals"
        if not root.is_dir():
            raise SystemExit(f"missing Google CTF Quals tree: {root}")
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            files = sorted(path for path in directory.rglob("*") if path.is_file())
            relative = [str(path.relative_to(directory)) for path in files]
            lowered = "\n".join(relative).lower()
            review_flags = []
            if directory.name in {"kctf", "third_party"}:
                review_flags.append("probable_shared_component_not_standalone_challenge")
            if not any(name.startswith("attachments/") for name in relative):
                review_flags.append("no_official_player_attachment_directory")
            if any(token in lowered for token in ("qemu", "vmlinuz", "bzimage", "kernel")):
                review_flags.append("requires_vm_or_kernel_isolation_review")
            if any(token in lowered for token in ("bot.mjs", "chrome", "firefox")):
                review_flags.append("requires_browser_bot_service")
            metadata = directory / "metadata.yaml"
            challenges.append({
                "event": f"Google CTF {year} Quals",
                "year": year,
                "challenge_directory": directory.name,
                "official_name": metadata_value(metadata, "name"),
                "description": metadata_description(metadata),
                "category": metadata_value(metadata, "category") or directory.name.split("-", 1)[0],
                "official_flag": metadata_value(metadata, "flag"),
                "official_host": metadata_value(metadata, "host"),
                "official_link": metadata_value(metadata, "link"),
                "source": f"https://github.com/google/google-ctf/tree/{commit}/{year}/quals/{directory.name}",
                "commit": commit,
                "files": [{"path": str(path.relative_to(directory)), "sha256": digest(path), "bytes": path.stat().st_size} for path in files],
                "review_flags": review_flags,
                "status": "pending_manual_review",
                "exclusion_reason": None,
            })
    result = {
        "schema": "original-ctf-catalog-v1",
        "repository": "https://github.com/google/google-ctf",
        "commit": commit,
        "license": "Apache-2.0",
        "selection_policy": "No silent omission; every directory is retained and individually reviewed.",
        "directory_count": len(challenges),
        "challenges": challenges,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "directory_count": len(challenges), "commit": commit}))


if __name__ == "__main__":
    main()
