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


def test_compute_semantic_retention_recovers_after_setting_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    before = [{"content": "hello"}]
    after = [{"content": "hello"}]

    assert retention.compute_semantic_retention(before, after) is None

    created_keys: List[str] = []

    class _DummyOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.embeddings = types.SimpleNamespace(create=self._create)
            created_keys.append(api_key)

        def _create(self, *, model: str, input: str):
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(embedding=[1.0, 0.0])]
            )

    module = types.ModuleType("openai")
    setattr(module, "OpenAI", _DummyOpenAI)
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")

    score = retention.compute_semantic_retention(before, after)

    assert score == pytest.approx(1.0)
    assert created_keys == ["dummy-key"]


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


def test_gemini_embedder_falls_back_to_google_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyGenAI()
    _install_dummy_genai(monkeypatch, dummy)
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-api-key")

    score = _compute_with_provider()

    assert score == pytest.approx(1.0)
    assert dummy.configured_keys == ["google-api-key"]


def test_embedder_rebuilds_after_env_update(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyGenAI()
    _install_dummy_genai(monkeypatch, dummy)
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    embedder = retention.get_embedder("gemini")

    assert embedder is None
    assert "gemini" not in retention._EMBEDDER_CACHE

    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "after-key")

    rebuilt = retention.get_embedder("gemini")

    assert rebuilt is not None
    cached_signature, cached_embedder = retention._EMBEDDER_CACHE["gemini"]
    assert cached_embedder is rebuilt
    assert ("GOOGLE_GEMINI_API_KEY", "after-key") in cached_signature
    assert rebuilt("sample text") == [1.0, 0.0]


def test_get_embedder_rebuilds_after_setting_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert retention.get_embedder("openai") is None
    assert "openai" not in retention._EMBEDDER_CACHE

    module = types.ModuleType("openai")

    class _DummyOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.embeddings = types.SimpleNamespace(create=self._create)

        def _create(self, *, model: str, input: str):
            return types.SimpleNamespace(data=[types.SimpleNamespace(embedding=[1.0, 0.0])])

    setattr(module, "OpenAI", _DummyOpenAI)
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_API_KEY", "after-key")

    embedder = retention.get_embedder("openai")

    assert embedder is not None
    cached_signature, cached_embedder = retention._EMBEDDER_CACHE["openai"]
    assert cached_embedder is embedder
    assert ("OPENAI_API_KEY", "after-key") in cached_signature
