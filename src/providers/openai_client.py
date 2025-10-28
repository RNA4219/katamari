from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Mapping, Sequence, cast

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from openai import AsyncOpenAI


MessageParam = Mapping[str, object]

_MISSING_OPENAI_MESSAGE = (
    "OpenAI provider requires the 'openai' package. Install it with `pip install openai`."
)

if TYPE_CHECKING:
    AsyncOpenAIFactory = Callable[..., AsyncOpenAI]
else:
    AsyncOpenAIFactory = Callable[..., Any]


def _resolve_async_openai() -> AsyncOpenAIFactory:
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as exc:
        raise ImportError(_MISSING_OPENAI_MESSAGE) from exc
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
