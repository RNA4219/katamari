from __future__ import annotations

import asyncio
import os
import sys
from time import perf_counter
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Literal, Mapping, Sequence, cast

from core_ext.logging import InferenceLogRecord, StructuredLogger

MessageParam = Mapping[str, object]

_MISSING_OPENAI_MESSAGE = (
    'OpenAI provider requires openai>=1.30.0. Upgrade via `pip install --upgrade "openai>=1.30.0"`.'
)

_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)
_PROVIDER_LOGGER = StructuredLogger(logger_name="katamari.provider")
_REQUEST_LOGGER = StructuredLogger()

__all__ = ["AsyncOpenAI", "OpenAIProvider"]

if TYPE_CHECKING:
    from openai import AsyncOpenAI as AsyncOpenAIClient
else:  # pragma: no cover - used only for typing fallbacks at runtime

    class AsyncOpenAIClient:  # type: ignore[too-few-public-methods]
        """Runtime placeholder for the OpenAI async client."""

        ...

AsyncOpenAIFactory = Callable[..., AsyncOpenAIClient]


async def _start_chat_stream(
    client: AsyncOpenAIClient,
    *,
    model: str,
    messages: Sequence[MessageParam],
    options: Mapping[str, Any],
) -> AsyncIterator[Any]:
    """Create a streaming chat completion iterator."""

    stream = await client.chat.completions.create(
        model=model,
        messages=cast(Any, messages),
        stream=True,
        **dict(options),
    )
    return cast(AsyncIterator[Any], stream)


def _extract_token(part: Any) -> str | None:
    """Return the SSE token content from a streamed part if present."""

    def _is_sequence(value: Any) -> bool:
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))

    def _collect_text(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if _is_sequence(value):
            fragments: list[str] = []
            for item in value:
                fragments.extend(_collect_text(item))
            return fragments
        if isinstance(value, Mapping):
            fragments: list[str] = []
            for key, item in value.items():
                if key == "text":
                    fragments.extend(_collect_text(item))
                elif _is_sequence(item) or isinstance(item, Mapping) or getattr(item, "text", None) is not None:
                    fragments.extend(_collect_text(item))
            return fragments

        text_attr = getattr(value, "text", None)
        if text_attr is not None:
            return _collect_text(text_attr)

        if hasattr(value, "__dict__"):
            fragments: list[str] = []
            for item in vars(value).values():
                if item is value:
                    continue
                if isinstance(item, Mapping) or _is_sequence(item) or getattr(item, "text", None) is not None:
                    fragments.extend(_collect_text(item))
            return fragments
        return []

    choices = getattr(part, "choices", None)
    if not choices:
        return None
    choice = choices[0]
    delta = getattr(choice, "delta", None)
    content = getattr(delta, "content", "") if delta is not None else ""
    fragments = _collect_text(content)
    if not fragments and isinstance(content, str):
        fragments = [content]
    fragments = [fragment for fragment in fragments if isinstance(fragment, str) and fragment]
    if not fragments:
        return None
    token = "".join(fragments)
    return token or None


def _coerce_retryable(exc: BaseException) -> bool:
    """Normalise the retryable flag on exceptions to a boolean."""

    retryable = getattr(exc, "retryable", None)
    is_retryable = retryable if isinstance(retryable, bool) else True
    try:
        setattr(exc, "retryable", is_retryable)
    except Exception:  # pragma: no cover - defensive
        pass
    return is_retryable


def _set_retryable(exc: BaseException, value: bool) -> None:
    """Update the retryable flag if the exception allows attribute assignment."""

    try:
        setattr(exc, "retryable", value)
    except Exception:  # pragma: no cover - defensive
        pass


def _emit_stream_metric(
    *,
    status: Literal["success", "failure"],
    model: str,
    chain: str,
    latency_ms: float,
    token_out: int,
    retryable: bool | None,
    error: str | None = None,
    provider_log: bool = False,
) -> None:
    """Emit structured stream metrics to request (and optionally provider) logs."""

    record = InferenceLogRecord(
        status=status,
        model=model,
        chain=chain,
        token_in=0,
        token_out=token_out,
        compress_ratio=0.0,
        step_latency_ms=[],
        latency_ms=latency_ms,
        retryable=retryable,
        error=error,
    )
    if provider_log:
        _PROVIDER_LOGGER.emit(record)
    _REQUEST_LOGGER.emit(record)


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
        options = cast(Mapping[str, Any], dict(opts))
        seen_tokens: list[str] = []
        start = perf_counter()

        for attempt_index in range(len(_BACKOFF_SECONDS) + 1):
            try:
                stream_iter = await _start_chat_stream(
                    self.client,
                    model=model,
                    messages=messages,
                    options=options,
                )
                index = 0
                async for part in stream_iter:
                    token = _extract_token(part)
                    if token is None:
                        continue
                    if index < len(seen_tokens):
                        if token == seen_tokens[index]:
                            index += 1
                            continue
                        index = len(seen_tokens)
                    seen_tokens.append(token)
                    index += 1
                    yield token

                elapsed_ms = (perf_counter() - start) * 1000.0
                _emit_stream_metric(
                    status="success",
                    model=model,
                    chain="openai.stream",
                    latency_ms=elapsed_ms,
                    token_out=len(seen_tokens),
                    retryable=None,
                )
                return
            except asyncio.CancelledError:  # pragma: no cover - cooperative cancellation
                raise
            except BaseException as exc:
                is_retryable = _coerce_retryable(exc)
                elapsed_ms = (perf_counter() - start) * 1000.0
                attempt_number = attempt_index + 1
                has_remaining = attempt_index < len(_BACKOFF_SECONDS)

                if not is_retryable or not has_remaining:
                    if is_retryable and not has_remaining:
                        _set_retryable(exc, False)
                        is_retryable = False
                    retry_attr = getattr(exc, "retryable", is_retryable)
                    retry_flag = retry_attr if isinstance(retry_attr, bool) else False
                    _emit_stream_metric(
                        status="failure",
                        model=model,
                        chain="openai.stream.failure",
                        latency_ms=elapsed_ms,
                        token_out=len(seen_tokens),
                        retryable=retry_flag,
                        error=(
                            f"attempt={attempt_number} terminal error={type(exc).__name__}: {exc}"
                        ),
                        provider_log=True,
                    )
                    raise

                delay = _BACKOFF_SECONDS[attempt_index]
                _emit_stream_metric(
                    status="failure",
                    model=model,
                    chain="openai.stream.retry",
                    latency_ms=elapsed_ms,
                    token_out=len(seen_tokens),
                    retryable=True,
                    error=(
                        f"attempt={attempt_number} delay={delay:.1f}s error={type(exc).__name__}: {exc}"
                    ),
                    provider_log=True,
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
