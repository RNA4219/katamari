from __future__ import annotations

import json
import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture()
def app_module(tmp_path) -> Iterator[object]:
    app_root = tmp_path / "app"
    app_root.mkdir()
    previous_root = os.environ.get("CHAINLIT_APP_ROOT")
    os.environ["CHAINLIT_APP_ROOT"] = str(app_root)
    project_root = Path(__file__).resolve().parents[2]
    added_paths: list[str] = []
    for path in (project_root, project_root / "src"):
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


@pytest.mark.parametrize(
    "model_id, expect_parallel",
    [
        ("gpt-5-thinking", True),
        ("gpt-5-thinking-pro", True),
        ("gpt-5-thinking-mini", False),
        ("gpt-5-thinking-nano", False),
    ],
)
def test_prepare_provider_options_parallel_flag(app_module, model_id: str, expect_parallel: bool) -> None:
    options = app_module._prepare_provider_options(model_id, {})
    reasoning = options.get("reasoning")

    if expect_parallel:
        assert reasoning is not None
        assert reasoning.get("parallel") is True
    else:
        if reasoning is None:
            return
        assert reasoning.get("parallel") in (None, False)


def test_load_parallel_reasoning_models_uses_registry(monkeypatch, tmp_path, app_module) -> None:
    registry_path = Path(app_module.__file__).resolve().parents[1] / "config" / "model_registry.json"
    registry_payload = json.dumps(
        [
            {"id": "gpt-5-thinking", "parallel": False},
            {"id": "gpt-5-thinking-pro", "parallel": True},
            {"id": "gpt-5-thinking-mini", "parallel": None},
        ]
    )
    original_read_text = Path.read_text

    def _mock_read_text(self: Path, *args, **kwargs):
        if self == registry_path:
            return registry_payload
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _mock_read_text)

    result = app_module._load_parallel_reasoning_models()

    assert result == frozenset({"gpt-5-thinking-pro"})
