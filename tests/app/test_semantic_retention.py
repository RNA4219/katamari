from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest


@pytest.fixture()
def app_module(tmp_path) -> Iterator[Any]:
    app_root = tmp_path / "app"
    app_root.mkdir()

    previous_root = os.environ.get("CHAINLIT_APP_ROOT")
    os.environ["CHAINLIT_APP_ROOT"] = str(app_root)

    project_root = Path(__file__).resolve().parents[2]
    added_paths: List[str] = []

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

    module = import_module("src.app")

    yield module

    for key in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(key, None)
    sys.modules.pop("src.app", None)
    for _ in added_paths:
        sys.path.pop(0)
    if previous_root is None:
        os.environ.pop("CHAINLIT_APP_ROOT", None)
    else:
        os.environ["CHAINLIT_APP_ROOT"] = previous_root


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.asyncio
@pytest.mark.anyio
async def test_ensure_semantic_retention_swallow_compute_errors(
    app_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEMANTIC_RETENTION_PROVIDER", "custom")

    calls: List[Dict[str, Any]] = []

    def _boom(*args: object, **kwargs: object) -> None:
        calls.append({"args": args, "kwargs": kwargs})
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "compute_semantic_retention", _boom)

    metrics: Dict[str, Any] = {}

    result = await app_module._ensure_semantic_retention(
        before=(
            {
                "role": "user",
                "content": "hello",
            },
        ),
        after=(
            {
                "role": "assistant",
                "content": "hi",
            },
        ),
        metrics=metrics,
    )

    assert result is None
    assert metrics["semantic_retention"] is None
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.anyio
async def test_ensure_semantic_retention_normalizes_invalid_existing_metric(
    app_module: Any,
) -> None:
    metrics: Dict[str, Any] = {"semantic_retention": "invalid"}

    result = await app_module._ensure_semantic_retention(
        before=(
            {
                "role": "user",
                "content": "hello",
            },
        ),
        after=(
            {
                "role": "assistant",
                "content": "hi",
            },
        ),
        metrics=metrics,
    )

    assert result is None
    assert metrics["semantic_retention"] is None
