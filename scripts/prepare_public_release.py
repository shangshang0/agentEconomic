#!/usr/bin/env python3
"""Build sanitized catalogs and deterministic GitHub Release archives."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


MAX_GITHUB_ASSET_BYTES = 1_900_000_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"non-object selection row {number}: {path}")
        rows.append(value)
    return rows


def load_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def evidence_tier(publication_tier: str) -> tuple[str, bool]:
    if publication_tier.startswith("canonical_confirmatory"):
        return "confirmatory", True
    if publication_tier.startswith("canonical_mechanism"):
        return "mechanism", True
    return "reference", False


def release_path(row: dict[str, Any]) -> str:
    asset_id = str(row["asset_id"])
    if row.get("asset_kind") == "operator_history":
        return f"operator/{asset_id}.cas"
    publication_tier = str(row.get("publication_tier") or "reference")
    prefix = "worlds" if publication_tier.startswith("canonical_") else "reference"
    return f"{prefix}/{asset_id}"


def trace_status(asset_root: Path) -> str:
    document = load_object(asset_root / "TRACE_COMPLETENESS.json")
    if not document:
        return "not_applicable" if (asset_root / "CAS_MANIFEST.json").is_file() else "unknown"
    return "complete" if document.get("complete") is True else "partial"


def recovery_amendments(asset_root: Path) -> list[str]:
    values: list[str] = []
    for path in sorted(asset_root.rglob("*")):
        if not path.is_file():
            continue
        folded = path.name.casefold()
        if "amendment" not in folded or path.suffix.casefold() not in {".json", ".md"}:
            continue
        values.append(path.relative_to(asset_root).as_posix())
    return values


def public_asset_row(selection: dict[str, Any], public_root: Path, release_tag: str) -> dict[str, Any]:
    asset_id = str(selection["asset_id"])
    asset_root = public_root / asset_id
    if not asset_root.is_dir():
        raise FileNotFoundError(f"selected public asset is missing: {asset_id}")
    publication_tier = str(selection.get("publication_tier") or "reference")
    tier, eligible = evidence_tier(publication_tier)
    metadata = load_object(asset_root / "run_metadata.json")
    terminal = selection.get("terminal_status") or metadata.get("terminal_status") or "unknown"
    path = release_path(selection)
    archive = f"{asset_id}.tar.gz"
    result = {
        "schema_version": 1,
        "asset_id": asset_id,
        "asset_kind": str(selection.get("asset_kind") or "world"),
        "run_id": str(selection["run_id"]),
        "evidence_tier": tier,
        "analysis_eligible": bool(eligible and terminal == "complete"),
        "publication_tier": publication_tier,
        "terminal_status": terminal,
        "trace_status": trace_status(asset_root),
        "trace_schema": selection.get("trace_schema"),
        "model": metadata.get("model") or selection.get("model"),
        "seed": metadata.get("seed") if metadata.get("seed") is not None else selection.get("seed"),
        "condition": metadata.get("condition") or metadata.get("config") or "unknown",
        "selection_reason": selection.get("selection_reason"),
        "release_tag": release_tag,
        "release_part": archive,
        "release_path": path,
        "recovery_amendments": recovery_amendments(asset_root),
    }
    return {key: value for key, value in result.items() if value is not None}


def canonical_rank(row: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        int(row.get("terminal_status") == "complete"),
        int(str(row.get("publication_tier", "")).startswith("canonical_")),
        int(row.get("trace_status") == "complete"),
        str(row["asset_id"]),
    )


def world_rows(assets: Iterable[dict[str, Any]], public_root: Path) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in assets:
        if row.get("asset_kind") != "operator_history":
            grouped[str(row["run_id"])].append(row)
    results: list[dict[str, Any]] = []
    for run_id, candidates in grouped.items():
        canonical = max(candidates, key=canonical_rank)
        metadata = load_object(public_root / str(canonical["asset_id"]) / "run_metadata.json")
        result = {
            "schema_version": 1,
            "run_id": run_id,
            "canonical_asset_id": canonical["asset_id"],
            "evidence_tier": canonical["evidence_tier"],
            "analysis_eligible": canonical["analysis_eligible"],
            "publication_tier": canonical["publication_tier"],
            "terminal_status": canonical["terminal_status"],
            "trace_status": canonical["trace_status"],
            "condition": canonical["condition"],
            "phase": metadata.get("phase"),
            "model": canonical.get("model"),
            "seed": canonical.get("seed"),
            "config": metadata.get("config"),
            "config_hash": metadata.get("config_hash"),
            "protocol_hash": metadata.get("protocol_hash"),
            "task_manifest_hash": metadata.get("task_manifest_hash"),
            "release_tag": canonical["release_tag"],
            "release_part": canonical["release_part"],
            "release_path": canonical["release_path"],
            "recovery_amendments": canonical.get("recovery_amendments", []),
        }
        results.append({key: value for key, value in result.items() if value is not None})
    return sorted(results, key=lambda row: str(row["run_id"]))


def normalized(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.pax_headers = {}
    return info


def archive_asset(source: str, arcroot: str, output: str, compresslevel: int) -> dict[str, Any]:
    source_path = Path(source)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=output_path.name + ".", dir=output_path.parent, delete=False) as temp:
        temporary = Path(temp.name)
        with gzip.GzipFile(filename="", mode="wb", fileobj=temp, compresslevel=compresslevel, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                paths = [source_path, *sorted(source_path.rglob("*"))]
                for path in paths:
                    if path.is_symlink() or not (path.is_dir() or path.is_file()):
                        raise ValueError(f"release input contains unsupported entry: {path}")
                    relative = path.relative_to(source_path)
                    name = PurePosixPath(arcroot, *relative.parts).as_posix()
                    info = normalized(archive.gettarinfo(str(path), arcname=name))
                    if path.is_file():
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
                    else:
                        archive.addfile(info)
    os.replace(temporary, output_path)
    return {
        "name": output_path.name,
        "bytes": output_path.stat().st_size,
        "sha256": sha256(output_path),
        "extract": True,
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def aggregate_manifest(assets: list[dict[str, Any]], public_root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for row in assets:
        asset_root = public_root / str(row["asset_id"])
        manifest_path = asset_root / "PUBLIC_MANIFEST.json"
        document = load_object(manifest_path)
        records = document.get("files")
        if not isinstance(records, list):
            raise ValueError(f"asset has no PUBLIC_MANIFEST.json: {row['asset_id']}")
        prefix = PurePosixPath(str(row["release_path"]))
        for record in records:
            relative = PurePosixPath(str(record["path"]))
            files.append({
                "path": (prefix / relative).as_posix(),
                "bytes": record["bytes"],
                "sha256": record["sha256"],
            })
        files.append({
            "path": (prefix / "PUBLIC_MANIFEST.json").as_posix(),
            "bytes": manifest_path.stat().st_size,
            "sha256": sha256(manifest_path),
        })
    files.sort(key=lambda row: str(row["path"]))
    if len({str(row["path"]) for row in files}) != len(files):
        raise ValueError("aggregate manifest contains duplicate paths")
    return {"schema_version": 1, "hash": "sha256", "files": files}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--operator-selection", type=Path)
    parser.add_argument("--public-assets", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--release-tag", default="public-data-v1")
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--compresslevel", type=int, default=1, choices=range(1, 10))
    parser.add_argument("--max-asset-bytes", type=int, default=MAX_GITHUB_ASSET_BYTES)
    args = parser.parse_args()

    selections = read_jsonl(args.selection)
    if args.operator_selection:
        selections.extend(read_jsonl(args.operator_selection))
    asset_ids = [str(row["asset_id"]) for row in selections]
    if len(set(asset_ids)) != len(asset_ids):
        raise SystemExit("selection contains duplicate asset_id")
    actual = {path.name for path in args.public_assets.iterdir() if path.is_dir()}
    missing = sorted(set(asset_ids) - actual)
    extra = sorted(actual - set(asset_ids))
    if missing or extra:
        raise SystemExit(f"public asset set mismatch: missing={missing}, extra={extra}")

    assets = [public_asset_row(row, args.public_assets, args.release_tag) for row in selections]
    assets.sort(key=lambda row: str(row["asset_id"]))
    worlds = world_rows(assets, args.public_assets)

    catalog = args.repository / "data/catalog"
    manifests = args.repository / "data/manifests"
    write_jsonl(catalog / "assets.jsonl", assets)
    write_jsonl(catalog / "worlds.jsonl", worlds)
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / "public-data-manifest.json").write_text(
        json.dumps(aggregate_manifest(assets, args.public_assets), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    args.archives.mkdir(parents=True, exist_ok=True)
    jobs = []
    for row in assets:
        jobs.append((
            str(args.public_assets / str(row["asset_id"])),
            str(row["release_path"]),
            str(args.archives / str(row["release_part"])),
            args.compresslevel,
        ))
    release_assets: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(archive_asset, *job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            if int(record["bytes"]) > args.max_asset_bytes:
                raise SystemExit(f"GitHub asset exceeds size ceiling: {record['name']}")
            release_assets.append(record)
            print(json.dumps({"kind": "archive_complete", **record}, sort_keys=True), flush=True)
    release_assets.sort(key=lambda row: str(row["name"]))
    index = {
        "schema_version": 1,
        "repository": "shangshang0/agentEconomic",
        "releases": [{"tag": args.release_tag, "assets": release_assets}],
    }
    (catalog / "releases.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "assets": len(assets),
        "worlds": len(worlds),
        "archive_bytes": sum(int(row["bytes"]) for row in release_assets),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
