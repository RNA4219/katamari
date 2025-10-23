"""Tests for :func:`src.app.on_start`."""

from __future__ import annotations

import builtins
import math
import sys
from importlib import import_module
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest


if not hasattr(builtins, "isnan"):
    setattr(builtins, "isnan", math.isnan)


class _StubUserSession:
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}

    def get(self, key: str, default: Any | None = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value


class _StubChatSettings:
    instances: List["_StubChatSettings"] = []

    def __init__(self, *, inputs: List[Any]) -> None:
        self.inputs = list(inputs)
        self.__class__.instances.append(self)

    async def send(self) -> Dict[str, Any]:
        return {}


def _widget_factory() -> Any:
    def _factory(**kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(**kwargs)

    return _factory


@pytest.fixture()
def app_module(monkeypatch, tmp_path) -> Any:
    app_root = tmp_path / "chainlit"
    app_root.mkdir()
    monkeypatch.setenv("CHAINLIT_APP_ROOT", str(app_root))
    for name in [key for key in sys.modules if key.startswith("chainlit") or key == "src.app"]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    module = import_module("src.app")
    for widget_name in ("Select", "Slider", "TextInput", "Switch"):
        monkeypatch.setattr(module, widget_name, _widget_factory())
    monkeypatch.setattr(module.cl, "ChatSettings", _StubChatSettings)
    module.cl.user_session = _StubUserSession()
    _StubChatSettings.instances.clear()
    return module


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_on_start_uses_environment_defaults(monkeypatch, app_module) -> None:
    monkeypatch.setenv("DEFAULT_MODEL", "gpt-5-thinking")
    monkeypatch.setenv("DEFAULT_CHAIN", "reflect")

    await app_module.on_start()

    session = app_module.cl.user_session
    assert session.get("model") == "gpt-5-thinking"
    assert session.get("chain") == "reflect"

    chat_settings = _StubChatSettings.instances[-1]
    widgets = {widget.id: widget for widget in chat_settings.inputs}

    model_widget = widgets["model"]
    assert model_widget.values[model_widget.initial_index] == session.get("model")

    chain_widget = widgets["chain"]
    assert chain_widget.values[chain_widget.initial_index] == session.get("chain")

    assert widgets["trim_tokens"].initial == session.get("trim_tokens")
    assert widgets["min_turns"].initial == session.get("min_turns")
    assert widgets["persona_yaml"].initial == ""
    assert widgets["show_debug"].initial is session.get("show_debug")
