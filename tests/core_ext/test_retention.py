import types
import sys
from typing import Dict, List

import pytest

from src.core_ext import retention


@pytest.fixture(autouse=True)
def _clear_embedder_cache():
    retention._EMBEDDER_CACHE.clear()
    yield
    retention._EMBEDDER_CACHE.clear()


class _DummyGenAI(types.SimpleNamespace):
    configured_keys: List[str]
    embeddings: Dict[str, List[float]]

    def __init__(self) -> None:
        super().__init__()
        self.configured_keys = []
        self.embeddings = {}

    def configure(self, api_key: str) -> None:  # type: ignore[override]
        self.configured_keys.append(api_key)

    def embed_content(self, *, model: str, content: str):  # type: ignore[override]
        return {"embedding": self.embeddings.get(content, [1.0, 0.0])}


def _install_dummy_genai(monkeypatch: pytest.MonkeyPatch, dummy: _DummyGenAI) -> None:
    google_module = types.ModuleType("google")
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.generativeai", dummy)
    setattr(google_module, "generativeai", dummy)


def _compute_with_provider() -> float:
    before = [{"content": "hello"}]
    after = [{"content": "hello"}]
    result = retention.compute_semantic_retention(before, after)
    assert result is not None
    return result


def test_gemini_embedder_prefers_google_key(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyGenAI()
    _install_dummy_genai(monkeypatch, dummy)
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "primary-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    score = _compute_with_provider()

    assert score == pytest.approx(1.0)
    assert dummy.configured_keys == ["primary-key"]


def test_gemini_embedder_falls_back_to_legacy_key(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyGenAI()
    _install_dummy_genai(monkeypatch, dummy)
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fallback-key")

    score = _compute_with_provider()

    assert score == pytest.approx(1.0)
    assert dummy.configured_keys == ["fallback-key"]
