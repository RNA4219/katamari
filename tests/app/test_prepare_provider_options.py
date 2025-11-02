from __future__ import annotations

import json
import os
import sys
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import ModuleType
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
    source_path = project_root / "src" / "app.py"

    class SanitizedLoader(SourceFileLoader):
        def get_source(self, fullname: str) -> str:  # type: ignore[override]
            source = source_path.read_text(encoding="utf-8")
            sentinel = "\nif show_debug:"
            if sentinel in source:
                source = source.split(sentinel, 1)[0] + "\n"
            return source

        def get_code(self, fullname: str):  # type: ignore[override]
            source = self.get_source(fullname)
            return compile(source, self.path, "exec", dont_inherit=True)

    loader = SanitizedLoader("src.app", str(source_path))
    spec = spec_from_loader("src.app", loader, origin=str(source_path))
    if spec is None:
        raise RuntimeError("failed to build spec for src.app")
    module = module_from_spec(spec)
    module.__file__ = str(source_path)
    module.__package__ = "src"
    src_package = sys.modules.setdefault("src", ModuleType("src"))
    src_package.__path__ = [str(project_root / "src")]
    sys.modules["src.app"] = module
    loader.exec_module(module)
    yield module
    for module_name in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(module_name, None)
    sys.modules.pop("src.app", None)
    sys.modules.pop("src", None)
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


@pytest.mark.parametrize(
    "model_id",
    [
        "gpt-5-thinking",
        "gpt-5-thinking-pro",
        "gpt-5-thinking-mini",
        "gpt-5-thinking-nano",
    ],
)
def test_prepare_provider_options_thinking_effort_default(app_module, model_id: str) -> None:
    options = app_module._prepare_provider_options(model_id, {})
    reasoning = options.get("reasoning")

    assert reasoning is not None
    assert reasoning.get("effort") == app_module._REASONING_DEFAULT["effort"]


def test_prepare_provider_options_thinking_effort_preserved_with_user_reasoning(app_module) -> None:
    options = app_module._prepare_provider_options(
        "gpt-5-thinking",
        {"reasoning": {"parallel": False}},
    )

    reasoning = options.get("reasoning")

    assert reasoning is not None
    assert reasoning.get("effort") == app_module._REASONING_DEFAULT["effort"]


def test_load_parallel_reasoning_models_uses_registry(
    app_module, monkeypatch
) -> None:
    registry_path = Path(app_module.__file__).resolve().parents[1] / "config" / "model_registry.json"
    custom_registry = [
        {"id": "gpt-5-thinking", "parallel": True},
        {"id": "gpt-5-thinking-pro", "parallel": False},
        {"id": "thinking-beta", "parallel": True},
        {"parallel": True},
    ]
    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs):  # type: ignore[override]
        if self == registry_path:
            return json.dumps(custom_registry)
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text, raising=False)

    models = app_module._load_parallel_reasoning_models()

    assert models == frozenset({"gpt-5-thinking", "thinking-beta"})
