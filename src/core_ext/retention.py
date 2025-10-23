import math
import os
from typing import Callable, Dict, Iterable, Optional, Sequence

Message = Dict[str, str]
Embedder = Callable[[str], Sequence[float]]

_EMBEDDER_CACHE: Dict[str, Optional[Embedder]] = {}


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
        from openai import OpenAI  # type: ignore
    except ImportError:
        return None
    model = os.getenv("SEMANTIC_RETENTION_OPENAI_MODEL", "text-embedding-3-large")
    client = OpenAI(api_key=api_key)

    def _embed(text: str) -> Sequence[float]:
        response = client.embeddings.create(model=model, input=text)
        return response.data[0].embedding  # type: ignore[no-any-return]

    return _embed


def _build_gemini_embedder() -> Optional[Embedder]:
    api_key = None
    for env_var in ("GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY"):
        value = os.getenv(env_var)
        if value:
            api_key = value
            break
    if not api_key:
        return None
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError:
        return None
    model = os.getenv("SEMANTIC_RETENTION_GEMINI_MODEL", "text-embedding-004")
    genai.configure(api_key=api_key)

    def _embed(text: str) -> Sequence[float]:
        response = genai.embed_content(model=model, content=text)
        embedding = response.get("embedding")
        if embedding is None:
            raise ValueError("Gemini embedding response missing 'embedding'")
        return embedding

    return _embed


def get_embedder(provider: str) -> Optional[Embedder]:
    key = provider.lower()
    if key not in _EMBEDDER_CACHE:
        if key == "openai":
            _EMBEDDER_CACHE[key] = _build_openai_embedder()
        elif key == "gemini":
            _EMBEDDER_CACHE[key] = _build_gemini_embedder()
        else:
            _EMBEDDER_CACHE[key] = None
    return _EMBEDDER_CACHE[key]


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
