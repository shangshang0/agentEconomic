#!/usr/bin/env python3
"""Audit the run-level world catalog and the physical-asset catalog."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

TIERS = {"confirmatory", "mechanism", "discovery", "recovered", "reference"}
WORLD_REQUIRED = {"run_id", "evidence_tier", "analysis_eligible", "condition", "terminal_status"}
ASSET_REQUIRED = {
    "asset_id",
    "asset_kind",
    "run_id",
    "evidence_tier",
    "terminal_status",
    "trace_status",
    "release_path",
}
RUN_ID = re.compile(r"^(?:v2-|run-)[A-Za-z0-9][A-Za-z0-9._-]*$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def rows(path: Path):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            yield number, json.loads(line)


def safe_relative(value: object) -> bool:
    path = PurePosixPath(str(value))
    return bool(path.parts) and not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def state_and_events(asset_root: Path) -> tuple[Path | None, Path | None]:
    candidates = (
        (
            asset_root / "data-v2/authority-world-v2.state.json",
            asset_root / "data-v2/authority-world-v2.events.jsonl",
        ),
        (
            asset_root / "data/authority-world-v1.state.json",
            asset_root / "data/authority-world-v1.events.jsonl",
        ),
    )
    for state, events in candidates:
        if state.is_file() or events.is_file():
            return state, events
    return None, None


def _asset_location(row: dict[str, Any], release_root: Path) -> Path:
    return release_root / PurePosixPath(str(row["release_path"]))


def audit(
    path: Path,
    release_root: Path | None = None,
    assets_path: Path | None = None,
) -> list[str]:
    """Return semantic errors without mutating catalogs or extracted evidence."""

    errors: list[str] = []
    worlds: dict[str, dict[str, Any]] = {}
    for number, row in rows(path):
        if not isinstance(row, dict):
            errors.append(f"world line {number}: row is not an object")
            continue
        missing = WORLD_REQUIRED - row.keys()
        if missing:
            errors.append(f"world line {number}: missing {','.join(sorted(missing))}")
            continue
        run_id = row["run_id"]
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            errors.append(f"world line {number}: invalid run_id")
            continue
        if run_id in worlds:
            errors.append(f"world line {number}: duplicate run_id {run_id}")
        worlds[run_id] = row
        if row["evidence_tier"] not in TIERS:
            errors.append(f"world line {number}: invalid evidence_tier")
        if not isinstance(row["analysis_eligible"], bool):
            errors.append(f"world line {number}: analysis_eligible is not boolean")
        if row["evidence_tier"] == "reference" and row["analysis_eligible"]:
            errors.append(f"world line {number}: reference world cannot be analysis eligible")
        if row["analysis_eligible"] and row["terminal_status"] != "complete":
            errors.append(f"world line {number}: eligible world is not complete")

    assets: dict[str, dict[str, Any]] = {}
    if assets_path and assets_path.is_file():
        for number, row in rows(assets_path):
            if not isinstance(row, dict):
                errors.append(f"asset line {number}: row is not an object")
                continue
            missing = ASSET_REQUIRED - row.keys()
            if missing:
                errors.append(f"asset line {number}: missing {','.join(sorted(missing))}")
                continue
            asset_id = row["asset_id"]
            if not isinstance(asset_id, str) or not IDENTIFIER.fullmatch(asset_id):
                errors.append(f"asset line {number}: invalid asset_id")
                continue
            if asset_id in assets:
                errors.append(f"asset line {number}: duplicate asset_id {asset_id}")
            assets[asset_id] = row
            if row["evidence_tier"] not in TIERS:
                errors.append(f"asset line {number}: invalid evidence_tier")
            if not safe_relative(row["release_path"]):
                errors.append(f"asset line {number}: unsafe release_path")
            run_id = row["run_id"]
            if row["asset_kind"] != "operator_history" and run_id not in worlds:
                errors.append(f"asset line {number}: unknown world run_id {run_id}")

    for run_id, world in worlds.items():
        canonical_id = world.get("canonical_asset_id")
        if canonical_id is None:
            continue
        asset = assets.get(str(canonical_id))
        if asset is None:
            errors.append(f"{run_id}: canonical_asset_id not found: {canonical_id}")
            continue
        if asset.get("run_id") != run_id:
            errors.append(f"{run_id}: canonical asset belongs to {asset.get('run_id')}")
        if world["analysis_eligible"] and asset.get("terminal_status") != "complete":
            errors.append(f"{run_id}: eligible canonical asset is not complete")

    if release_root:
        for run_id, world in worlds.items():
            canonical_id = world.get("canonical_asset_id")
            asset = assets.get(str(canonical_id)) if canonical_id is not None else None
            if asset is None:
                fallback = release_root / "worlds" / run_id
                if not fallback.exists():
                    continue
                asset_root = fallback
            else:
                asset_root = _asset_location(asset, release_root)
                if not asset_root.exists():
                    errors.append(f"{run_id}: canonical asset path is missing")
                    continue
            state_path, events_path = state_and_events(asset_root)
            if state_path and events_path and state_path.is_file() and events_path.is_file():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                count = sum(1 for line in events_path.open(encoding="utf-8") if line.strip())
                if state.get("event_seq") != count:
                    errors.append(f"{run_id}: state event_seq != nonblank event lines")
            elif world["analysis_eligible"]:
                errors.append(f"{run_id}: downloaded eligible world lacks state/events")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--release-root", type=Path, help="extracted release root containing release_path entries")
    args = parser.parse_args()
    assets_path = args.assets
    if assets_path is None:
        sibling = args.catalog.with_name("assets.jsonl")
        assets_path = sibling if sibling.is_file() else None
    errors = audit(args.catalog, args.release_root, assets_path)
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(f"catalog audit FAILED ({len(errors)} errors)")
    asset_count = sum(1 for _ in rows(assets_path)) if assets_path and assets_path.is_file() else 0
    print(f"catalog audit PASS ({sum(1 for _ in rows(args.catalog))} worlds, {asset_count} assets)")


if __name__ == "__main__":
    main()
