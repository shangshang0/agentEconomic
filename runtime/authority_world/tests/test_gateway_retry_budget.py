from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]


class FakeRequest:
    async def json(self) -> dict[str, object]:
        return {
            "request_id": "test-request",
            "agent_id": "A4",
            "input": [],
            "tools": [],
        }


def load_gateway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GATEWAY_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GATEWAY_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PROVIDER_MAX_ATTEMPTS", "3")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_STYLE", raising=False)
    spec = importlib.util.spec_from_file_location("gateway_retry_budget_test_module", ROOT / "gateway/app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_slow_timeout_exhausts_total_budget_without_second_attempt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = load_gateway(tmp_path, monkeypatch)
    timeouts: list[float] = []
    audit_rows: list[dict[str, object]] = []

    def create(**_: object) -> object:
        raise TimeoutError("timed out")

    def openai(**kwargs: object) -> object:
        timeouts.append(float(kwargs["timeout"]))
        return SimpleNamespace(responses=SimpleNamespace(create=create))

    ticks = iter([0.0, 0.0, 210.0])
    monkeypatch.setattr(gateway, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(gateway, "OpenAI", openai)
    monkeypatch.setattr(gateway, "audit", audit_rows.append)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(gateway.generate(FakeRequest(), authorization="Bearer test-token"))

    assert raised.value.status_code == 502
    assert timeouts == [210.0]
    assert [row["kind"] for row in audit_rows] == ["provider_error"]
    assert audit_rows[0]["attempts"] == 1
    assert audit_rows[0]["remaining_timeout_seconds"] == 0.0


def test_fast_retry_uses_only_remaining_total_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = load_gateway(tmp_path, monkeypatch)
    timeouts: list[float] = []
    audit_rows: list[dict[str, object]] = []
    calls = 0

    def create(**_: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("fast connection timeout")
        return SimpleNamespace(output=[], output_text="ok", model="test-model")

    def openai(**kwargs: object) -> object:
        timeouts.append(float(kwargs["timeout"]))
        return SimpleNamespace(responses=SimpleNamespace(create=create))

    async def no_sleep(_: float) -> None:
        return None

    ticks = iter([0.0, 0.0, 1.0, 3.0])
    monkeypatch.setattr(gateway, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(gateway, "OpenAI", openai)
    monkeypatch.setattr(gateway, "audit", audit_rows.append)
    monkeypatch.setattr(gateway.asyncio, "sleep", no_sleep)

    result = asyncio.run(gateway.generate(FakeRequest(), authorization="Bearer test-token"))

    assert result["text"] == "ok"
    assert timeouts == [210.0, 207.0]
    assert [row["kind"] for row in audit_rows] == ["provider_retry", "exchange"]
    assert audit_rows[0]["remaining_timeout_seconds"] == 209.0
