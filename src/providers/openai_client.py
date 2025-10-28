from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Mapping, Optional, Sequence, cast

MessageParam = Mapping[str, object]

_MISSING_OPENAI_MESSAGE = (
    'OpenAI provider requires openai>=1.30.0. Upgrade via `pip install --upgrade "openai>=1.30.0"`.'
)

if TYPE_CHECKING:
    from openai import AsyncOpenAI as AsyncOpenAIClient
else:  # pragma: no cover - used only for typing fallbacks at runtime
    class AsyncOpenAIClient:  # type: ignore[too-few-public-methods]
        """Runtime placeholder for the OpenAI async client."""

        ...

AsyncOpenAIFactory = Callable[..., AsyncOpenAIClient]

_async_openai_factory: Optional[AsyncOpenAIFactory] = None
_openai_module: Any | None = None
AsyncOpenAI: Optional[AsyncOpenAIFactory] = None
try:  # pragma: no cover - import only when available
    import openai as _imported_openai  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - tested via unit test
    pass
except ImportError:
    raise
else:
    _openai_module = _imported_openai
    _imported_async_openai = getattr(_imported_openai, "AsyncOpenAI", None)
    if callable(_imported_async_openai):
        AsyncOpenAI = cast(AsyncOpenAIFactory, _imported_async_openai)
        _async_openai_factory = AsyncOpenAI


def _resolve_async_openai() -> AsyncOpenAIFactory:
    global AsyncOpenAI, _async_openai_factory, _openai_module
    if AsyncOpenAI is not None and callable(AsyncOpenAI):
        if _async_openai_factory is not AsyncOpenAI:
            _async_openai_factory = AsyncOpenAI
        return AsyncOpenAI
    if _async_openai_factory is not None:
        return _async_openai_factory
    try:
        if _openai_module is None:
            import openai as runtime_openai  # type: ignore[import-not-found]
        else:
            runtime_openai = _openai_module
    except ModuleNotFoundError as exc:  # pragma: no cover - tested via unit test
        raise ImportError(_MISSING_OPENAI_MESSAGE) from exc
    except ImportError:  # pragma: no cover - tested via unit test
        raise
    candidate = getattr(runtime_openai, "AsyncOpenAI", None)
    if not callable(candidate):
        raise ImportError(_MISSING_OPENAI_MESSAGE)
    _openai_module = runtime_openai
    AsyncOpenAI = cast(AsyncOpenAIFactory, candidate)
    _async_openai_factory = AsyncOpenAI
    return _async_openai_factory


class OpenAIProvider:
    def __init__(self) -> None:
        async_openai_factory = _resolve_async_openai()
        self.client = async_openai_factory(api_key=os.getenv("OPENAI_API_KEY"))


    async def stream(
        self,
        model: str,
        messages: Sequence[MessageParam],
        **opts: Any,
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=model,
            messages=cast(Any, messages),
            stream=True,
            **opts,
        )
        stream_iter = cast(AsyncIterator[Any], stream)
        async for part in stream_iter:
            choice = getattr(part, "choices", [None])[0]
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", "") if delta is not None else ""
            if content:
                yield str(content)

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
