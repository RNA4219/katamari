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


@pytest.fixture(scope="module")
def utils_module() -> ModuleType:
    saved: dict[str, ModuleType] = {}
    for name in [key for key in sys.modules if key.startswith("chainlit")]:
        module = sys.modules.pop(name)
        if isinstance(module, ModuleType):
            saved[name] = module

    def _register_stub(name: str) -> ModuleType:
        module = ModuleType(name)
        sys.modules[name] = module
        return module

    chainlit_pkg = _register_stub("chainlit")
    chainlit_pkg.__path__ = [str(BACKEND_ROOT / "chainlit")]

    _register_stub("chainlit.auth").ensure_jwt_secret = lambda: None

    async def _async_noop(*args: object, **kwargs: object) -> None:  # pragma: no cover - utility
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

    spec = importlib.util.spec_from_file_location("chainlit.utils", UTILS_PATH)
    if not spec or not spec.loader:  # pragma: no cover - guard
        raise RuntimeError("failed to load chainlit.utils for testing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    yield module

    for key in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(key, None)
    for name, module in saved.items():
        sys.modules[name] = module


class _FakeModule:
    __version__ = "1.0.0"


def test_check_module_version_disallowed_module(utils_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    imported: list[str] = []

    def _fake_import(name: str, package: str | None = None):  # pragma: no cover - guard
        imported.append(name)
        return _FakeModule()

    monkeypatch.setattr(importlib, "import_module", _fake_import)

    result = utils_module.check_module_version("malicious.module", "0.0.1")

    assert result is False
    assert imported == []


def test_check_module_version_allowed_module(utils_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    imported: list[str] = []

    def _fake_import(name: str, package: str | None = None):
        imported.append(name)
        module = _FakeModule()
        module.__version__ = "2.0.0"
        return module

    monkeypatch.setattr(importlib, "import_module", _fake_import)

    result = utils_module.check_module_version("langchain", "1.0.0")

    assert result is True
    assert imported == ["langchain"]
