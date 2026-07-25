#!/usr/bin/env python3
"""Restore and verify a bundle made by build_cas_bundle.py."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    destination = args.destination.resolve()
    manifest = json.loads((bundle / "CAS_MANIFEST.json").read_text(encoding="utf-8"))
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit("destination must not exist or must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    for entry in manifest["files"]:
        target = (root / entry["path"]).resolve()
        if root not in target.parents:
            raise SystemExit(f"unsafe manifest path: {entry['path']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry["type"] == "symlink":
            link_target = entry["target"]
            resolved_target = (target.parent / link_target).resolve()
            if os.path.isabs(link_target) or root not in resolved_target.parents:
                raise SystemExit(f"unsafe symlink target: {entry['path']}")
            os.symlink(link_target, target)
            continue
        source = bundle / "objects" / entry["sha256"][:2] / entry["sha256"]
        if source.stat().st_size != entry["bytes"] or digest(source) != entry["sha256"]:
            raise SystemExit(f"object verification failed: {entry['sha256']}")
        shutil.copyfile(source, target)
        target.chmod(entry["mode"])
        os.utime(target, ns=(entry["mtime_ns"], entry["mtime_ns"]))
    print(json.dumps({"restored": len(manifest["files"]), "label": manifest["label"]}, sort_keys=True))


if __name__ == "__main__":
    main()
