"""Health and metrics endpoint tests."""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
import math
from typing import Iterator, List, Tuple

import pytest
from fastapi.testclient import TestClient

from scripts.perf.collect_metrics import _parse_prometheus


def _bootstrap_chainlit(tmp_path) -> Tuple[object, object, str | None, List[str]]:
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
    chainlit_server = import_module("chainlit.server")
    app_module = import_module("src.app")
    return chainlit_server.app, app_module, previous_root, added_paths


@pytest.fixture()
def app_context(tmp_path) -> Iterator[Tuple[object, object]]:
    app, module, previous_root, added_paths = _bootstrap_chainlit(tmp_path)
    yield app, module
    for key in [name for name in sys.modules if name.startswith("chainlit")]:
        sys.modules.pop(key, None)
    sys.modules.pop("src.app", None)
    for _ in added_paths:
        sys.path.pop(0)
    if previous_root is None:
        os.environ.pop("CHAINLIT_APP_ROOT", None)
    else:
        os.environ["CHAINLIT_APP_ROOT"] = previous_root


def test_healthz_endpoint_returns_ok_status(app_context) -> None:
    chainlit_app, _ = app_context
    client = TestClient(chainlit_app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint_exposes_trim_gauges(app_context) -> None:
    chainlit_app, app_module = app_context
    app_module.METRICS_REGISTRY.observe_trim(
        compress_ratio=0.75,
        semantic_retention=0.9,
    )
    client = TestClient(chainlit_app)

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "# HELP compress_ratio" in body
    assert "# TYPE compress_ratio gauge" in body
    assert "compress_ratio 0.75" in body
    assert "semantic_retention 0.9" in body
    assert response.headers["content-type"].startswith("text/plain")


def test_metrics_endpoint_reports_nan_for_missing_retention(app_context) -> None:
    chainlit_app, app_module = app_context
    app_module.METRICS_REGISTRY.observe_trim(
        compress_ratio=0.5,
        semantic_retention=0.8,
    )
    app_module.METRICS_REGISTRY.observe_trim(
        compress_ratio=0.6,
        semantic_retention=None,
    )
    client = TestClient(chainlit_app)

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "compress_ratio 0.6" in body
    assert "semantic_retention nan" in body


def test_metrics_endpoint_does_not_report_one_for_missing_retention(app_context) -> None:
    chainlit_app, app_module = app_context
    app_module.METRICS_REGISTRY.observe_trim(
        compress_ratio=0.7,
        semantic_retention=None,
    )

    client = TestClient(chainlit_app)

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "semantic_retention nan" in body
    assert "semantic_retention 1.0" not in body


def test_export_prometheus_outputs_nan_for_missing_retention(app_context) -> None:
    _, app_module = app_context
    registry = app_module.METRICS_REGISTRY
    registry.observe_trim(compress_ratio=0.8, semantic_retention=None)

    payload = registry.export_prometheus()

    assert "semantic_retention nan" in payload
    parsed = _parse_prometheus(payload)
    assert math.isnan(parsed["semantic_retention"])
