from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


def repository_root() -> Path:
    configured = os.environ.get("AGENT_ECONOMIC_REPO")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def load_jsonl_catalog(name: str, root: Path | None = None, identity: str = "run_id") -> list[dict[str, Any]]:
    path = (root or repository_root()) / "data/catalog" / name
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict) or not isinstance(value.get(identity), str):
                raise ValueError(f"invalid catalog row {number}: {path}")
            rows.append(value)
    return rows


def load_catalog(root: Path | None = None) -> list[dict[str, Any]]:
    return load_jsonl_catalog("worlds.jsonl", root)


def load_assets(root: Path | None = None) -> list[dict[str, Any]]:
    return load_jsonl_catalog("assets.jsonl", root, "asset_id")


def find_world(run_id: str, root: Path | None = None) -> dict[str, Any]:
    matches = [row for row in load_catalog(root) if row.get("run_id") == run_id]
    if len(matches) != 1:
        raise KeyError(f"expected one catalog row for {run_id}, found {len(matches)}")
    return matches[0]


def find_asset(asset_id: str, root: Path | None = None) -> dict[str, Any]:
    matches = [row for row in load_assets(root) if row.get("asset_id") == asset_id]
    if len(matches) != 1:
        raise KeyError(f"expected one asset row for {asset_id}, found {len(matches)}")
    return matches[0]


def release_path(row: dict[str, Any], root: Path | None = None) -> Path:
    base = root or repository_root()
    tag = str(row.get("release_tag") or "public-data-v1")
    relative = str(
        row.get("release_path")
        or f"worlds/{row.get('canonical_asset_id') or row.get('asset_id') or row['run_id']}"
    )
    return base / "data/releases" / tag / "extracted" / relative


def world_path(run_id: str, root: Path | None = None) -> Path:
    return release_path(find_world(run_id, root), root)


def asset_path(asset_id: str, root: Path | None = None) -> Path:
    return release_path(find_asset(asset_id, root), root)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8", errors="strict") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value.setdefault("_line", number)
                yield value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_worlds(
    *,
    tier: str | None = None,
    condition: str | None = None,
    model: str | None = None,
    terminal_status: str | None = None,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    rows = load_catalog(root)
    filters = {
        "evidence_tier": tier,
        "condition": condition,
        "model": model,
        "terminal_status": terminal_status,
    }
    for key, expected in filters.items():
        if expected is not None:
            rows = [row for row in rows if str(row.get(key)) == expected]
    return rows
