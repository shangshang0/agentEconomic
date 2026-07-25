from __future__ import annotations

import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("audit_original_ctf_catalog", Path(__file__).parents[1] / "scripts" / "audit_original_ctf_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_topology_does_not_treat_build_only_dockerfile_as_service(tmp_path: Path) -> None:
    (tmp_path / "attachments").mkdir()
    (tmp_path / "attachments" / "challenge.bin").write_bytes(b"binary")
    (tmp_path / "challenge").mkdir()
    (tmp_path / "challenge" / "Dockerfile").write_text("FROM scratch\n")
    assert MODULE.topology(tmp_path)["service"] is False


def test_topology_detects_declared_service_port(tmp_path: Path) -> None:
    (tmp_path / "challenge.yaml").write_text("ports:\n  - targetPort: 31337\n")
    assert MODULE.topology(tmp_path)["service"] is True


def test_handouts_exclude_solver_and_deployment_tree(tmp_path: Path) -> None:
    for directory in ("files", "solver", "build"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "payload").write_text(directory)
    assert MODULE.handout_paths(tmp_path) == ["files/payload"]


def test_flag_extraction_ignores_placeholder_values(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("flag{fake_flag} and SECCON{real_value_123}")
    assert [item["value"] for item in MODULE.trusted_flag_candidates(tmp_path)] == ["SECCON{real_value_123}"]
