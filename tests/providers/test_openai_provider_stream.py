"""OpenAI provider contract tests using recorded SSE reflect scenario."""

from __future__ import annotations

import builtins
import importlib
import json
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Callable, Dict, Iterable, Iterator, List, Type, TypeVar, TypedDict, cast

import pytest

_F = TypeVar("_F", bound=Callable[..., Any])
ANYIO_ASYNCIO = cast(Callable[[_F], _F], pytest.mark.anyio("asyncio"))


@pytest.fixture(name="anyio_backend")
def fixture_anyio_backend() -> str:
    """Limit anyio to asyncio backend for CI."""

    return "asyncio"


def _to_namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _to_namespace(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_to_namespace(item) for item in value]
    return value


class _StubStream:
    def __init__(self, events: Iterable[Any]) -> None:
        self._events = list(events)
        self._iterator: Iterator[Any] | None = None

    def __aiter__(self) -> "_StubStream":
        self._iterator = iter(self._events)
        return self

    async def __anext__(self) -> Any:
        if self._iterator is None:
            self._iterator = iter(self._events)
        try:
            return next(self._iterator)
        except StopIteration as exc:  # pragma: no cover - safety guard
            raise StopAsyncIteration from exc


class _StubChatCompletions:
    def __init__(self, *, stream_events: List[Any], completion: Any) -> None:
        self._stream_events = [_to_namespace(event) for event in stream_events]
        self._completion = _to_namespace(completion)
        self.calls: List[Dict[str, Any]] = []

    async def create(self, model: str, messages: List[Dict[str, Any]], *, stream: bool, **opts: Any) -> Any:
        record = {"model": model, "messages": messages, "stream": stream, "opts": opts}
        self.calls.append(record)
        if stream:
            return _StubStream(self._stream_events)
        return self._completion


class _StubOpenAI:
    def __init__(self, *, stream_events: List[Any], completion: Any, **_: Any) -> None:
        self.chat = SimpleNamespace(
            completions=_StubChatCompletions(stream_events=stream_events, completion=completion)
        )


class _StubBundle(TypedDict):
    provider: Any
    completions: "_StubChatCompletions"
    payload: Dict[str, Any]


def _load_reflect_payload() -> Dict[str, Any]:
    """Load SSE replay data captured from the reflect chain scenario."""

    path = Path(__file__).with_name("fixtures") / "openai_chat_reflect_stream.json"
    with path.open(encoding="utf-8") as handle:
        return cast(Dict[str, Any], json.load(handle))


def _install_stubbed_openai(monkeypatch: pytest.MonkeyPatch, payload: Dict[str, Any]) -> _StubBundle:
    """Inject the recorded OpenAI client so CI runs without network keys."""

    provider_module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Any, getattr(provider_module, "OpenAIProvider"))
    from src.providers import openai_client

    def _factory(**kwargs: Any) -> _StubOpenAI:
        return _StubOpenAI(stream_events=payload["stream_events"], completion=payload["completion"], **kwargs)

    def stub_factory() -> Any:
        return cast(Any, _factory)
    monkeypatch.setattr(provider_module, "_resolve_async_openai", stub_factory)
    monkeypatch.setattr(openai_client, "_resolve_async_openai", stub_factory)

    provider = provider_cls()
    completions = cast(_StubChatCompletions, provider.client.chat.completions)
    return cast(
        _StubBundle,
        {
            "provider": provider,
            "completions": completions,
            "payload": payload,
        },
    )


def _simulate_missing_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = "openai"
    monkeypatch.delitem(sys.modules, module_name, raising=False)

    original_import = builtins.__import__

    def _missing_import(
        name: str,
        globals_: Dict[str, Any] | None = None,
        locals_: Dict[str, Any] | None = None,
        fromlist: Iterable[str] = (),
        level: int = 0,
    ) -> Any:
        if name == module_name or name.startswith(f"{module_name}."):
            raise ModuleNotFoundError(f"No module named '{module_name}'")
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _missing_import)


def test_provider_raises_helpful_error_when_openai_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider should expose a clear error if the openai package is unavailable."""

    _simulate_missing_openai(monkeypatch)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))

    with pytest.raises(ImportError, match=r"openai>=1\.30\.0"):
        provider_cls()


def test_module_import_succeeds_without_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """openai_client module should import even if openai is absent."""

    _simulate_missing_openai(monkeypatch)
    monkeypatch.delitem(sys.modules, "openai", raising=False)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))

    assert getattr(module, "AsyncOpenAI", None) is None

    with pytest.raises(ImportError, match=r"openai>=1\.30\.0"):
        provider_cls()


@ANYIO_ASYNCIO
async def test_stream_uses_recorded_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure streaming yields the recorded reflect SSE tokens and logs the request."""

    payload = _load_reflect_payload()
    bundle = _install_stubbed_openai(monkeypatch, payload)
    provider = bundle["provider"]
    completions: _StubChatCompletions = bundle["completions"]
    messages = payload["messages"]

    chunks: List[str] = []
    async for token in provider.stream("gpt-4o-mini", messages, temperature=0.4):
        chunks.append(token)

    expected = [
        event["choices"][0]["delta"]["content"]
        for event in payload["stream_events"]
        if event["choices"][0]["delta"]["content"]
    ]
    assert chunks == expected

    assert completions.calls == [
        {
            "model": "gpt-4o-mini",
            "messages": messages,
            "stream": True,
            "opts": {"temperature": 0.4},
        }
    ]


@ANYIO_ASYNCIO
async def test_complete_uses_recorded_final_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Final completion should reuse the recorded reflect output without network access."""

    payload = _load_reflect_payload()
    bundle = _install_stubbed_openai(monkeypatch, payload)
    provider = bundle["provider"]

    result = await provider.complete("gpt-4o-mini", payload["messages"], temperature=0.0)

    assert result == payload["completion"]["choices"][0]["message"]["content"]


def test_openai_dependency_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Import succeeds without openai, but instantiating raises a helpful error."""

    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    original_import = builtins.__import__

    def _raising_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "openai":
            raise ModuleNotFoundError("No module named 'openai'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _raising_import)
    module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Any, getattr(module, "OpenAIProvider"))

    with pytest.raises(ImportError, match=re.compile(r"openai>=1\.30\.0", re.IGNORECASE)):
        provider_cls()


def test_provider_prompts_upgrade_when_async_client_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provide guidance to upgrade openai when AsyncOpenAI is unavailable."""

    dummy_openai = ModuleType("openai")
    monkeypatch.setitem(sys.modules, "openai", dummy_openai)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))

    with pytest.raises(ImportError, match=r"openai>=1\.30\.0"):
        provider_cls()


def test_module_exposes_async_openai_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module should publish the AsyncOpenAI factory when available at import time."""

    calls: Dict[str, Any] = {}

    def _factory(**kwargs: Any) -> Any:
        calls["kwargs"] = kwargs
        return SimpleNamespace(**kwargs)

    dummy_openai = ModuleType("openai")
    dummy_openai.AsyncOpenAI = _factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", dummy_openai)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    module = importlib.import_module("src.providers.openai_client")

    exported = getattr(module, "AsyncOpenAI")
    assert callable(exported)
    exported(api_key="test-key")
    assert calls == {"kwargs": {"api_key": "test-key"}}
