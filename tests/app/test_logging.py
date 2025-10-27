"""Structured logging behavior for :func:`src.app.on_message`."""

from __future__ import annotations

import json
import math
import os
import sys
import uuid
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterable, Iterator, List
from unittest.mock import Mock

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
    instances: List["_StubStep"] = []

    def __init__(self, name: str, *, type: str, show_input: bool) -> None:  # noqa: A002 - Chainlit signature
        self.name = name
        self.type = type
        self.show_input = show_input
        self.tokens: List[str] = []
        self.input: str | None = None
        self.output: str | None = None
        self.__class__.instances.append(self)

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
    _StubStep.instances.clear()

    original_analyze_intent = getattr(app_module, "analyze_intent", None)
    app_module.analyze_intent = lambda _text: ""

    try:
        yield session
    finally:
        if original_analyze_intent is not None:
            app_module.analyze_intent = original_analyze_intent
        else:
            delattr(app_module, "analyze_intent")


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_on_message_computes_semantic_retention(
    monkeypatch, caplog, app_module, stub_chainlit
):
    metrics = {
        "input_tokens": 120,
        "output_tokens": 60,
        "compress_ratio": 0.5,
        "semantic_retention": None,
    }
    trimmed_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]

    def _fake_trim(history, target_tokens, model, *, min_turns: int = 0):
        return list(trimmed_messages), dict(metrics)

    monkeypatch.setattr(app_module, "trim_messages", _fake_trim)

    observed: Dict[str, Any] = {}

    def fake_observe_trim(*, compress_ratio: float, semantic_retention: float | None = None) -> None:
        observed["compress_ratio"] = compress_ratio
        observed["semantic_retention"] = semantic_retention

    monkeypatch.setattr(app_module.METRICS_REGISTRY, "observe_trim", fake_observe_trim)

    calls: List[Dict[str, Any]] = []

    def fake_compute(before, after):
        calls.append({"before": list(before), "after": list(after)})
        return 0.8

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "stub")
    monkeypatch.setattr(app_module, "compute_semantic_retention", fake_compute)
    monkeypatch.setattr(app_module.asyncio, "to_thread", immediate_to_thread)

    provider = _StubProvider(["hi"])
    monkeypatch.setattr(app_module, "get_provider", lambda model: provider)
    monkeypatch.setattr(app_module, "get_chain_steps", lambda chain_id: ["final"])

    clock = iter([100.0, 100.1, 100.2, 100.6])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    with caplog.at_level("INFO", logger="katamari.request"):
        await app_module.on_message(_DummyMessage("hello"))

    assert observed == {
        "compress_ratio": metrics["compress_ratio"],
        "semantic_retention": 0.8,
    }
    assert len(calls) == 1
    assert calls[0]["before"][1]["content"] == "hello"
    assert calls[0]["after"] == trimmed_messages

    stored_metrics = app_module.cl.user_session.get("trim_metrics")
    assert stored_metrics["semantic_retention"] == pytest.approx(0.8)

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].msg)
    assert payload["semantic_retention"] == pytest.approx(0.8)


@pytest.mark.anyio
async def test_on_message_uses_formatter_for_trim_message_when_debug_disabled(
    monkeypatch, app_module, stub_chainlit
):
    metrics = {
        "input_tokens": 120,
        "output_tokens": 60,
        "compress_ratio": 0.5,
        "semantic_retention": 0.7,
    }
    trimmed_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]

    def _fake_trim(history, target_tokens, model, *, min_turns: int = 0):
        return list(trimmed_messages), dict(metrics)

    monkeypatch.setattr(app_module, "trim_messages", _fake_trim)

    provider = _StubProvider(["hi"])
    monkeypatch.setattr(app_module, "get_provider", lambda model: provider)
    monkeypatch.setattr(app_module, "get_chain_steps", lambda chain_id: ["final"])

    clock = iter([100.0, 100.1, 100.2, 100.6])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    stub_chainlit.set("history", [])
    stub_chainlit.set("show_debug", False)
    _StubOutboundMessage.sent.clear()

    observed_calls: list[dict[str, Any]] = []
    formatted_messages: list[str] = []

    def _fake_format_trim_message(
        *,
        token_out: int,
        token_in: int,
        compress_ratio: float,
        show_retention: bool,
        semantic_retention: float | None,
    ) -> str:
        observed_calls.append(
            {
                "token_out": token_out,
                "token_in": token_in,
                "compress_ratio": compress_ratio,
                "show_retention": show_retention,
                "semantic_retention": semantic_retention,
            }
        )
        formatted = (
            f"[trim] tokens: {token_out}/{token_in} (ratio {compress_ratio})"
        )
        formatted_messages.append(formatted)
        return formatted

    monkeypatch.setattr(
        app_module,
        "_format_trim_message",
        _fake_format_trim_message,
    )

    await app_module.on_message(_DummyMessage("hello"))

    assert len(observed_calls) == 1
    observed_call = observed_calls[0]
    assert observed_call["token_out"] == metrics["output_tokens"]
    assert observed_call["token_in"] == metrics["input_tokens"]
    assert observed_call["compress_ratio"] == metrics["compress_ratio"]
    assert observed_call["show_retention"] is False
    assert (
        observed_call["semantic_retention"] == metrics["semantic_retention"]
    )
    assert formatted_messages == [_StubOutboundMessage.sent[0]]
    assert _StubOutboundMessage.sent.count(formatted_messages[0]) == 1

@pytest.mark.anyio
async def test_on_message_emits_trim_and_streams_tokens_when_debug_enabled(
    monkeypatch, app_module, stub_chainlit
):
    metrics = {
        "input_tokens": 200,
        "output_tokens": 120,
        "compress_ratio": 0.6,
        "semantic_retention": 0.85,
    }
    trimmed_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]

    def _fake_trim(history, target_tokens, model, *, min_turns: int = 0):
        return list(trimmed_messages), dict(metrics)

    monkeypatch.setattr(app_module, "trim_messages", _fake_trim)

    provider = _StubProvider(["hi", " there"])
    monkeypatch.setattr(app_module, "get_provider", lambda model: provider)
    monkeypatch.setattr(app_module, "get_chain_steps", lambda chain_id: ["final"])

    clock = iter([100.0, 100.1, 100.2, 100.6, 200.0, 200.1, 200.2, 200.6])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    stub_chainlit.set("history", [])
    stub_chainlit.set("show_debug", True)
    _StubOutboundMessage.sent.clear()
    _StubStep.instances.clear()

    await app_module.on_message(_DummyMessage("hello"))

    trim_messages = [
        msg
        for msg in _StubOutboundMessage.sent
        if msg.startswith("[trim]") and not msg.startswith("[trim][debug]")
    ]
    assert trim_messages, "Expected [trim] message even when show_debug=True"

    expected_prefix = (
        f"[trim] tokens: {metrics['output_tokens']}/{metrics['input_tokens']} "
        f"(ratio {metrics['compress_ratio']})"
    )
    assert any(msg.startswith(expected_prefix) for msg in trim_messages)
    assert any("retention" in msg for msg in trim_messages)

    debug_messages = [
        msg for msg in _StubOutboundMessage.sent if msg.startswith("[trim][debug]")
    ]
    assert debug_messages, "Debug mode should still emit [trim][debug] message"

    streamed_tokens = [step.tokens for step in _StubStep.instances if step.tokens]
    assert streamed_tokens, "LLM tokens should be streamed regardless of show_debug"
    assert streamed_tokens[0] == ["hi", " there"]


@pytest.mark.anyio
async def test_on_message_records_trim_message_in_sent_buffer_when_debug_disabled(
    monkeypatch, app_module, stub_chainlit
):
    metrics = {
        "input_tokens": 120,
        "output_tokens": 60,
        "compress_ratio": 0.5,
        "semantic_retention": 0.7,
    }
    trimmed_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]

    mock_trim = Mock(return_value=(list(trimmed_messages), dict(metrics)))
    monkeypatch.setattr(app_module, "trim_messages", mock_trim)

    provider = _StubProvider(["hi"])
    monkeypatch.setattr(app_module, "get_provider", lambda model: provider)
    monkeypatch.setattr(app_module, "get_chain_steps", lambda chain_id: ["final"])

    clock = iter([100.0, 100.1, 100.2, 100.6])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    stub_chainlit.set("history", [])
    stub_chainlit.set("show_debug", False)
    _StubOutboundMessage.sent.clear()
    _StubStep.instances.clear()

    await app_module.on_message(_DummyMessage("hello"))

    mock_trim.assert_called_once()

    trim_messages = [
        message
        for message in _StubOutboundMessage.sent
        if message.startswith("[trim]") and not message.startswith("[trim][debug]")
    ]
    expected_message = app_module._format_trim_message(
        token_out=metrics["output_tokens"],
        token_in=metrics["input_tokens"],
        compress_ratio=metrics["compress_ratio"],
        show_retention=False,
        semantic_retention=metrics["semantic_retention"],
    )
    assert trim_messages, "[trim] message should be emitted"
    assert all(message == expected_message for message in trim_messages)

    debug_messages = [
        message
        for message in _StubOutboundMessage.sent
        if message.startswith("[trim][debug]")
    ]
    assert not debug_messages, "[trim][debug] message must not be emitted when show_debug=False"


@pytest.mark.anyio
async def test_on_message_converts_string_nan_semantic_retention(
    monkeypatch, caplog, app_module, stub_chainlit
):
    metrics = {
        "input_tokens": 120,
        "output_tokens": 60,
        "compress_ratio": 0.5,
        "semantic_retention": None,
    }
    trimmed_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]

    def _fake_trim(history, target_tokens, model, *, min_turns: int = 0):
        return list(trimmed_messages), dict(metrics)

    monkeypatch.setattr(app_module, "trim_messages", _fake_trim)

    observed: Dict[str, Any] = {}

    def fake_observe_trim(*, compress_ratio: float, semantic_retention: float | None = None) -> None:
        observed["compress_ratio"] = compress_ratio
        observed["semantic_retention"] = semantic_retention

    monkeypatch.setattr(app_module.METRICS_REGISTRY, "observe_trim", fake_observe_trim)

    calls: List[Dict[str, Any]] = []

    def fake_compute(before, after):
        calls.append({"before": list(before), "after": list(after)})
        return "nan"

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "stub")
    monkeypatch.setattr(app_module, "compute_semantic_retention", fake_compute)
    monkeypatch.setattr(app_module.asyncio, "to_thread", immediate_to_thread)

    provider = _StubProvider(["hi"])
    monkeypatch.setattr(app_module, "get_provider", lambda model: provider)
    monkeypatch.setattr(app_module, "get_chain_steps", lambda chain_id: ["final"])

    clock = iter([100.0, 100.1, 100.2, 100.6])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    with caplog.at_level("INFO", logger="katamari.request"):
        await app_module.on_message(_DummyMessage("hello"))

    assert observed == {
        "compress_ratio": metrics["compress_ratio"],
        "semantic_retention": None,
    }
    assert len(calls) == 1
    assert calls[0]["before"][1]["content"] == "hello"
    assert calls[0]["after"] == trimmed_messages

    stored_metrics = app_module.cl.user_session.get("trim_metrics")
    assert stored_metrics["semantic_retention"] is None

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].msg)
    assert payload["semantic_retention"] is None


@pytest.mark.anyio
async def test_on_message_logs_nan_semantic_retention_as_null_json(
    monkeypatch, caplog, app_module, stub_chainlit
):
    metrics = {
        "input_tokens": 120,
        "output_tokens": 60,
        "compress_ratio": 0.5,
        "semantic_retention": None,
    }
    trimmed_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hello"},
    ]

    def _fake_trim(history, target_tokens, model, *, min_turns: int = 0):
        return list(trimmed_messages), dict(metrics)

    monkeypatch.setattr(app_module, "trim_messages", _fake_trim)

    observed: Dict[str, Any] = {}

    def fake_observe_trim(*, compress_ratio: float, semantic_retention: float | None = None) -> None:
        observed["compress_ratio"] = compress_ratio
        observed["semantic_retention"] = semantic_retention

    monkeypatch.setattr(app_module.METRICS_REGISTRY, "observe_trim", fake_observe_trim)

    calls: List[Dict[str, Any]] = []

    def fake_compute(before, after):
        calls.append({"before": list(before), "after": list(after)})
        return math.nan

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "stub")
    monkeypatch.setattr(app_module, "compute_semantic_retention", fake_compute)
    monkeypatch.setattr(app_module.asyncio, "to_thread", immediate_to_thread)

    provider = _StubProvider(["hi"])
    monkeypatch.setattr(app_module, "get_provider", lambda model: provider)
    monkeypatch.setattr(app_module, "get_chain_steps", lambda chain_id: ["final"])

    clock = iter([100.0, 100.1, 100.2, 100.6])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    with caplog.at_level("INFO", logger="katamari.request"):
        await app_module.on_message(_DummyMessage("hello"))

    assert observed == {
        "compress_ratio": metrics["compress_ratio"],
        "semantic_retention": None,
    }
    assert len(calls) == 1
    assert calls[0]["before"][1]["content"] == "hello"
    assert calls[0]["after"] == trimmed_messages

    stored_metrics = app_module.cl.user_session.get("trim_metrics")
    assert stored_metrics["semantic_retention"] is None

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].msg)
    assert payload["semantic_retention"] is None
    assert "NaN" not in caplog.records[0].msg


@pytest.mark.anyio
async def test_on_message_emits_structured_log(monkeypatch, caplog, app_module, stub_chainlit):
    metrics = {
        "input_tokens": 120,
        "output_tokens": 60,
        "compress_ratio": 0.5,
        "semantic_retention": None,
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

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.delenv("SEMANTIC_RETENTION_PROVIDER", raising=False)
    monkeypatch.setattr(app_module.asyncio, "to_thread", immediate_to_thread)

    clock = iter([100.0, 100.1, 100.2, 100.6])
    monkeypatch.setattr(app_module, "perf_counter", lambda: next(clock), raising=False)

    stub_chainlit.set("min_turns", 2)

    with caplog.at_level("INFO", logger="katamari.request"):
        await app_module.on_message(_DummyMessage("hello"))

    assert observed_min_turns["value"] == 2

    assert observed == {
        "compress_ratio": metrics["compress_ratio"],
        "semantic_retention": None,
    }

    stored_metrics = app_module.cl.user_session.get("trim_metrics")
    assert stored_metrics["semantic_retention"] is None

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].msg)
    uuid.UUID(payload["req_id"])
    assert payload["status"] == "success"
    assert payload["model"] == "gpt-5-main"
    assert payload["chain"] == "single"
    assert payload["token_in"] == metrics["input_tokens"]
    assert payload["token_out"] == metrics["output_tokens"]
    assert payload["compress_ratio"] == metrics["compress_ratio"]
    assert payload["semantic_retention"] is None
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
async def test_apply_settings_updates_history_system(
    monkeypatch, app_module, stub_chainlit
):
    session = app_module.cl.user_session
    session.set(
        "history",
        [
            {"role": "system", "content": "legacy persona"},
            {"role": "user", "content": "hello"},
        ],
    )

    updated_prompt = "You are Persona 2."
    monkeypatch.setattr(
        app_module,
        "compile_persona_yaml",
        lambda yaml_text: (updated_prompt, []),
    )

    await app_module.apply_settings({"persona_yaml": "name: persona"})

    history = session.get("history")
    assert history[0] == {"role": "system", "content": updated_prompt}
    assert history[1] == {"role": "user", "content": "hello"}
    assert session.get("system") == updated_prompt

    await app_module.apply_settings({"persona_yaml": ""})

    history = session.get("history")
    assert history[0] == {
        "role": "system",
        "content": app_module.DEFAULT_SYSTEM_PROMPT,
    }
    assert session.get("system") == app_module.DEFAULT_SYSTEM_PROMPT


@pytest.mark.anyio
async def test_apply_settings_updates_history_system_when_history_empty(
    monkeypatch, app_module, stub_chainlit
):
    session = app_module.cl.user_session
    session.set("history", [])

    updated_prompt = "You are Persona 3."
    monkeypatch.setattr(
        app_module,
        "compile_persona_yaml",
        lambda yaml_text: (updated_prompt, []),
    )

    await app_module.apply_settings({"persona_yaml": "name: persona"})

    assert session.get("history") == [
        {"role": "system", "content": updated_prompt},
    ]
    assert session.get("system") == updated_prompt

    await app_module.apply_settings({"persona_yaml": ""})

    assert session.get("history") == [
        {"role": "system", "content": app_module.DEFAULT_SYSTEM_PROMPT},
    ]
    assert session.get("system") == app_module.DEFAULT_SYSTEM_PROMPT


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
