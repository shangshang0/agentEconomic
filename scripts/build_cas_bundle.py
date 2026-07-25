#!/usr/bin/env python3
"""Store a directory losslessly as deduplicated content-addressed objects."""

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
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()
    if not source.is_dir():
        raise SystemExit("source must be a directory")
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit("destination must not exist or must be empty")
    if destination == source or source in destination.parents:
        raise SystemExit("destination cannot be inside source")
    objects = destination / "objects"
    objects.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, object]] = []
    logical_bytes = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source).as_posix()
        if path.is_symlink():
            link_target = os.readlink(path)
            resolved_target = (path.parent / link_target).resolve()
            if os.path.isabs(link_target) or source not in resolved_target.parents:
                raise SystemExit(f"unsafe source symlink: {relative}")
            files.append({"path": relative, "type": "symlink", "target": link_target})
            continue
        if not path.is_file():
            continue
        stat = path.stat()
        sha256 = digest(path)
        target = objects / sha256[:2] / sha256
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            target.chmod(0o444)
        logical_bytes += stat.st_size
        files.append(
            {
                "path": relative,
                "type": "file",
                "sha256": sha256,
                "bytes": stat.st_size,
                "mode": stat.st_mode & 0o777,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    object_files = [path for path in objects.rglob("*") if path.is_file()]
    stored_bytes = sum(path.stat().st_size for path in object_files)
    manifest = {
        "schema_version": 1,
        "hash": "sha256",
        "label": args.label,
        "logical_files": len(files),
        "unique_objects": len(object_files),
        "logical_bytes": logical_bytes,
        "stored_bytes": stored_bytes,
        "files": files,
    }
    (destination / "CAS_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "logical_files": len(files),
                "unique_objects": len(object_files),
                "logical_bytes": logical_bytes,
                "stored_bytes": stored_bytes,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
