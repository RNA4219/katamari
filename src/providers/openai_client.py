
import os
from typing import AsyncIterator, Dict, List
from openai import AsyncOpenAI

class OpenAIProvider:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def stream(self, model: str, messages: List[Dict], **opts) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=model, messages=messages, stream=True, **opts
        )
        async for part in stream:
            delta = part.choices[0].delta.content or ""
            if delta:
                yield delta

    async def complete(self, model: str, messages: List[Dict], **opts) -> str:
        resp = await self.client.chat.completions.create(
            model=model, messages=messages, stream=False, **opts
        )
        return resp.choices[0].message.content or ""
