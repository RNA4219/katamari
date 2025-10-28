from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from src.providers.google_gemini_client import GoogleGeminiProvider


class StubGenerativeModel:
    def __init__(self, name: str, stream_chunks: List[str], response_text: str) -> None:
        self.name = name
        self.stream_chunks = stream_chunks
        self.response_text = response_text
        self.calls: List[Dict[str, Any]] = []

    def generate_content(self, *, contents: List[Dict[str, Any]], stream: bool = False, **opts: Any) -> Any:
        record = {
            "contents": contents,
            "stream": stream,
            "opts": opts,
        }
        self.calls.append(record)
        if stream:
            return (SimpleNamespace(text=chunk) for chunk in self.stream_chunks)
        return SimpleNamespace(text=self.response_text)


class StubGenerativeAIModule:
    def __init__(self, *, stream_chunks: List[str], response_text: str) -> None:
        self.stream_chunks = stream_chunks
        self.response_text = response_text
        self.configure_kwargs: List[Dict[str, Any]] = []
        self.created_models: List[StubGenerativeModel] = []

    def configure(self, **kwargs: Any) -> None:
        self.configure_kwargs.append(kwargs)

    def GenerativeModel(self, name: str) -> StubGenerativeModel:
        model = StubGenerativeModel(name, self.stream_chunks, self.response_text)
        self.created_models.append(model)
        return model


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_stream_builds_request_and_splits_chunks() -> None:
    module = StubGenerativeAIModule(stream_chunks=["alpha\n\nbeta", "", "gamma"], response_text="ignored")
    provider = GoogleGeminiProvider(api_key="fake-key", genai_module=module)
    messages = [
        {"role": "system", "content": "Keep responses brief."},
        {"role": "user", "content": "Ping"},
        {"role": "assistant", "content": "Pong"},
    ]

    chunks: List[str] = []
    async for part in provider.stream("models/gemini-pro", messages, temperature=0.1):
        chunks.append(part)

    assert chunks == ["alpha", "beta", "gamma"]
    assert module.configure_kwargs == [{"api_key": "fake-key"}]
    assert [model.name for model in module.created_models] == ["models/gemini-pro"]
    call = module.created_models[0].calls[0]
    assert call["stream"] is True
    assert call["opts"]["temperature"] == 0.1
    assert call["contents"] == [
        {"role": "user", "parts": ["[system]\nKeep responses brief."]},
        {"role": "user", "parts": ["Ping"]},
        {"role": "model", "parts": ["Pong"]},
    ]


@pytest.mark.anyio("asyncio")
async def test_complete_returns_text_response() -> None:
    module = StubGenerativeAIModule(stream_chunks=[], response_text="final answer")
    provider = GoogleGeminiProvider(api_key="fake-key", genai_module=module)
    messages = [{"role": "user", "content": "Hello"}]

    result = await provider.complete("models/gemini-pro", messages, temperature=0.0)

    assert result == "final answer"
    call = module.created_models[0].calls[0]
    assert call["stream"] is False
    assert call["opts"]["temperature"] == 0.0
    assert call["contents"] == [{"role": "user", "parts": ["Hello"]}]


def test_init_configures_with_gemini_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "fallback-key")
    module = StubGenerativeAIModule(stream_chunks=[], response_text="unused")

    GoogleGeminiProvider(genai_module=module)

    assert module.configure_kwargs == [{"api_key": "fallback-key"}]


def test_init_configures_with_google_api_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "final-fallback")
    module = StubGenerativeAIModule(stream_chunks=[], response_text="unused")

    GoogleGeminiProvider(genai_module=module)

    assert module.configure_kwargs == [{"api_key": "final-fallback"}]


@pytest.mark.parametrize(
    "env_name",
    ["GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY"],
)
@pytest.mark.parametrize("api_key_value", ["", "   "])
def test_google_gemini_provider_ignores_blank_api_key(
    env_name: str, api_key_value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for variable in ("GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv(env_name, api_key_value)
    module = StubGenerativeAIModule(stream_chunks=[], response_text="unused")

    GoogleGeminiProvider(genai_module=module)

    assert module.configure_kwargs == []
