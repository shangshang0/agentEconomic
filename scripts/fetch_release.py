#!/usr/bin/env python3
"""Download, verify, and safely extract versioned public data assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

REPOSITORY = "shangshang0/agentEconomic"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request(url: str) -> urllib.request.Request:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "agentEconomic-auditor"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with tarfile.open(archive, "r:*") as handle:
        members = handle.getmembers()
        for member in members:
            rel = PurePosixPath(member.name)
            if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
                raise ValueError(f"unsafe archive member: {member.name!r}")
            if member.name in seen:
                raise ValueError(f"duplicate archive member: {member.name}")
            seen.add(member.name)
            if not (member.isdir() or member.isfile()):
                raise ValueError(f"only regular files/directories are allowed: {member.name}")
        for member in members:
            relative = PurePosixPath(member.name)
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise ValueError(f"archive would overwrite an existing file: {member.name}")
            source = handle.extractfile(member)
            if source is None:
                raise ValueError(f"archive member has no file payload: {member.name}")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            descriptor = os.open(target, flags, member.mode & 0o777 or 0o600)
            try:
                with source, os.fdopen(descriptor, "wb") as output:
                    descriptor = -1
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--all", action="store_true", dest="all_assets")
    parser.add_argument("--asset", action="append", default=[])
    parser.add_argument("--index", type=Path, default=Path("data/catalog/releases.json"))
    parser.add_argument("--destination", type=Path, default=Path("data/releases"))
    parser.add_argument(
        "--source-directory",
        type=Path,
        help="verify local release assets instead of downloading them (pre-upload audit)",
    )
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding="utf-8"))
    release = next((item for item in index["releases"] if item["tag"] == args.release), None)
    if release is None:
        raise SystemExit(f"release not found in index: {args.release}")
    selected = release["assets"] if args.all_assets else [a for a in release["assets"] if a["name"] in args.asset]
    if not selected:
        raise SystemExit("no assets selected; use --all or --asset NAME")
    target = args.destination / args.release
    target.mkdir(parents=True, exist_ok=True)
    for asset in selected:
        name = PurePosixPath(asset["name"])
        if len(name.parts) != 1 or name.name != asset["name"]:
            raise ValueError("asset name must be a basename")
        output = target / name.name
        if args.source_directory is not None:
            source = args.source_directory / name.name
            if not source.is_file():
                raise FileNotFoundError(f"local release asset is missing: {source}")
            shutil.copyfile(source, output)
        else:
            url = asset.get("url") or f"https://github.com/{REPOSITORY}/releases/download/{args.release}/{name.name}"
            with urllib.request.urlopen(request(url)) as response, output.open("wb") as handle:
                shutil.copyfileobj(response, handle, length=1024 * 1024)
        if output.stat().st_size != asset["bytes"] or sha256(output) != asset["sha256"]:
            output.unlink(missing_ok=True)
            raise SystemExit(f"checksum failure: {name.name}")
        if asset.get("extract", True):
            safe_extract(output, target / "extracted")
        print(f"verified {name.name}")


if __name__ == "__main__":
    main()
