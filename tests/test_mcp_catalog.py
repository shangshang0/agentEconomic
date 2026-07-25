from __future__ import annotations

import json
from pathlib import Path

from agent_economic_mcp.catalog import asset_path, find_asset, find_world, load_assets, load_catalog, world_path
from agent_economic_mcp.server import list_assets_impl, registered_analysis_plan_impl, verify_release_manifest_impl


def test_catalog_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "data/catalog"
    path.mkdir(parents=True)
    row = {"run_id": "v2-test", "terminal_status": "complete"}
    (path / "worlds.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert load_catalog(tmp_path) == [row]
    assert find_world("v2-test", tmp_path) == row


def test_asset_catalog_and_release_paths(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "data/catalog"
    path.mkdir(parents=True)
    world = {
        "run_id": "v2-test",
        "canonical_asset_id": "v2-test-complete",
        "release_tag": "data-v1",
        "release_path": "worlds/v2-test-complete",
    }
    assets = [
        {"asset_id": "v2-test-failed", "run_id": "v2-test", "release_tag": "data-v1", "release_path": "reference/v2-test-failed"},
        {"asset_id": "v2-test-complete", "run_id": "v2-test", "release_tag": "data-v1", "release_path": "worlds/v2-test-complete"},
    ]
    (path / "worlds.jsonl").write_text(json.dumps(world) + "\n", encoding="utf-8")
    (path / "assets.jsonl").write_text("".join(json.dumps(row) + "\n" for row in assets), encoding="utf-8")
    assert load_assets(tmp_path) == assets
    assert find_asset("v2-test-failed", tmp_path) == assets[0]
    assert world_path("v2-test", tmp_path) == tmp_path / "data/releases/data-v1/extracted/worlds/v2-test-complete"
    assert asset_path("v2-test-failed", tmp_path) == tmp_path / "data/releases/data-v1/extracted/reference/v2-test-failed"
    monkeypatch.setenv("AGENT_ECONOMIC_REPO", str(tmp_path))
    assert [row["asset_id"] for row in list_assets_impl(run_id="v2-test")] == [
        "v2-test-failed",
        "v2-test-complete",
    ]


def test_registered_analysis_plan(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "data/catalog"
    path.mkdir(parents=True)
    rows = [
        {"run_id": "v2-a", "evidence_tier": "confirmatory", "analysis_eligible": True},
        {"run_id": "v2-b", "evidence_tier": "reference", "analysis_eligible": False},
    ]
    (path / "worlds.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setenv("AGENT_ECONOMIC_REPO", str(tmp_path))
    assert registered_analysis_plan_impl()["run_ids"] == ["v2-a"]


def test_verify_release_manifest(monkeypatch, tmp_path: Path) -> None:
    import hashlib

    release = tmp_path / "data/release"
    release.mkdir(parents=True)
    payload = release / "payload.txt"
    payload.write_text("evidence\n", encoding="utf-8")
    manifest = {
        "files": [{
            "path": "payload.txt",
            "bytes": payload.stat().st_size,
            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
        }]
    }
    (release / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("AGENT_ECONOMIC_REPO", str(tmp_path))
    assert verify_release_manifest_impl("data/release/MANIFEST.json")["valid"] is True
