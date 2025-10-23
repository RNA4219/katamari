from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from typing import Any, AsyncIterator, Callable, Dict, Iterable, Iterator, List, Optional, Sequence, cast

_genai: Optional[Any] = None
_genai_module: Any

try:
    import google.generativeai as _genai_module
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    _genai_module = None

_genai = cast(Optional[Any], _genai_module)


class GoogleGeminiProvider:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        genai_module: Optional[Any] = None,
        model_factory: Optional[Callable[[Any, str], Any]] = None,
    ) -> None:
        module = genai_module or _genai
        if module is None:  # pragma: no cover - enforced at runtime
            raise RuntimeError(
                "google-generativeai is required. Install the package or "
                "inject a stub via genai_module."
            )
        self._genai: Any = module
        self._model_factory = model_factory or (lambda mod, name: mod.GenerativeModel(name))
        api_key_value = (
            api_key
            or os.getenv("GOOGLE_GEMINI_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if api_key_value:
            self._genai.configure(api_key=api_key_value)

    async def stream(
        self, model: str, messages: Sequence[Dict[str, Any]], **opts: Any
    ) -> AsyncIterator[str]:
        client = self._model_factory(self._genai, model)
        iterator_obj = await asyncio.to_thread(
            client.generate_content,
            contents=self._convert_messages(messages),
            stream=True,
            **self._clean_opts(opts),
        )
        iterator = iter(cast(Iterable[Any], iterator_obj))
        sentinel = SimpleNamespace()
        while True:
            chunk = await asyncio.to_thread(next, iterator, sentinel)
            if chunk is sentinel:
                break
            text_chunk = self._text(chunk)
            for part in self._split_stream_text(text_chunk):
                yield str(part)

    async def complete(
        self, model: str, messages: Sequence[Dict[str, Any]], **opts: Any
    ) -> str:
        client = self._model_factory(self._genai, model)
        response = await asyncio.to_thread(
            client.generate_content,
            contents=self._convert_messages(messages),
            stream=False,
            **self._clean_opts(opts),
        )
        return self._text(response)

    @staticmethod
    def _clean_opts(opts: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = dict(opts)
        cleaned.pop("stream", None)
        return cleaned

    @staticmethod
    def _text(chunk: Any) -> str:
        text = getattr(chunk, "text", "")
        return text or ""

    @staticmethod
    def _split_stream_text(text: str) -> List[str]:
        return [part for part in text.split("\n\n") if part]

    @staticmethod
    def _convert_messages(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        converted: List[Dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role", "user"))
            content = GoogleGeminiProvider._to_text(message.get("content"))
            if role == "assistant":
                role = "model"
            elif role == "system":
                role = "user"
                content = f"[system]\n{content}"
            converted.append({"role": role, "parts": [content]})
        return converted

    @staticmethod
    def _to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                str(item.get("text"))
                if isinstance(item, dict) and "text" in item
                else str(item)
                for item in content
            )
        if content is None:
            return ""
        return str(content)
