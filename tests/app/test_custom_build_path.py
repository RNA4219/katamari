from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture()
def chainlit_server(tmp_path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    app_root = tmp_path / "app"
    app_root.mkdir()
    config_dir = app_root / ".chainlit"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        """[meta]\ngenerated_by = \"0.3.1\"\n\n[project]\nuser_env = []\n\n[features]\n\n[UI]\nname = \"Test\"\n""",
        encoding="utf-8",
    )

    project_root = Path(__file__).resolve().parents[2]
    backend_root = project_root / "upstream" / "chainlit" / "backend"
    package_root = project_root / "upstream" / "chainlit"

    (package_root / "frontend" / "dist").mkdir(parents=True, exist_ok=True)
    (package_root / "libs" / "copilot" / "dist").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("CHAINLIT_APP_ROOT", str(app_root))
    monkeypatch.syspath_prepend(str(backend_root))

    for name in [key for key in sys.modules if key.startswith("chainlit")]:
        sys.modules.pop(name, None)

    server = import_module("chainlit.server")
    original_custom_build = server.config.ui.custom_build

    yield server

    server.config.ui.custom_build = original_custom_build
    for name in [key for key in sys.modules if key.startswith("chainlit")]:
        sys.modules.pop(name, None)


def test_get_build_dir_rejects_traversal(chainlit_server: ModuleType) -> None:
    app_root = Path(chainlit_server.APP_ROOT)
    outside_dir = app_root.parent / "outside"
    outside_dir.mkdir(exist_ok=True)
    chainlit_server.config.ui.custom_build = os.path.relpath(outside_dir, app_root)

    with pytest.raises(ValueError):
        chainlit_server.get_build_dir("frontend", "frontend")


def test_get_build_dir_accepts_safe_path(chainlit_server: ModuleType) -> None:
    app_root = Path(chainlit_server.APP_ROOT)
    safe_dir = app_root / "custom" / "dist"
    safe_dir.mkdir(parents=True, exist_ok=True)
    chainlit_server.config.ui.custom_build = os.path.relpath(safe_dir, app_root)

    result = chainlit_server.get_build_dir("frontend", "frontend")

    assert Path(result) == safe_dir


def test_get_build_dir_missing_custom_build(chainlit_server: ModuleType) -> None:
    app_root = Path(chainlit_server.APP_ROOT)
    missing_dir = app_root / "custom" / "dist"
    chainlit_server.config.ui.custom_build = os.path.relpath(missing_dir, app_root)

    with pytest.raises(FileNotFoundError):
        chainlit_server.get_build_dir("frontend", "frontend")
