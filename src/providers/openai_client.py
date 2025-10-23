
from __future__ import annotations

import os
from typing import Any, AsyncIterator, Iterable, Mapping, Sequence, cast

from openai import AsyncOpenAI

MessageParam = Mapping[str, object]


class OpenAIProvider:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
