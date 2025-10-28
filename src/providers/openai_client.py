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
try:  # pragma: no cover - import only when available
    from openai import AsyncOpenAI as _imported_async_openai
except ModuleNotFoundError:  # pragma: no cover - tested via unit test
    pass
except ImportError as exc:  # pragma: no cover - tested via unit test
    if "AsyncOpenAI" not in str(exc):
        raise
else:
    if callable(_imported_async_openai):
        _async_openai_factory = cast(AsyncOpenAIFactory, _imported_async_openai)


def _resolve_async_openai() -> AsyncOpenAIFactory:
    global _async_openai_factory
    if _async_openai_factory is not None:
        return _async_openai_factory
    try:
        from openai import AsyncOpenAI as runtime_async_openai
    except ModuleNotFoundError as exc:  # pragma: no cover - tested via unit test
        raise ImportError(_MISSING_OPENAI_MESSAGE) from exc
    except ImportError as exc:  # pragma: no cover - tested via unit test
        if "AsyncOpenAI" not in str(exc):
            raise
        raise ImportError(_MISSING_OPENAI_MESSAGE) from exc
    if not callable(runtime_async_openai):
        raise ImportError(_MISSING_OPENAI_MESSAGE)
    _async_openai_factory = cast(AsyncOpenAIFactory, runtime_async_openai)
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
