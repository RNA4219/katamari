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
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

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
    original_import_module = importlib.import_module

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

    def _missing_import_module(name: str, package: str | None = None) -> ModuleType:
        if name == module_name or name.startswith(f"{module_name}."):
            raise ModuleNotFoundError(f"No module named '{module_name}'")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _missing_import_module)


def test_provider_raises_helpful_error_when_openai_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider should expose a clear error if the openai package is unavailable."""

    _simulate_missing_openai(monkeypatch)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))

    with pytest.raises(ImportError) as excinfo:
        provider_cls()

    message = str(excinfo.value)
    assert "openai>=1.30.0" in message
    assert 'pip install --upgrade "openai>=1.30.0"' in message


def test_module_import_succeeds_without_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """openai_client module should import even if openai is absent."""

    _simulate_missing_openai(monkeypatch)
    monkeypatch.delitem(sys.modules, "openai", raising=False)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))

    async_factory = getattr(module, "AsyncOpenAI", None)
    assert async_factory is None

    with pytest.raises(ImportError) as excinfo:
        provider_cls()

    message = str(excinfo.value)
    assert "openai>=1.30.0" in message
    assert 'pip install --upgrade "openai>=1.30.0"' in message


def test_module_reimport_allows_stub_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing openai import should still allow injecting a stub factory after re-import."""

    _simulate_missing_openai(monkeypatch)
    monkeypatch.delitem(sys.modules, "openai", raising=False)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    # Initial import without openai should leave the factory unset.
    module = importlib.import_module("src.providers.openai_client")
    assert getattr(module, "AsyncOpenAI") is None

    # Re-import to mimic fresh module load when tests swap in stubs.
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)
    module = importlib.import_module("src.providers.openai_client")

    assert getattr(module, "AsyncOpenAI") is None

    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    class _DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=lambda **_: SimpleNamespace())
            )

    dummy_client = _DummyClient()

    def stub_factory(**kwargs: Any) -> _DummyClient:
        dummy_client.kwargs = kwargs
        return dummy_client

    module._register_async_openai(stub_factory)

    provider = provider_cls()
    assert isinstance(provider.client, _DummyClient)
    assert provider.client is dummy_client


def test_module_import_with_legacy_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module import tolerates legacy openai packages missing AsyncOpenAI."""

    legacy_openai = ModuleType("openai")
    monkeypatch.setitem(sys.modules, "openai", legacy_openai)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    module = importlib.import_module("src.providers.openai_client")

    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))

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
async def test_stream_supports_structured_delta_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream should concatenate structured content payloads into string tokens."""

    messages = [{"role": "user", "content": "hello"}]
    structured_events = [
        {
            "choices": [
                {"delta": {"content": [{"type": "output_text", "text": "alpha"}]}},
            ],
        },
        {
            "choices": [
                {
                    "delta": {
                        "content": [
                            {"type": "output_text", "text": "be"},
                            {"type": "output_text", "text": "ta"},
                            {"type": "reasoning", "text": ""},
                        ]
                    }
                }
            ],
        },
        {
            "choices": [
                {
                    "delta": {
                        "content": [
                            {"type": "output_text", "text": "gamma"},
                            {"type": "tool_use", "id": "ignore", "text": None},
                        ]
                    }
                }
            ],
        },
    ]
    payload = {
        "messages": messages,
        "stream_events": structured_events,
        "completion": {"choices": [{"message": {"content": "unused"}}]},
    }
    bundle = _install_stubbed_openai(monkeypatch, payload)
    provider = bundle["provider"]
    completions: _StubChatCompletions = bundle["completions"]

    chunks: List[str] = []
    async for token in provider.stream("gpt-4o-mini", messages, temperature=0.1):
        chunks.append(token)

    assert chunks == ["alpha", "beta", "gamma"]
    assert completions.calls == [
        {
            "model": "gpt-4o-mini",
            "messages": messages,
            "stream": True,
            "opts": {"temperature": 0.1},
        }
    ]


@ANYIO_ASYNCIO
async def test_stream_handles_namespace_delta_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structured namespaces should be flattened to raw text tokens."""

    messages = [{"role": "user", "content": "hello"}]
    namespace_events = [
        {
            "choices": [
                {
                    "delta": {
                        "content": [
                            SimpleNamespace(
                                type="output_text",
                                text=SimpleNamespace(payload={"text": "alpha", "noise": 1}),
                            )
                        ]
                    }
                }
            ],
        },
        {
            "choices": [
                {
                    "delta": {
                        "content": [
                            SimpleNamespace(
                                type="output_text",
                                text=SimpleNamespace(payload={"meta": {"text": "beta"}}),
                            ),
                            SimpleNamespace(type="reasoning", text=""),
                        ]
                    }
                }
            ],
        },
        {
            "choices": [
                {
                    "delta": {
                        "content": [
                            SimpleNamespace(
                                type="output_text",
                                text=SimpleNamespace(
                                    payload=SimpleNamespace(payload={"text": "gamma"})
                                ),
                            )
                        ]
                    }
                }
            ],
        },
    ]
    payload = {
        "messages": messages,
        "stream_events": namespace_events,
        "completion": {"choices": [{"message": {"content": "unused"}}]},
    }
    bundle = _install_stubbed_openai(monkeypatch, payload)
    provider = bundle["provider"]
    completions: _StubChatCompletions = bundle["completions"]

    chunks: List[str] = []
    async for token in provider.stream("gpt-4o-mini", messages, temperature=0.2):
        chunks.append(token)

    assert chunks == ["alpha", "beta", "gamma"]
    assert completions.calls == [
        {
            "model": "gpt-4o-mini",
            "messages": messages,
            "stream": True,
            "opts": {"temperature": 0.2},
        }
    ]


@ANYIO_ASYNCIO
async def test_stream_retries_and_resumes_on_retryable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry streaming on retryable failures and resume without duplicating tokens."""

    from src.providers import openai_client

    class _RetryableStreamError(RuntimeError):
        retryable = True

    class _FlakyStream:
        def __init__(self, events: List[Any], fail_after: int | None) -> None:
            self._events = events
            self._fail_after = fail_after
            self._index = 0

        def __aiter__(self) -> "_FlakyStream":
            return self

        async def __anext__(self) -> Any:
            if self._fail_after is not None and self._index >= self._fail_after:
                raise _RetryableStreamError("transient failure")
            if self._index >= len(self._events):
                raise StopAsyncIteration
            event = self._events[self._index]
            self._index += 1
            return event

    class _FlakyCompletions:
        def __init__(self, events: List[Any], failures: List[int | None]) -> None:
            self._events = events
            self._failures = failures
            self.calls: List[Dict[str, Any]] = []
            self._invocation = 0

        async def create(
            self,
            model: str,
            messages: List[Dict[str, Any]],
            *,
            stream: bool,
            **opts: Any,
        ) -> Any:
            record = {"model": model, "messages": messages, "stream": stream, "opts": opts}
            self.calls.append(record)
            fail_after = self._failures[min(self._invocation, len(self._failures) - 1)]
            self._invocation += 1
            if not stream:
                raise AssertionError("flaky completions only supports streaming in tests")
            return _FlakyStream(self._events, fail_after)

    class _FlakyClient:
        def __init__(self, completions: _FlakyCompletions) -> None:
            self.chat = SimpleNamespace(completions=completions)

    messages = [{"role": "user", "content": "hello"}]
    tokens = ["alpha", "beta", "gamma", "delta"]
    events = [
        _to_namespace(
            {"choices": [{"delta": {"content": token}}]},
        )
        for token in tokens
    ]

    completions = _FlakyCompletions(events, failures=[0, 1, 2, None])
    client = _FlakyClient(completions)

    def _factory(**_: Any) -> _FlakyClient:
        return client

    monkeypatch.setattr(openai_client, "_resolve_async_openai", lambda: _factory)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    provider = openai_client.OpenAIProvider()

    sleep_calls: List[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(openai_client.asyncio, "sleep", _fake_sleep)

    chunks: List[str] = []
    async for token in provider.stream("gpt-4o-mini", messages, temperature=0.2):
        chunks.append(token)

    assert chunks == tokens
    assert sleep_calls == [1, 2, 4]
    assert completions.calls == [
        {
            "model": "gpt-4o-mini",
            "messages": messages,
            "stream": True,
            "opts": {"temperature": 0.2},
        }
        for _ in range(4)
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
    original_import_module = importlib.import_module

    def _raising_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "openai":
            raise ModuleNotFoundError("No module named 'openai'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _raising_import)
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name, package=None: (_raise_module_not_found(name) if name == "openai" or name.startswith("openai.") else original_import_module(name, package)),
    )

    def _raise_module_not_found(name: str) -> ModuleType:
        raise ModuleNotFoundError(f"No module named '{name}'")
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


def test_provider_prompts_upgrade_when_async_client_not_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provide guidance when AsyncOpenAI attribute exists but is not callable."""

    dummy_openai = ModuleType("openai")
    dummy_openai.AsyncOpenAI = object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", dummy_openai)
    monkeypatch.delitem(sys.modules, "src.providers.openai_client", raising=False)

    module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))

    with pytest.raises(ImportError, match=r"openai>=1\.30\.0"):
        provider_cls()


@pytest.mark.parametrize("env_value", ["", "  "])
def test_provider_reports_missing_key_for_blank_env(
    monkeypatch: pytest.MonkeyPatch, env_value: str
) -> None:
    """Blank OPENAI_API_KEY values should raise an explicit ValueError."""

    module = importlib.import_module("src.providers.openai_client")
    provider_cls = cast(Type[Any], getattr(module, "OpenAIProvider"))

    def _factory(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover - defensive guard
        pytest.fail("AsyncOpenAI factory should not be invoked when the API key is missing")

    monkeypatch.setattr(module, "_resolve_async_openai", lambda: cast(Any, _factory))
    monkeypatch.setenv("OPENAI_API_KEY", env_value)

    with pytest.raises(ValueError, match=r"OPENAI_API_KEY is required"):
        provider_cls()
