from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Mapping, Optional, Sequence, cast

MessageParam = Mapping[str, object]

_MISSING_OPENAI_MESSAGE = (
    'OpenAI provider requires openai>=1.30.0. Install it with `pip install --upgrade "openai>=1.30.0"`.'
)

if TYPE_CHECKING:
    from openai import AsyncOpenAI

    AsyncOpenAIFactory = Callable[..., AsyncOpenAI]
else:
    AsyncOpenAIFactory = Callable[..., Any]

try:  # pragma: no cover - import only when available
    from openai import AsyncOpenAI as _AsyncOpenAI
except (ModuleNotFoundError, ImportError):  # pragma: no cover - tested via unit test
    _AsyncOpenAI = None  # type: ignore[assignment]

AsyncOpenAI: Optional[AsyncOpenAIFactory]
if _AsyncOpenAI is not None:
    AsyncOpenAI = cast(AsyncOpenAIFactory, _AsyncOpenAI)
else:
    AsyncOpenAI = None


def _resolve_async_openai() -> AsyncOpenAIFactory:
    global AsyncOpenAI
    if AsyncOpenAI is not None:
        return cast(AsyncOpenAIFactory, AsyncOpenAI)
    try:
        from openai import AsyncOpenAI as runtime_async_openai
    except (ModuleNotFoundError, ImportError) as exc:  # pragma: no cover - tested via unit test
        raise ImportError(_MISSING_OPENAI_MESSAGE) from exc
    AsyncOpenAI = cast(AsyncOpenAIFactory, runtime_async_openai)
    return cast(AsyncOpenAIFactory, AsyncOpenAI)


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
