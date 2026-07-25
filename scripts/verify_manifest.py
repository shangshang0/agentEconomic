#!/usr/bin/env python3
"""Verify a deterministic SHA-256 file manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe manifest path: {value!r}")
    return path


def verify(manifest_path: Path, root: Path | None = None, reject_extra: bool = False) -> list[str]:
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = document.get("files") if isinstance(document, dict) else None
    if not isinstance(records, list):
        raise ValueError("manifest must contain a files array")
    base = (root or manifest_path.parent).resolve()
    expected: set[str] = set()
    errors: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            errors.append("non-object file record")
            continue
        rel = safe_relative(str(record.get("path", "")))
        rel_text = rel.as_posix()
        if rel_text in expected:
            errors.append(f"duplicate path: {rel_text}")
            continue
        expected.add(rel_text)
        path = base.joinpath(*rel.parts)
        if not path.is_file() or path.is_symlink():
            errors.append(f"missing/non-regular: {rel_text}")
            continue
        size = path.stat().st_size
        if record.get("bytes") != size:
            errors.append(f"size mismatch: {rel_text}")
        if record.get("sha256") != sha256(path):
            errors.append(f"sha256 mismatch: {rel_text}")
    if reject_extra:
        actual = {
            p.relative_to(base).as_posix()
            for p in base.rglob("*")
            if p.is_file() and not p.is_symlink() and p.resolve() != manifest_path.resolve()
        }
        for rel in sorted(actual - expected):
            errors.append(f"unexpected file: {rel}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--reject-extra", action="store_true")
    args = parser.parse_args()
    errors = verify(args.manifest, args.root, args.reject_extra)
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(f"manifest verification FAILED ({len(errors)} errors)")
    print("manifest verification PASS")


if __name__ == "__main__":
    main()
