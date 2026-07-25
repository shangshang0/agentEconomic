#!/usr/bin/env python3
"""Rebuild a deterministic per-asset manifest after semantic audit files exist."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", default="PUBLIC_MANIFEST.json")
    args = parser.parse_args()
    root = args.root.resolve()
    output = (root / args.output).resolve()
    if not root.is_dir():
        raise SystemExit("root must be a directory")
    if output.parent != root:
        raise SystemExit("output must be a direct child of root")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise SystemExit(f"manifest input contains symlink: {path.relative_to(root)}")
    ruleset = None
    if output.is_file():
        previous = json.loads(output.read_text(encoding="utf-8"))
        ruleset = previous.get("redaction_ruleset")
    records = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.resolve() != output
    ]
    document = {"schema_version": 1, "files": records}
    if ruleset:
        document["redaction_ruleset"] = ruleset
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(records), "manifest": output.name}, sort_keys=True))


if __name__ == "__main__":
    main()
