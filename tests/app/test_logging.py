"""Structured logging behavior for :func:`src.app.on_message`."""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterable, Iterator, List

import pytest


@dataclass
class _DummyMessage:
    content: str


class _StubUserSession:
    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value


class _StubOutboundMessage:
    sent: List[str] = []

    def __init__(self, content: str) -> None:
        self.content = content
        self.__class__.sent.append(content)

    async def send(self) -> None:  # pragma: no cover - exercised indirectly
        self.__class__.sent.append(self.content)


class _StubStep:
    def __init__(self, name: str, *, type: str, show_input: bool) -> None:  # noqa: A002 - Chainlit signature
        self.name = name
        self.type = type
        self.show_input = show_input
        self.tokens: List[str] = []
        self.input: str | None = None
        self.output: str | None = None

    async def __aenter__(self) -> "_StubStep":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def stream_token(self, token: str) -> None:
        self.tokens.append(token)


class _StubProvider:
    def __init__(self, chunks: Iterable[str] | None = None, *, error: BaseException | None = None) -> None:
        self._chunks = list(chunks or [])
        self._error = error

    async def stream(self, model: str, messages: List[Dict[str, Any]], temperature: float) -> AsyncIterator[str]:
        if self._error:
            raise self._error
        for chunk in self._chunks:
            yield chunk


@pytest.fixture()
def app_module(tmp_path) -> Iterator[object]:
    """Load ``src.app`` with isolated Chainlit state."""

    app_root = tmp_path / "app"
    app_root.mkdir()
    previous_root = os.environ.get("CHAINLIT_APP_ROOT")
    os.environ["CHAINLIT_APP_ROOT"] = str(app_root)
    project_root = Path(__file__).resolve().parents[2]
    added_paths: list[str] = []
    for path in [project_root, project_root / "src"]:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
            added_paths.append(str(path))
    for module_name in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(module_name, None)
    sys.modules.pop("src.app", None)
    module = import_module("src.app")
    yield module
    for module_name in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(module_name, None)
    sys.modules.pop("src.app", None)
    for path in added_paths:
        if path in sys.path:
            sys.path.remove(path)
    if previous_root is None:
        os.environ.pop("CHAINLIT_APP_ROOT", None)
    else:
        os.environ["CHAINLIT_APP_ROOT"] = previous_root


@pytest.fixture()
def stub_chainlit(app_module):
    session = _StubUserSession()
    session.set("model", "gpt-5-main")
    session.set("chain", "single")
    session.set("trim_tokens", 512)
    session.set("min_turns", 0)
    session.set("system", "system prompt")
    session.set("show_debug", False)
    session.set("history", [])

    app_module.cl.user_session = session
    app_module.cl.Message = _StubOutboundMessage
    app_module.cl.Step = _StubStep
    _StubOutboundMessage.sent.clear()
    return session


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_on_message_emits_structured_log(monkeypatch, caplog, app_module, stub_chainlit):
    metrics = {
        "input_tokens": 120,
        "output_tokens": 60,
        "compress_ratio": 0.5,
        "semantic_retention": 0.8,
    }
    trimmed_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]

    observed_min_turns: Dict[str, int] = {}

    def _fake_trim_messages(
        history: List[Dict[str, Any]],
        target_tokens: int,
        model: str,
        *,
        min_turns: int = 0,
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        observed_min_turns["value"] = min_turns
        return list(trimmed_messages), dict(metrics)

    monkeypatch.setattr(app_module, "trim_messages", _fake_trim_messages)

    observed: Dict[str, Any] = {}

    def fake_observe_trim(*, compress_ratio: float, semantic_retention: float | None = None) -> None:
        observed["compress_ratio"] = compress_ratio
        observed["semantic_retention"] = semantic_retention

    monkeypatch.setattr(app_module.METRICS_REGISTRY, "observe_trim", fake_observe_trim)

    provider = _StubProvider(["hi"])
    monkeypatch.setattr(app_module, "get_provider", lambda model: provider)
    monkeypatch.setattr(app_module, "get_chain_steps", lambda chain_id: ["final"])

    clock = iter([100.0, 100.1, 100.2, 100.6])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    stub_chainlit.set("min_turns", 2)

    with caplog.at_level("INFO", logger="katamari.request"):
        await app_module.on_message(_DummyMessage("hello"))

    assert observed_min_turns["value"] == 2

    assert observed == {
        "compress_ratio": metrics["compress_ratio"],
        "semantic_retention": metrics["semantic_retention"],
    }

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].msg)
    uuid.UUID(payload["req_id"])
    assert payload["status"] == "success"
    assert payload["model"] == "gpt-5-main"
    assert payload["chain"] == "single"
    assert payload["token_in"] == metrics["input_tokens"]
    assert payload["token_out"] == metrics["output_tokens"]
    assert payload["compress_ratio"] == metrics["compress_ratio"]
    assert payload["semantic_retention"] == metrics["semantic_retention"]
    assert payload["retryable"] is None
    assert payload["latency_ms"] == pytest.approx((100.6 - 100.0) * 1000)
    steps = payload["step_latency_ms"]
    assert isinstance(steps, list)
    assert steps[0]["step"] == "Step 1: final"
    assert steps[0]["latency_ms"] == pytest.approx((100.2 - 100.1) * 1000)


class _RetryableError(RuntimeError):
    retryable = True


@pytest.mark.anyio
async def test_apply_settings_persists_min_turns(app_module, stub_chainlit):
    await app_module.apply_settings({"min_turns": 3})

    assert app_module.cl.user_session.get("min_turns") == 3


@pytest.mark.anyio
async def test_on_message_logs_retryable_error(monkeypatch, caplog, app_module, stub_chainlit):
    metrics = {
        "input_tokens": 80,
        "output_tokens": 40,
        "compress_ratio": 0.5,
        "semantic_retention": None,
    }
    trimmed_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "oops"},
    ]
    def _failing_trim(
        history: List[Dict[str, Any]],
        target_tokens: int,
        model: str,
        *,
        min_turns: int = 0,
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        return list(trimmed_messages), dict(metrics)

    monkeypatch.setattr(app_module, "trim_messages", _failing_trim)
    monkeypatch.setattr(app_module.METRICS_REGISTRY, "observe_trim", lambda **_: None)
    monkeypatch.setattr(app_module, "get_chain_steps", lambda chain_id: ["final"])

    error = _RetryableError("temporary")
    provider = _StubProvider(error=error)
    monkeypatch.setattr(app_module, "get_provider", lambda model: provider)

    clock = iter([10.0, 10.1, 10.2, 10.5])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    with caplog.at_level("INFO", logger="katamari.request"):
        with pytest.raises(_RetryableError):
            await app_module.on_message(_DummyMessage("oops"))

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].msg)
    uuid.UUID(payload["req_id"])
    assert payload["status"] == "failure"
    assert payload["retryable"] is True
    assert payload["error"] == "temporary"
    assert payload["token_in"] == metrics["input_tokens"]
    assert payload["token_out"] == metrics["output_tokens"]
    assert payload["compress_ratio"] == metrics["compress_ratio"]
    assert payload.get("semantic_retention") is None
