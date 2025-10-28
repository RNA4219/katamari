from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Mapping, Optional, Sequence, cast

MessageParam = Mapping[str, object]

_MISSING_OPENAI_MESSAGE = (
    'OpenAI provider requires openai>=1.30.0. Install it with `pip install --upgrade "openai>=1.30.0"`.'
)

if TYPE_CHECKING:
    from openai import AsyncOpenAI as _TypedAsyncOpenAI

    AsyncOpenAIFactory = Callable[..., _TypedAsyncOpenAI]
else:
    AsyncOpenAIFactory = Callable[..., Any]

_ImportedAsyncOpenAICallable: Optional[AsyncOpenAIFactory]
try:  # pragma: no cover - import only when available
    from openai import AsyncOpenAI as _ImportedAsyncOpenAI
except (ModuleNotFoundError, ImportError):  # pragma: no cover - tested via unit test
    _ImportedAsyncOpenAICallable = None
else:
    _ImportedAsyncOpenAICallable = cast(AsyncOpenAIFactory, _ImportedAsyncOpenAI)

_async_openai_factory: Optional[AsyncOpenAIFactory] = _ImportedAsyncOpenAICallable

AsyncOpenAI: Optional[AsyncOpenAIFactory] = _async_openai_factory


def _resolve_async_openai() -> AsyncOpenAIFactory:
    global AsyncOpenAI
    global _async_openai_factory
    if _async_openai_factory is not None:
        return _async_openai_factory
    try:
        from openai import AsyncOpenAI as runtime_async_openai
    except (ModuleNotFoundError, ImportError) as exc:  # pragma: no cover - tested via unit test
        raise ImportError(_MISSING_OPENAI_MESSAGE) from exc
    _async_openai_factory = cast(AsyncOpenAIFactory, runtime_async_openai)
    AsyncOpenAI = _async_openai_factory
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
