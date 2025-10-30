import types
import sys
from typing import Dict, List

import pytest

from src.core_ext import retention


@pytest.fixture(autouse=True)
def _clear_embedder_cache():
    retention.reset_embedder_cache()
    yield
    retention.reset_embedder_cache()


class _DummyGenAI(types.SimpleNamespace):
    configured_keys: List[str]
    embeddings: Dict[str, List[float]]
    requested_models: List[str]

    def __init__(self) -> None:
        super().__init__()
        self.configured_keys = []
        self.embeddings = {}
        self.requested_models = []

    def configure(self, api_key: str) -> None:  # type: ignore[override]
        self.configured_keys.append(api_key)

    def embed_content(self, *, model: str, content: str):  # type: ignore[override]
        self.requested_models.append(model)
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


def test_compute_semantic_retention_serializes_non_string_content() -> None:
    embed_inputs: List[str] = []

    def _embed(text: str) -> List[float]:
        embed_inputs.append(text)
        return [1.0]

    before = [
        {"content": ["hello", {"key": "value"}]},
        {"content": None},
        {"content": ""},
    ]
    after = [
        {"content": {"summary": "ok"}},
        {"content": ["bye"]},
    ]

    score = retention.compute_semantic_retention(before, after, embedder=_embed)

    assert score == pytest.approx(1.0)
    assert embed_inputs == [
        "['hello', {'key': 'value'}]",
        "{'summary': 'ok'}\n['bye']",
    ]


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


def test_compute_semantic_retention_rebuilds_after_api_key_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    module = types.ModuleType("openai")
    created_keys: List[str] = []
    embeddings_for_key = {
        "first-key": [1.0, 0.0],
        "second-key": [0.0, 1.0],
    }

    class _DummyOpenAI:
        def __init__(self, api_key: str) -> None:
            created_keys.append(api_key)
            self.api_key = api_key
            self.embeddings = types.SimpleNamespace(create=self._create)

        def _create(self, *, model: str, input: str):
            vector = embeddings_for_key[self.api_key]
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(embedding=vector)]
            )

    setattr(module, "OpenAI", _DummyOpenAI)
    monkeypatch.setitem(sys.modules, "openai", module)

    before = [{"content": "hello"}]
    after = [{"content": "hello"}]

    assert retention.compute_semantic_retention(before, after) is None

    monkeypatch.setenv("OPENAI_API_KEY", "first-key")
    first_score = retention.compute_semantic_retention(before, after)

    assert first_score == pytest.approx(1.0)
    assert created_keys == ["first-key"]

    monkeypatch.setenv("OPENAI_API_KEY", "second-key")
    second_score = retention.compute_semantic_retention(before, after)

    assert second_score == pytest.approx(1.0)
    assert created_keys == ["first-key", "second-key"]


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


def test_gemini_embedder_reconfigures_after_api_key_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _DummyGenAI()
    _install_dummy_genai(monkeypatch, dummy)
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "first-key")

    first = retention.get_embedder("gemini")

    assert first is not None
    assert dummy.configured_keys == ["first-key"]

    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "second-key")

    second = retention.get_embedder("gemini")

    assert second is not None
    assert second is not first
    assert dummy.configured_keys == ["first-key", "second-key"]


def test_embedder_rebuilds_after_env_update(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyGenAI()
    _install_dummy_genai(monkeypatch, dummy)
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    embedder = retention.get_embedder("gemini")

    assert embedder is None

    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "after-key")

    rebuilt = retention.get_embedder("gemini")

    assert rebuilt is not None
    cache_entry = retention._EMBEDDER_CACHE.get("gemini")
    assert cache_entry is not None
    _, cached_embedder = cache_entry
    assert cached_embedder is rebuilt
    assert rebuilt("sample text") == [1.0, 0.0]


def test_gemini_embedder_rebuilds_when_env_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy = _DummyGenAI()
    _install_dummy_genai(monkeypatch, dummy)
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "first-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("SEMANTIC_RETENTION_GEMINI_MODEL", "model-a")

    first = retention.get_embedder("gemini")

    assert first is not None
    first("payload")
    assert dummy.configured_keys == ["first-key"]
    assert dummy.requested_models == ["model-a"]

    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "second-key")
    monkeypatch.setenv("SEMANTIC_RETENTION_GEMINI_MODEL", "model-b")

    second = retention.get_embedder("gemini")

    assert second is not None
    assert second is not first
    second("payload")
    assert dummy.configured_keys == ["first-key", "second-key"]
    assert dummy.requested_models == ["model-a", "model-b"]


def test_openai_embedder_rebuilds_when_env_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "openai")

    created_keys: List[str] = []

    class _DummyOpenAI:
        def __init__(self, api_key: str) -> None:
            created_keys.append(api_key)
            self.embeddings = types.SimpleNamespace(create=self._create)

        def _create(self, *, model: str, input: str):  # pragma: no cover - dummy API
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(embedding=[1.0, 0.0])]
            )

    module = types.ModuleType("openai")
    setattr(module, "OpenAI", _DummyOpenAI)
    monkeypatch.setitem(sys.modules, "openai", module)

    monkeypatch.setenv("OPENAI_API_KEY", "first")
    first = retention.get_embedder("openai")

    assert first is not None
    assert created_keys == ["first"]

    monkeypatch.setenv("OPENAI_API_KEY", "second")
    second = retention.get_embedder("openai")

    assert second is not None
    assert second is not first
    assert created_keys == ["first", "second"]


@pytest.mark.parametrize("blank_value", ["", "   ", "\t"], ids=["empty", "spaces", "tab"])
def test_openai_embedder_ignores_blank_key(
    monkeypatch: pytest.MonkeyPatch, blank_value: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", blank_value)

    class _FailingOpenAI:
        def __init__(self, api_key: str) -> None:  # pragma: no cover - defensive
            raise AssertionError("embedder should not initialize with blank key")

    module = types.ModuleType("openai")
    setattr(module, "OpenAI", _FailingOpenAI)
    monkeypatch.setitem(sys.modules, "openai", module)

    assert retention.get_embedder("openai") is None


def test_gemini_embedder_ignores_blank_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = _DummyGenAI()
    _install_dummy_genai(monkeypatch, dummy)
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "   ")
    monkeypatch.setenv("GEMINI_API_KEY", "\t")
    monkeypatch.setenv("GOOGLE_API_KEY", "\n")

    assert retention.get_embedder("gemini") is None
    assert dummy.configured_keys == []


@pytest.mark.parametrize("blank_value", ["", "   ", "\t"], ids=["empty", "spaces", "tab"])
def test_compute_semantic_retention_ignores_blank_openai_key(
    monkeypatch: pytest.MonkeyPatch, blank_value: str
) -> None:
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", blank_value)

    class _FailingOpenAI:
        def __init__(self, api_key: str) -> None:  # pragma: no cover - defensive
            raise AssertionError("embedder should not initialize with blank key")

    module = types.ModuleType("openai")
    setattr(module, "OpenAI", _FailingOpenAI)
    monkeypatch.setitem(sys.modules, "openai", module)

    before = [{"content": "before"}]
    after = [{"content": "after"}]

    assert retention.get_embedder("openai") is None
    assert retention.compute_semantic_retention(before, after) is None


@pytest.mark.parametrize(
    "env_var",
    ["GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"],
)
@pytest.mark.parametrize("blank_value", ["", "   ", "\t"], ids=["empty", "spaces", "tab"])
def test_compute_semantic_retention_ignores_blank_gemini_keys(
    monkeypatch: pytest.MonkeyPatch, env_var: str, blank_value: str
) -> None:
    def _configure(*, api_key: str) -> None:  # pragma: no cover - defensive
        raise AssertionError("Gemini configure should not run with blank key")

    def _embed_content(*, model: str, content: str):  # pragma: no cover - defensive
        raise AssertionError("Gemini embed_content should not run with blank key")

    generativeai = types.SimpleNamespace(
        configure=_configure,
        embed_content=_embed_content,
    )
    google_module = types.ModuleType("google")
    setattr(google_module, "generativeai", generativeai)
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.generativeai", generativeai)

    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "gemini")
    for candidate in ("GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(candidate, raising=False)
    monkeypatch.setenv(env_var, blank_value)

    before = [{"content": "before"}]
    after = [{"content": "after"}]

    assert retention.get_embedder("gemini") is None
    assert retention.compute_semantic_retention(before, after) is None
