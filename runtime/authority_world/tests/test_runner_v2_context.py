from __future__ import annotations

import importlib
import json
from pathlib import Path


def load_runner(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("BACKEND_URL", "http://backend:8100")
    monkeypatch.setenv("AGENT_ID", "A1")
    monkeypatch.setenv("AGENT_TOKEN", "token")
    module = importlib.import_module("agent.runner_v2")
    monkeypatch.setattr(module, "STATE", tmp_path)
    monkeypatch.setattr(module, "RUN_ID", "run-test")
    return module


def test_tool_receipt_context_omits_fresh_panel_and_keeps_semantic_result(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner(monkeypatch, tmp_path)
    huge_panel = {"forum": ["x" * 5000], "private_messages": ["secret" * 1000], "run_id": "run-test"}
    compact = runner.receipt_for_context(
        "open_task",
        True,
        {"panel": huge_panel, "handle": "h" * 32, "task_output": "AW?", "status": "ok", "unused": "drop me"},
    )
    text = json.dumps(compact, ensure_ascii=False)
    assert "panel" not in text
    assert "private_messages" not in text
    assert compact == {"name": "open_task", "ok": True, "receipt": {"handle": "h" * 32, "task_output": "AW?", "status": "ok"}}


def test_raw_audit_and_model_context_are_separate(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner(monkeypatch, tmp_path)
    raw_value = {"request_id": "r1", "panel": {"forum": ["x" * 5000]}, "handle": "h" * 32}
    context_value = runner.receipt_for_context("open_task", True, raw_value)
    runner.event("tool_result", raw_value, context_value)
    raw_path = tmp_path / "runs" / "run-test" / "audit.raw.jsonl"
    context_path = tmp_path / "runs" / "run-test" / "context.jsonl"
    raw = raw_path.read_text(encoding="utf-8")
    ctx = context_path.read_text(encoding="utf-8")
    assert "panel" in raw and "forum" in raw
    assert "panel" not in ctx and "forum" not in ctx
    assert len(ctx) < len(raw) / 10


def test_context_preserves_unicode_line_separators_inside_json(monkeypatch, tmp_path: Path) -> None:
    runner = load_runner(monkeypatch, tmp_path)
    payload = "before\u0085middle\u2028after\u2029end"
    runner.event("tool_result", {"task_output": payload})

    assert runner.context() == [
        {
            "at": json.loads(
                (tmp_path / "runs" / "run-test" / "context.jsonl").read_text(encoding="utf-8")
            )["at"],
            "kind": "tool_result",
            "task_output": payload,
        }
    ]
