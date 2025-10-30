from __future__ import annotations

import asyncio
import os
import sys
from time import perf_counter
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Mapping, Sequence, cast

from core_ext.logging import InferenceLogRecord, StructuredLogger

MessageParam = Mapping[str, object]

_MISSING_OPENAI_MESSAGE = (
    'OpenAI provider requires openai>=1.30.0. Upgrade via `pip install --upgrade "openai>=1.30.0"`.'
)

_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
_PROVIDER_LOGGER = StructuredLogger(logger_name="katamari.provider")

__all__ = ["AsyncOpenAI", "OpenAIProvider"]

if TYPE_CHECKING:
    from openai import AsyncOpenAI as AsyncOpenAIClient
else:  # pragma: no cover - used only for typing fallbacks at runtime
    class AsyncOpenAIClient:  # type: ignore[too-few-public-methods]
        """Runtime placeholder for the OpenAI async client."""

        ...

AsyncOpenAIFactory = Callable[..., AsyncOpenAIClient]


def _missing_async_openai_factory(*_: Any, **__: Any) -> AsyncOpenAIClient:
    raise ImportError(_MISSING_OPENAI_MESSAGE)


AsyncOpenAI: AsyncOpenAIFactory | None = None
_async_openai_factory: AsyncOpenAIFactory | None = None
_openai_module: Any | None = sys.modules.get("openai")


def _register_async_openai(factory: AsyncOpenAIFactory | None) -> AsyncOpenAIFactory:
    global AsyncOpenAI, _async_openai_factory
    AsyncOpenAI = factory
    _async_openai_factory = factory
    if factory is None:
        return _missing_async_openai_factory
    return factory

if _openai_module is not None:
    candidate = getattr(_openai_module, "AsyncOpenAI", None)
    if callable(candidate):
        _register_async_openai(cast(AsyncOpenAIFactory, candidate))
    else:
        _openai_module = None
        _register_async_openai(None)


def _resolve_async_openai() -> AsyncOpenAIFactory:
    global AsyncOpenAI, _async_openai_factory, _openai_module

    if AsyncOpenAI is not None:
        factory = AsyncOpenAI
        _async_openai_factory = factory
        return factory

    cached_factory = _async_openai_factory
    if cached_factory is not None:
        module = _openai_module
        if module is not None:
            candidate = getattr(module, "AsyncOpenAI", None)
            if callable(candidate) and candidate is not cached_factory:
                return _register_async_openai(cast(AsyncOpenAIFactory, candidate))
        return cached_factory

    module = _openai_module
    if module is not None:
        candidate = getattr(module, "AsyncOpenAI", None)
        if callable(candidate):
            return _register_async_openai(cast(AsyncOpenAIFactory, candidate))
        _openai_module = None
        _register_async_openai(None)
        return _missing_async_openai_factory

    try:
        runtime_openai = __import__("openai") if module is None else module
    except ModuleNotFoundError as exc:  # pragma: no cover - tested via unit test
        _register_async_openai(None)
        raise ImportError(_MISSING_OPENAI_MESSAGE) from exc
    except ImportError:  # pragma: no cover - tested via unit test
        _register_async_openai(None)
        raise

    candidate = getattr(runtime_openai, "AsyncOpenAI", None)
    if not callable(candidate):
        _openai_module = None
        _register_async_openai(None)
        raise ImportError(_MISSING_OPENAI_MESSAGE)

    _openai_module = runtime_openai
    return _register_async_openai(cast(AsyncOpenAIFactory, candidate))


class OpenAIProvider:
    def __init__(self) -> None:
        async_openai_factory = _resolve_async_openai()
        raw_key = os.getenv("OPENAI_API_KEY")
        if raw_key is None:
            raise ValueError("OPENAI_API_KEY is required")

        api_key = raw_key.strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")

        self.client = async_openai_factory(api_key=api_key)


    async def stream(
        self,
        model: str,
        messages: Sequence[MessageParam],
        **opts: Any,
    ) -> AsyncIterator[str]:
        attempt = 0
        seen_tokens: list[str] = []
        start = perf_counter()

        while True:
            attempt += 1
            try:
                stream = await self.client.chat.completions.create(
                    model=model,
                    messages=cast(Any, messages),
                    stream=True,
                    **opts,
                )
                stream_iter = cast(AsyncIterator[Any], stream)
                index = 0
                async for part in stream_iter:
                    choice = getattr(part, "choices", [None])[0]
                    delta = getattr(choice, "delta", None)
                    content = getattr(delta, "content", "") if delta is not None else ""
                    if not content:
                        continue
                    token = str(content)
                    if index < len(seen_tokens):
                        if token == seen_tokens[index]:
                            index += 1
                            continue
                        index = len(seen_tokens)
                    seen_tokens.append(token)
                    index += 1
                    yield token
                return
            except asyncio.CancelledError:  # pragma: no cover - cooperative cancellation
                raise
            except BaseException as exc:
                retryable = getattr(exc, "retryable", None)
                is_retryable = True if not isinstance(retryable, bool) else retryable
                try:
                    setattr(exc, "retryable", is_retryable)
                except Exception:  # pragma: no cover - defensive
                    pass

                retry_index = attempt - 1
                if not is_retryable or retry_index > len(_BACKOFF_SECONDS) - 1:
                    raise

                delay = _BACKOFF_SECONDS[retry_index]
                elapsed_ms = (perf_counter() - start) * 1000.0
                _PROVIDER_LOGGER.emit(
                    InferenceLogRecord(
                        status="failure",
                        model=model,
                        chain="openai.stream.retry",
                        token_in=0,
                        token_out=0,
                        compress_ratio=0.0,
                        step_latency_ms=[],
                        latency_ms=elapsed_ms,
                        retryable=True,
                        error=f"attempt={attempt} delay={delay:.1f}s",
                    )
                )
                await asyncio.sleep(delay)

    async def complete(
        self,
        model: str,
        messages: Sequence[MessageParam],
        **opts: Any,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=cast(Any, messages),
            stream=False,
            **opts,
        )
        completion = cast(Any, response)
        choice = completion.choices[0]
        content = getattr(choice.message, "content", "")
        return str(content or "")
