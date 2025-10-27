
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Mapping, Sequence, cast

MessageParam = Mapping[str, object]

if TYPE_CHECKING:
    from openai import AsyncOpenAI as _AsyncOpenAI

    AsyncOpenAICallable = type[_AsyncOpenAI]
else:
    AsyncOpenAICallable = Callable[..., Any]

AsyncOpenAI: AsyncOpenAICallable | None = None


def _resolve_async_openai() -> AsyncOpenAICallable:
    global AsyncOpenAI
    if AsyncOpenAI is not None:
        return cast(AsyncOpenAICallable, AsyncOpenAI)

    try:
        from openai import AsyncOpenAI as _AsyncOpenAI  # type: ignore import-not-found
    except ModuleNotFoundError as exc:  # pragma: no cover - tested via unit test
        raise RuntimeError(
            "OpenAI client dependency 'openai' is not installed. Install the 'openai' package to use OpenAIProvider."
        ) from exc

    AsyncOpenAI = cast(AsyncOpenAICallable, _AsyncOpenAI)
    return AsyncOpenAI


class OpenAIProvider:
    def __init__(self) -> None:
        client_factory = _resolve_async_openai()
        self.client = client_factory(api_key=os.getenv("OPENAI_API_KEY"))

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
