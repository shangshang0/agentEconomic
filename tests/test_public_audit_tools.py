from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(name: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_secret_scanner_does_not_echo_value(tmp_path: Path) -> None:
    secret = "sk-" + "A" * 32
    (tmp_path / "trace.jsonl").write_text(json.dumps({"value": secret}) + "\n", encoding="utf-8")
    result = run_script("scan_secrets.py", str(tmp_path))
    assert result.returncode == 1
    assert "openai-key" in result.stdout
    assert secret not in result.stdout + result.stderr


def test_redaction_manifest_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source"
    public = tmp_path / "public"
    source.mkdir()
    secret = "runtime-secret-" + "B" * 24
    (source / "events.jsonl").write_text(json.dumps({"authorization": secret}) + "\n", encoding="utf-8")
    (source / ".env").write_text("PRIVATE=" + secret + "\n", encoding="utf-8")
    env = dict(os.environ, TEST_EXPORT_SECRET=secret)
    result = run_script(
        "redact_export.py", str(source), str(public), "--secret-env", "TEST_EXPORT_SECRET", env=env
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert secret not in (public / "events.jsonl").read_text(encoding="utf-8")
    assert not (public / ".env").exists()
    ledger = [json.loads(line) for line in (public / "REDACTION_LEDGER.jsonl").read_text().splitlines()]
    assert ledger[0]["redactions"]["test_export_secret"] == 1
    verify = run_script("verify_manifest.py", str(public / "PUBLIC_MANIFEST.json"), "--root", str(public))
    assert verify.returncode == 0, verify.stdout + verify.stderr


def test_public_manifest_can_cover_post_redaction_audit(tmp_path: Path) -> None:
    root = tmp_path / "public"
    root.mkdir()
    (root / "trace.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "PUBLIC_MANIFEST.json").write_text(
        json.dumps({"schema_version": 1, "redaction_ruleset": "test", "files": []}),
        encoding="utf-8",
    )
    (root / "TRACE_COMPLETENESS.json").write_text("{}\n", encoding="utf-8")
    build = run_script("build_public_manifest.py", str(root))
    assert build.returncode == 0, build.stdout + build.stderr
    manifest = json.loads((root / "PUBLIC_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["redaction_ruleset"] == "test"
    assert {record["path"] for record in manifest["files"]} == {
        "TRACE_COMPLETENESS.json",
        "trace.jsonl",
    }
    verify = run_script(
        "verify_manifest.py",
        str(root / "PUBLIC_MANIFEST.json"),
        "--root",
        str(root),
        "--reject-extra",
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr


def test_redaction_covers_operator_paths_networks_and_embedded_credentials(tmp_path: Path) -> None:
    source = tmp_path / "source"
    public = tmp_path / "public"
    source.mkdir()
    fixture_value = "Sufficient" + "lyLongPassphrase99"
    content = (
        "/Users/operator/private/project\n"
        "gateway=10.24.8.19\n"
        f"gateway_token={fixture_value}\n"
        "-----BEGIN " + "PRIVATE KEY-----\\nsecret-material\\n-----END " + "PRIVATE KEY-----\n"
    )
    (source / "operator.log").write_text(content, encoding="utf-8")
    result = run_script("redact_export.py", str(source), str(public))
    assert result.returncode == 0, result.stdout + result.stderr
    rendered = (public / "operator.log").read_text(encoding="utf-8")
    assert "operator" not in rendered
    assert "10.24.8.19" not in rendered
    assert fixture_value not in rendered
    assert "secret-material" not in rendered
    assert rendered.count("[REDACTED:") >= 4


def test_content_addressed_bundle_deduplicates_and_restores(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one").mkdir()
    (source / "two").mkdir()
    payload = b"same recovery checkpoint\n"
    (source / "one/a.jsonl").write_bytes(payload)
    (source / "two/b.jsonl").write_bytes(payload)
    bundle = tmp_path / "bundle"
    build = run_script("build_cas_bundle.py", str(source), str(bundle), "--label", "test-recovery")
    assert build.returncode == 0, build.stdout + build.stderr
    report = json.loads(build.stdout)
    assert report["logical_files"] == 2
    assert report["unique_objects"] == 1
    restored = tmp_path / "restored"
    restore = run_script("restore_cas_bundle.py", str(bundle), str(restored))
    assert restore.returncode == 0, restore.stdout + restore.stderr
    assert (restored / "one/a.jsonl").read_bytes() == payload
    assert (restored / "two/b.jsonl").read_bytes() == payload


def test_manifest_rejects_traversal(tmp_path: Path) -> None:
    manifest = tmp_path / "MANIFEST.json"
    manifest.write_text(json.dumps({"files": [{"path": "../outside", "bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()}]}))
    result = run_script("verify_manifest.py", str(manifest))
    assert result.returncode != 0


def make_trace_world(root: Path, *, omit_gateway: bool = False) -> Path:
    run_id = "v2-test-complete"
    (root / "data-v2").mkdir(parents=True)
    (root / "gateway-data-v2").mkdir()
    (root / "run_metadata.json").write_text(
        json.dumps({"run_id": run_id, "terminal_status": "complete"}), encoding="utf-8"
    )
    (root / "data-v2/authority-world-v2.state.json").write_text(
        json.dumps({"event_seq": 1, "status": "complete"}), encoding="utf-8"
    )
    (root / "data-v2/authority-world-v2.events.jsonl").write_text(
        json.dumps({"seq": 1, "kind": "world_started"}) + "\n", encoding="utf-8"
    )
    gateway: list[str] = []
    for number in range(1, 7):
        agent = f"A{number}"
        request_id = f"test:{agent}:request"
        call_id = f"call-{agent}"
        base = root / "agent-state-v2" / agent.lower() / "runner-v2/runs" / run_id
        base.mkdir(parents=True)
        response = {
            "kind": "model_response",
            "request_id": request_id,
            "text": f"response from {agent}",
            "function_calls": [{"id": call_id, "name": "sleep", "arguments": {}}],
        }
        receipt = {
            "kind": "tool_result",
            "request_id": request_id,
            "call_id": call_id,
            "name": "sleep",
            "ok": True,
            "result": {"slept": True},
        }
        (base / "audit.raw.jsonl").write_text(
            "\n".join(json.dumps(row) for row in (response, receipt)) + "\n", encoding="utf-8"
        )
        compact_receipt = {"kind": "tool_result", "name": "sleep", "ok": True, "receipt": {}}
        (base / "context.jsonl").write_text(
            "\n".join(json.dumps(row) for row in (response, compact_receipt)) + "\n", encoding="utf-8"
        )
        gateway.append(
            json.dumps(
                {
                    "kind": "exchange",
                    "agent_id": agent,
                    "request_id": request_id,
                    "request": {"messages": []},
                    "response": {"text": response["text"]},
                }
            )
        )
    if not omit_gateway:
        (root / "gateway-data-v2/authority-world-v1.gateway.jsonl").write_text(
            "\n".join(gateway) + "\n", encoding="utf-8"
        )
    return root


def test_trace_completeness_accepts_compact_context_receipts(tmp_path: Path) -> None:
    world = make_trace_world(tmp_path / "world")
    result = run_script("audit_trace_completeness.py", str(world))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["complete"] is True
    assert report["audit_passed"] is True
    assert report["model_responses"] == 6
    assert report["function_calls"] == report["tool_results"] == 6


def test_trace_partial_is_never_mislabeled_complete(tmp_path: Path) -> None:
    world = make_trace_world(tmp_path / "world", omit_gateway=True)
    strict = run_script("audit_trace_completeness.py", str(world))
    assert strict.returncode == 1
    partial = run_script("audit_trace_completeness.py", str(world), "--allow-partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    report = json.loads(partial.stdout)
    assert report["complete"] is False
    assert report["audit_passed"] is True
    assert report["partial_allowed"] is True
    assert "gateway trace is missing" in report["errors"]


def test_trace_partial_records_malformed_jsonl_without_crashing(tmp_path: Path) -> None:
    world = make_trace_world(tmp_path / "world")
    gateway = world / "gateway-data-v2/authority-world-v1.gateway.jsonl"
    lines = gateway.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("response from A1", "response\x01from A1")
    gateway.write_text("\n".join(lines) + "\n", encoding="utf-8")

    strict = run_script("audit_trace_completeness.py", str(world))
    assert strict.returncode == 1, strict.stdout + strict.stderr
    partial = run_script("audit_trace_completeness.py", str(world), "--allow-partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    report = json.loads(partial.stdout)
    assert report["complete"] is False
    assert any(
        error.startswith("gateway JSONL: invalid JSON at line 1")
        for error in report["errors"]
    )


def test_trace_reports_the_identity_of_a_missing_tool_result(tmp_path: Path) -> None:
    world = make_trace_world(tmp_path / "world")
    audit = world / "agent-state-v2/a1/runner-v2/runs/v2-test-complete/audit.raw.jsonl"
    rows = audit.read_text(encoding="utf-8").splitlines()
    audit.write_text(rows[0] + "\n", encoding="utf-8")
    context = world / "agent-state-v2/a1/runner-v2/runs/v2-test-complete/context.jsonl"
    context.write_text(rows[0] + "\n", encoding="utf-8")
    partial = run_script("audit_trace_completeness.py", str(world), "--allow-partial")
    assert partial.returncode == 0, partial.stdout + partial.stderr
    report = json.loads(partial.stdout)
    assert report["complete"] is False
    assert report["missing_result_calls"] == [
        {
            "agent_id": "A1",
            "call_id": "call-A1",
            "request_id": "test:A1:request",
            "tool": "sleep",
        }
    ]


def test_trace_completeness_supports_legacy_runner_streams(tmp_path: Path) -> None:
    world = make_trace_world(tmp_path / "v2")
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "run_metadata.json").write_bytes((world / "run_metadata.json").read_bytes())
    (legacy / "data").mkdir()
    (legacy / "gateway-data").mkdir()
    (legacy / "data/authority-world-v1.state.json").write_bytes(
        (world / "data-v2/authority-world-v2.state.json").read_bytes()
    )
    (legacy / "data/authority-world-v1.events.jsonl").write_bytes(
        (world / "data-v2/authority-world-v2.events.jsonl").read_bytes()
    )
    (legacy / "gateway-data/authority-world-v1.gateway.jsonl").write_bytes(
        (world / "gateway-data-v2/authority-world-v1.gateway.jsonl").read_bytes()
    )
    run_id = "v2-test-complete"
    for number in range(1, 7):
        source = world / "agent-state-v2" / f"a{number}" / "runner-v2/runs" / run_id / "audit.raw.jsonl"
        destination = legacy / "agent-state" / f"a{number}" / "runner/events.jsonl"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(source.read_bytes())
    result = run_script("audit_trace_completeness.py", str(legacy))
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["complete"] is True
    assert report["trace_schema_generation"] == "v1"
    assert report["context_streams_emitted"] is False
    assert all(agent["context_rows"] is None for agent in report["agents"].values())


def test_catalog_separates_unique_worlds_from_historical_assets(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    worlds = [
        {
            "run_id": "run-2026071901-legacy",
            "evidence_tier": "reference",
            "analysis_eligible": False,
            "condition": "legacy-r1",
            "terminal_status": "complete",
            "canonical_asset_id": "legacy-complete",
        },
        {
            "run_id": "v2-2026100101-history",
            "evidence_tier": "discovery",
            "analysis_eligible": True,
            "condition": "I1",
            "terminal_status": "complete",
            "canonical_asset_id": "history-complete",
        },
    ]
    assets = [
        {
            "asset_id": "legacy-complete",
            "asset_kind": "world",
            "run_id": "run-2026071901-legacy",
            "evidence_tier": "reference",
            "terminal_status": "complete",
            "trace_status": "partial",
            "release_path": "reference/legacy-complete",
        },
        {
            "asset_id": "history-failed",
            "asset_kind": "world",
            "run_id": "v2-2026100101-history",
            "evidence_tier": "reference",
            "terminal_status": "technical_failed",
            "trace_status": "partial",
            "release_path": "reference/history-failed",
        },
        {
            "asset_id": "history-complete",
            "asset_kind": "world",
            "run_id": "v2-2026100101-history",
            "evidence_tier": "discovery",
            "terminal_status": "complete",
            "trace_status": "complete",
            "release_path": "worlds/history-complete",
        },
        {
            "asset_id": "operator-history",
            "asset_kind": "operator_history",
            "run_id": "operator-history-frank-controls",
            "evidence_tier": "reference",
            "terminal_status": "reference",
            "trace_status": "not_applicable",
            "release_path": "operator/operator-history.cas",
        },
    ]
    (catalog / "worlds.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in worlds), encoding="utf-8"
    )
    (catalog / "assets.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in assets), encoding="utf-8"
    )
    result = run_script(
        "audit_catalog.py",
        str(catalog / "worlds.jsonl"),
        "--assets",
        str(catalog / "assets.jsonl"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 worlds, 4 assets" in result.stdout


def test_catalog_rejects_unsafe_asset_release_path(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    world = {
        "run_id": "v2-test",
        "evidence_tier": "reference",
        "analysis_eligible": False,
        "condition": "test",
        "terminal_status": "technical_failed",
    }
    asset = {
        "asset_id": "bad-asset",
        "asset_kind": "world",
        "run_id": "v2-test",
        "evidence_tier": "reference",
        "terminal_status": "technical_failed",
        "trace_status": "partial",
        "release_path": "../escape",
    }
    (catalog / "worlds.jsonl").write_text(json.dumps(world) + "\n", encoding="utf-8")
    (catalog / "assets.jsonl").write_text(json.dumps(asset) + "\n", encoding="utf-8")
    result = run_script(
        "audit_catalog.py",
        str(catalog / "worlds.jsonl"),
        "--assets",
        str(catalog / "assets.jsonl"),
    )
    assert result.returncode != 0
    assert "unsafe release_path" in result.stdout


def test_public_release_packaging_is_deterministic_and_safely_extractable(tmp_path: Path) -> None:
    public = tmp_path / "public"
    asset = public / "v2-test-release"
    asset.mkdir(parents=True)
    (asset / "run_metadata.json").write_text(
        json.dumps(
            {
                "run_id": "v2-test-release",
                "terminal_status": "complete",
                "condition": "I1",
                "model": "fixture-model",
                "seed": 7,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (asset / "TRACE_COMPLETENESS.json").write_text(
        json.dumps({"schema_version": 1, "complete": True}) + "\n",
        encoding="utf-8",
    )
    (asset / "dialogue.jsonl").write_text('{"text":"hello"}\n', encoding="utf-8")
    build = run_script("build_public_manifest.py", str(asset))
    assert build.returncode == 0, build.stdout + build.stderr
    selection = tmp_path / "selection.jsonl"
    selection.write_text(
        json.dumps(
            {
                "asset_id": "v2-test-release",
                "run_id": "v2-test-release",
                "publication_tier": "canonical_confirmatory_fixture",
                "terminal_status": "complete",
                "selection_reason": "test fixture",
                "trace_schema": "v2",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    hashes = []
    for number in (1, 2):
        repository = tmp_path / f"repository-{number}"
        archives = tmp_path / f"archives-{number}"
        result = run_script(
            "prepare_public_release.py",
            "--selection",
            str(selection),
            "--public-assets",
            str(public),
            "--repository",
            str(repository),
            "--archives",
            str(archives),
            "--jobs",
            "1",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        archive = archives / "v2-test-release.tar.gz"
        hashes.append(hashlib.sha256(archive.read_bytes()).hexdigest())
        worlds = [
            json.loads(line)
            for line in (repository / "data/catalog/worlds.jsonl").read_text().splitlines()
        ]
        assert worlds[0]["analysis_eligible"] is True
        assert worlds[0]["release_path"] == "worlds/v2-test-release"
    assert hashes[0] == hashes[1]

    spec = importlib.util.spec_from_file_location("agent_economic_fetch_release", ROOT / "scripts/fetch_release.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    extracted = tmp_path / "extracted"
    module.safe_extract(tmp_path / "archives-1/v2-test-release.tar.gz", extracted)
    assert (extracted / "worlds/v2-test-release/dialogue.jsonl").read_text() == '{"text":"hello"}\n'

    fetched = tmp_path / "fetched"
    verify_local = run_script(
        "fetch_release.py",
        "--release",
        "public-data-v1",
        "--all",
        "--index",
        str(tmp_path / "repository-1/data/catalog/releases.json"),
        "--destination",
        str(fetched),
        "--source-directory",
        str(tmp_path / "archives-1"),
    )
    assert verify_local.returncode == 0, verify_local.stdout + verify_local.stderr
    assert (
        fetched / "public-data-v1/extracted/worlds/v2-test-release/dialogue.jsonl"
    ).read_text() == '{"text":"hello"}\n'


def test_local_custody_keeps_raw_public_assets_without_duplicate_redacted_archive(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    redacted = tmp_path / "redacted"
    for root in (raw, redacted):
        for asset_id in ("public-world", "reference-world"):
            asset = root / asset_id
            asset.mkdir(parents=True)
            (asset / "trace.jsonl").write_text('{"ok":true}\n', encoding="utf-8")
    selection = tmp_path / "selection.jsonl"
    selection.write_text(
        "".join(
            json.dumps({
                "asset_id": asset_id,
                "run_id": asset_id,
                "publication_tier": tier,
                "terminal_status": "complete",
            }) + "\n"
            for asset_id, tier in (
                ("public-world", "canonical_confirmatory_stage1"),
                ("reference-world", "reference_exploratory"),
            )
        ),
        encoding="utf-8",
    )
    public_selection = tmp_path / "public-selection.jsonl"
    public_selection.write_text(
        json.dumps({"asset_id": "public-world", "run_id": "public-world"}) + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "custody"
    result = run_script(
        "prepare_local_custody.py",
        "--selection",
        str(selection),
        "--public-selection",
        str(public_selection),
        "--raw-assets",
        str(raw),
        "--redacted-assets",
        str(redacted),
        "--output",
        str(output),
        "--jobs",
        "1",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(list((output / "private/raw-worlds").glob("*.tar.gz"))) == 2
    assert len(list((output / "private/redacted-reference").glob("*.tar.gz"))) == 1
    manifest = json.loads((output / "catalog/CUSTODY_MANIFEST.json").read_text())
    assert manifest["raw_nonredacted_assets"] == 2
    assert manifest["public_redacted_assets_stored_in_github_release"] == 1
    assert manifest["local_redacted_reference_assets"] == 1
