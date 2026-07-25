#!/usr/bin/env python3
"""Build a deterministic, local-only custody archive.

The custody archive deliberately keeps non-redacted source evidence. It must
never be used as a GitHub Release input. Public assets are stored once in the
public Release; only non-public reference assets receive an additional
redacted local archive.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
from typing import Any

from prepare_public_release import archive_asset, read_jsonl


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_rows(selection: Path, operator_selection: Path | None) -> list[dict[str, Any]]:
    rows = read_jsonl(selection)
    if operator_selection is not None:
        rows.extend(read_jsonl(operator_selection))
    ids = [str(row["asset_id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("custody selection contains duplicate asset_id")
    return sorted(rows, key=lambda row: str(row["asset_id"]))


def validate_source(root: Path, expected: set[str], label: str) -> None:
    actual = {path.name for path in root.iterdir() if path.is_dir()}
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(f"{label} asset set mismatch: missing={missing}, extra={extra}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--operator-selection", type=Path)
    parser.add_argument("--public-selection", type=Path, required=True)
    parser.add_argument("--raw-assets", type=Path, required=True)
    parser.add_argument("--redacted-assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--compresslevel", type=int, default=1, choices=range(1, 10))
    args = parser.parse_args()

    rows = selected_rows(args.selection, args.operator_selection)
    all_ids = {str(row["asset_id"]) for row in rows}
    public_ids = {str(row["asset_id"]) for row in read_jsonl(args.public_selection)}
    if not public_ids <= all_ids:
        raise ValueError(f"public selection is not a custody subset: {sorted(public_ids - all_ids)}")
    validate_source(args.raw_assets, all_ids, "raw")
    validate_source(args.redacted_assets, all_ids, "redacted")

    raw_output = args.output / "private/raw-worlds"
    reference_output = args.output / "private/redacted-reference"
    raw_output.mkdir(parents=True, exist_ok=True)
    reference_output.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[str, str, str, int, str, dict[str, Any]]] = []
    for row in rows:
        asset_id = str(row["asset_id"])
        jobs.append((
            str(args.raw_assets / asset_id),
            f"raw-worlds/{asset_id}",
            str(raw_output / f"{asset_id}.raw.tar.gz"),
            args.compresslevel,
            "raw_nonredacted",
            row,
        ))
        if asset_id not in public_ids:
            jobs.append((
                str(args.redacted_assets / asset_id),
                f"redacted-reference/{asset_id}",
                str(reference_output / f"{asset_id}.redacted.tar.gz"),
                args.compresslevel,
                "redacted_local_reference",
                row,
            ))

    records: list[dict[str, Any]] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(archive_asset, source, arcroot, output, level): (kind, row, output)
            for source, arcroot, output, level, kind, row in jobs
        }
        for future in concurrent.futures.as_completed(futures):
            kind, row, output = futures[future]
            archive = future.result()
            path = Path(output)
            record = {
                "schema_version": 1,
                "asset_id": str(row["asset_id"]),
                "run_id": str(row["run_id"]),
                "publication_tier": row.get("publication_tier"),
                "terminal_status": row.get("terminal_status"),
                "custody_kind": kind,
                "sensitive": kind == "raw_nonredacted",
                "archive": path.relative_to(args.output).as_posix(),
                "bytes": archive["bytes"],
                "sha256": archive["sha256"],
            }
            records.append({key: value for key, value in record.items() if value is not None})
            print(json.dumps({"kind": "custody_archive_complete", **record}, sort_keys=True), flush=True)

    records.sort(key=lambda row: (str(row["asset_id"]), str(row["custody_kind"])))
    catalog_dir = args.output / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_dir / "local-custody.jsonl"
    catalog_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    manifest_files = [
        {
            "path": str(row["archive"]),
            "bytes": int(row["bytes"]),
            "sha256": str(row["sha256"]),
        }
        for row in records
    ]
    manifest_files.append({
        "path": catalog_path.relative_to(args.output).as_posix(),
        "bytes": catalog_path.stat().st_size,
        "sha256": sha256(catalog_path),
    })
    manifest = {
        "schema_version": 1,
        "hash": "sha256",
        "raw_nonredacted_assets": len(rows),
        "public_redacted_assets_stored_in_github_release": len(public_ids),
        "local_redacted_reference_assets": len(rows) - len(public_ids),
        "files": sorted(manifest_files, key=lambda row: str(row["path"])),
    }
    (catalog_dir / "CUSTODY_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "archives": len(records),
        "raw_assets": len(rows),
        "redacted_reference_assets": len(rows) - len(public_ids),
        "archive_bytes": sum(int(row["bytes"]) for row in records),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
