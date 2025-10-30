"""chainlit.utils の安全な import 動作に関するテスト"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
UTILS_PATH = ROOT / "upstream" / "chainlit" / "backend" / "chainlit" / "utils.py"
BACKEND_ROOT = UTILS_PATH.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _register_stub(name: str) -> ModuleType:
    module = ModuleType(name)
    sys.modules[name] = module
    return module


chainlit_pkg = _register_stub("chainlit")
chainlit_pkg.__path__ = [str(BACKEND_ROOT / "chainlit")]

_register_stub("chainlit.auth").ensure_jwt_secret = lambda: None

async def _async_noop(*args, **kwargs):  # pragma: no cover - utility
    return None


context_module = _register_stub("chainlit.context")
context_module.context = SimpleNamespace(
    emitter=SimpleNamespace(task_start=_async_noop, task_end=_async_noop)
)


logger_module = _register_stub("chainlit.logger")
logger_module.logger = SimpleNamespace(
    exception=lambda *args, **kwargs: None,
    warning=lambda *args, **kwargs: None,
)

SPEC = importlib.util.spec_from_file_location("chainlit.utils", UTILS_PATH)
assert SPEC and SPEC.loader  # pragma: no mutate
_utils = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(_utils)


class _FakeModule:
    __version__ = "1.0.0"


def test_check_module_version_disallowed_module(monkeypatch: pytest.MonkeyPatch) -> None:
    imported: list[str] = []

    def _fake_import(name: str, package: str | None = None):  # pragma: no cover - guard
        imported.append(name)
        return _FakeModule()

    monkeypatch.setattr(importlib, "import_module", _fake_import)

    result = _utils.check_module_version("malicious.module", "0.0.1")

    assert result is False
    assert imported == []


def test_check_module_version_allowed_module(monkeypatch: pytest.MonkeyPatch) -> None:
    imported: list[str] = []

    def _fake_import(name: str, package: str | None = None):
        imported.append(name)
        module = _FakeModule()
        module.__version__ = "2.0.0"
        return module

    monkeypatch.setattr(importlib, "import_module", _fake_import)

    result = _utils.check_module_version("langchain", "1.0.0")

    assert result is True
    assert imported == ["langchain"]
