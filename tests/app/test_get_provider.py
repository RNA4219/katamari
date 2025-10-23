"""Tests for the provider factory exposed by :mod:`src.app`."""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest


@pytest.fixture()
def app_module(tmp_path) -> Iterator[object]:
    """Import :mod:`src.app` with an isolated Chainlit configuration."""

    app_root = tmp_path / "app"
    app_root.mkdir()
    previous_root = os.environ.get("CHAINLIT_APP_ROOT")
    os.environ["CHAINLIT_APP_ROOT"] = str(app_root)
    project_root = Path(__file__).resolve().parents[2]
    added_paths: list[str] = []
    for path in [project_root, project_root / "src"]:
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
            added_paths.append(str(path))
    for module_name in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(module_name, None)
    sys.modules.pop("src.app", None)
    module = import_module("src.app")
    yield module
    for module_name in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(module_name, None)
    sys.modules.pop("src.app", None)
    for path in added_paths:
        if path in sys.path:
            sys.path.remove(path)
    if previous_root is None:
        os.environ.pop("CHAINLIT_APP_ROOT", None)
    else:
        os.environ["CHAINLIT_APP_ROOT"] = previous_root


@pytest.fixture()
def stub_openai(monkeypatch):
    """Avoid constructing the real OpenAI client during tests."""

    from providers import openai_client

    class _StubOpenAI:
        def __init__(self, **_):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **__: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content=""),
                                message=SimpleNamespace(content=""),
                            )
                        ]
                    )
                )
            )

    monkeypatch.setattr(openai_client, "AsyncOpenAI", _StubOpenAI)


@pytest.fixture(name="stub_genai")
def fixture_stub_genai(monkeypatch):
    """Provide a stubbed google generative AI module."""

    from providers import google_gemini_client

    stub = SimpleNamespace(
        configure=lambda **_: None,
        GenerativeModel=lambda name: SimpleNamespace(name=name),
    )
    monkeypatch.setattr(google_gemini_client, "_genai", stub, raising=False)
    return google_gemini_client


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_get_provider_returns_openai_for_gpt_models(app_module, stub_openai):
    provider = app_module.get_provider("gpt-4o-mini")

    from providers.openai_client import OpenAIProvider

    assert isinstance(provider, OpenAIProvider)


def test_get_provider_returns_gemini_for_prefixed_models(app_module, stub_genai):
    provider = app_module.get_provider("gemini-2.5-flash")

    assert isinstance(provider, stub_genai.GoogleGeminiProvider)


@pytest.mark.anyio("asyncio")
async def test_thinking_model_stream_passes_reasoning(app_module):
    calls = []

    async def fake_stream(*, model, messages, **kw):
        calls.append(kw)

    opts = app_module._prepare_provider_options("gpt-5-thinking", {"temperature": 0.5})
    await fake_stream(model="gpt-5-thinking", messages=[], **opts)
    assert calls[0]["reasoning"] == {"effort": "medium", "parallel": True}

    opts = app_module._prepare_provider_options("gpt-5-main", {"temperature": 0.5})
    await fake_stream(model="gpt-5-main", messages=[], **opts)
    assert "reasoning" not in calls[1]


@pytest.mark.anyio("asyncio")
async def test_openai_provider_forwards_extra_kwargs(monkeypatch: pytest.MonkeyPatch):
    from providers import openai_client

    calls = []

    async def fake_create(**kwargs):
        calls.append(kwargs)
        if kwargs.get("stream"):
            async def agen():
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content="chunk"),
                            message=SimpleNamespace(content=None),
                        )
                    ]
                )

            return agen()
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="complete"))]
        )

    stub_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))
    monkeypatch.setattr(openai_client, "AsyncOpenAI", lambda **_: stub_client)
    provider = openai_client.OpenAIProvider()
    messages = [{"role": "user", "content": "Ping"}]

    async for _ in provider.stream("gpt-5-main", messages, temperature=0.7, reasoning={"effort": "medium"}):
        pass
    assert calls[0]["reasoning"] == {"effort": "medium"}

    await provider.complete("gpt-5-main", messages, temperature=0.1, reasoning={"effort": "low"})
    assert calls[1]["reasoning"] == {"effort": "low"}


@pytest.mark.anyio("asyncio")
async def test_google_provider_forwards_extra_kwargs():
    from src.providers.google_gemini_client import GoogleGeminiProvider

    records = []

    def make_model(name):  # noqa: ARG001
        def generate_content(*, contents, stream=False, **kwargs):
            records.append({"stream": stream, "opts": kwargs})
            if stream:
                return iter([SimpleNamespace(text="alpha")])
            return SimpleNamespace(text="omega")

        return SimpleNamespace(generate_content=generate_content)

    module = SimpleNamespace(configure=lambda **_: None, GenerativeModel=make_model)
    provider = GoogleGeminiProvider(api_key="stub", genai_module=module)
    messages = [{"role": "user", "content": "Hello"}]

    async for _ in provider.stream("gemini-2.5-pro", messages, reasoning={"effort": "medium"}):
        pass
    assert records[0]["opts"]["reasoning"] == {"effort": "medium"}

    await provider.complete("gemini-2.5-pro", messages, reasoning={"effort": "low"})
    assert records[1]["opts"]["reasoning"] == {"effort": "low"}
