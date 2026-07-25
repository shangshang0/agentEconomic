#!/usr/bin/env python3
"""Run the repository's deterministic public-evidence gates."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository", type=Path)
    parser.add_argument("--release-root", type=Path)
    args = parser.parse_args()
    root = args.repository.resolve()
    commands = [
        [sys.executable, str(root / "scripts/scan_secrets.py"), str(root)],
        [
            sys.executable,
            str(root / "scripts/audit_catalog.py"),
            str(root / "data/catalog/worlds.jsonl"),
            "--assets",
            str(root / "data/catalog/assets.jsonl"),
        ],
    ]
    if args.release_root:
        commands[-1] += ["--release-root", str(args.release_root)]
    for command in commands:
        subprocess.run(command, cwd=root, check=True)
    print("Agent Economic evidence gates PASS")


if __name__ == "__main__":
    main()
