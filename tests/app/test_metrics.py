"""MetricsRegistry export behavior tests."""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture()
def app_module(tmp_path: Path) -> Iterator[object]:
    app_root = tmp_path / "app"
    app_root.mkdir()
    previous_root = os.environ.get("CHAINLIT_APP_ROOT")
    os.environ["CHAINLIT_APP_ROOT"] = str(app_root)
    added_paths: list[str] = []
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        added_paths.append(str(project_root))
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
        added_paths.append(str(src_path))
    for module_name in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(module_name, None)
    sys.modules.pop("src.app", None)
    try:
        module = import_module("src.app")
        yield module
    finally:
        sys.modules.pop("src.app", None)
        for key in [name for name in sys.modules if name.startswith("chainlit")]:
            sys.modules.pop(key, None)
        for _ in added_paths:
            sys.path.pop(0)
        if previous_root is None:
            os.environ.pop("CHAINLIT_APP_ROOT", None)
        else:
            os.environ["CHAINLIT_APP_ROOT"] = previous_root


def test_export_prometheus_reports_nan_when_retention_unset(app_module: object) -> None:
    registry = app_module.MetricsRegistry()  # type: ignore[attr-defined]

    payload = registry.export_prometheus()

    lines = payload.strip().splitlines()

    assert lines[-1] == "semantic_retention NaN"
    assert lines.count("semantic_retention NaN") == 1


def test_export_prometheus_formats_nan_for_missing_retention(app_module: object) -> None:
    registry = app_module.MetricsRegistry()  # type: ignore[attr-defined]

    registry.observe_trim(compress_ratio=0.5, semantic_retention=None)

    payload = registry.export_prometheus()

    lines = payload.strip().splitlines()

    assert lines[-1] == "semantic_retention NaN"


def test_export_prometheus_normalizes_nan_like_strings(app_module: object) -> None:
    registry = app_module.MetricsRegistry()  # type: ignore[attr-defined]

    registry.observe_trim(compress_ratio=0.5, semantic_retention="nan")

    payload = registry.export_prometheus()

    lines = payload.strip().splitlines()

    assert lines[-1] == "semantic_retention NaN"
