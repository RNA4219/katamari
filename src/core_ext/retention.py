from __future__ import annotations

import math
import os
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Tuple, cast

Message = Mapping[str, Any]
Embedder = Callable[[str], Sequence[float]]
_Signature = Tuple[Tuple[str, str], ...]

_EMBEDDER_CACHE: Dict[str, Tuple[_Signature, Embedder]] = {}


def _norm(vec: Sequence[float]) -> float:
    return math.sqrt(sum(v * v for v in vec))


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    if not a or not b:
        return None
    denom = _norm(a) * _norm(b)
    if denom == 0:
        return None
    return round(sum(x * y for x, y in zip(a, b)) / denom, 3)


def _aggregate(messages: Iterable[Message]) -> str:
    return "\n".join(m.get("content", "") for m in messages if m.get("content"))


def _build_openai_embedder() -> Optional[Embedder]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    model = os.getenv("SEMANTIC_RETENTION_OPENAI_MODEL", "text-embedding-3-large")
    client = OpenAI(api_key=api_key)

    def _embed(text: str) -> Sequence[float]:
        response = client.embeddings.create(model=model, input=text)
        return cast(Sequence[float], response.data[0].embedding)

    return _embed


def _build_gemini_embedder() -> Optional[Embedder]:
    api_key = None
    for env_var in ("GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY"):
        value = os.getenv(env_var)
        if value:
            api_key = value
            break
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
    except ImportError:
        return None
    model = os.getenv("SEMANTIC_RETENTION_GEMINI_MODEL", "text-embedding-004")
    configure = getattr(genai, "configure", None)
    if callable(configure):
        configure(api_key=api_key)
    else:  # pragma: no cover - defensive guard
        return None

    def _embed(text: str) -> Sequence[float]:
        embed_content = getattr(genai, "embed_content", None)
        if not callable(embed_content):
            raise RuntimeError("Gemini embed_content API unavailable")
        response = embed_content(model=model, content=text)
        embedding = response.get("embedding")
        if embedding is None:
            raise ValueError("Gemini embedding response missing 'embedding'")
        return cast(Sequence[float], embedding)

    return _embed


def _provider_signature(provider: str) -> _Signature:
    if provider == "openai":
        env_vars = ("OPENAI_API_KEY", "SEMANTIC_RETENTION_OPENAI_MODEL")
    elif provider == "gemini":
        env_vars = (
            "GOOGLE_GEMINI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "SEMANTIC_RETENTION_GEMINI_MODEL",
        )
    else:
        env_vars = ()
    return tuple((name, os.getenv(name, "") or "") for name in env_vars)


def get_embedder(provider: str) -> Optional[Embedder]:
    key = provider.lower()
    builder: Optional[Callable[[], Optional[Embedder]]]
    if key == "openai":
        builder = _build_openai_embedder
    elif key == "gemini":
        builder = _build_gemini_embedder
    else:
        return None

    signature = _provider_signature(key)
    cached = _EMBEDDER_CACHE.get(key)
    if cached is not None:
        cached_signature, cached_embedder = cached
        if cached_signature == signature:
            return cached_embedder

    embedder = builder()
    if embedder is None:
        _EMBEDDER_CACHE.pop(key, None)
        return None
    _EMBEDDER_CACHE[key] = (signature, embedder)
    return embedder


def compute_semantic_retention(
    before: Iterable[Message],
    after: Iterable[Message],
    embedder: Optional[Embedder] = None,
) -> Optional[float]:
    provider = os.getenv("SEMANTIC_RETENTION_PROVIDER", "").strip().lower()
    if embedder is None:
        if provider in {"", "none", "off", "0", "false"}:
            return None
        embedder = get_embedder(provider)
        if embedder is None:
            return None
    before_text = _aggregate(before)
    after_text = _aggregate(after)
    if not before_text or not after_text:
        return None
    before_vec = list(embedder(before_text))
    after_vec = list(embedder(after_text))
    return _cosine_similarity(before_vec, after_vec)
