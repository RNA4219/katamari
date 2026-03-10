"""Integration tests for /evolve endpoint."""

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
    previous_secret = os.environ.get("CHAINLIT_AUTH_SECRET")
    os.environ["CHAINLIT_APP_ROOT"] = str(app_root)
    os.environ["CHAINLIT_AUTH_SECRET"] = "test-secret-for-evolve"
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
        if previous_secret is None:
            os.environ.pop("CHAINLIT_AUTH_SECRET", None)
        else:
            os.environ["CHAINLIT_AUTH_SECRET"] = previous_secret


def test_evolve_endpoint_requires_authentication(app_module: object) -> None:
    """Test that /evolve endpoint requires Bearer token."""
    from fastapi.testclient import TestClient

    # Reset registry for clean state
    registry = app_module.MetricsRegistry()  # type: ignore[attr-defined]
    app_module.METRICS_REGISTRY = registry

    client = TestClient(app_module.chainlit_app)

    response = client.post(
        "/evolve",
        headers={
            "X-Seed-Prompt": "test prompt",
            "X-Objective": "test objective",
        },
    )

    assert response.status_code == 401


def test_evolve_endpoint_accepts_valid_token(app_module: object) -> None:
    """Test that /evolve endpoint accepts valid Bearer token."""
    from fastapi.testclient import TestClient

    # Reset registry for clean state
    registry = app_module.MetricsRegistry()  # type: ignore[attr-defined]
    app_module.METRICS_REGISTRY = registry

    client = TestClient(app_module.chainlit_app)

    response = client.post(
        "/evolve",
        headers={
            "Authorization": "Bearer test-secret-for-evolve",
            "X-Seed-Prompt": "Write a greeting",
            "X-Objective": "Create friendly greetings",
            "X-Population": "2",
            "X-Generations": "1",
        },
    )

    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert "bestPrompt" in data
    assert "history" in data
    assert isinstance(data["history"], list)


def test_evolve_endpoint_updates_metrics(app_module: object) -> None:
    """Test that /evolve endpoint updates evolution metrics."""
    from fastapi.testclient import TestClient

    # Reset registry for clean state
    registry = app_module.MetricsRegistry()  # type: ignore[attr-defined]
    app_module.METRICS_REGISTRY = registry

    client = TestClient(app_module.chainlit_app)

    # Verify initial metrics state
    initial_snapshot = registry.snapshot()
    assert initial_snapshot["evolution_success_total"] == 0
    assert initial_snapshot["evolution_failure_total"] == 0

    # Call evolve endpoint
    response = client.post(
        "/evolve",
        headers={
            "Authorization": "Bearer test-secret-for-evolve",
            "X-Seed-Prompt": "Test prompt",
            "X-Objective": "Test objective",
            "X-Population": "2",
            "X-Generations": "1",
        },
    )

    assert response.status_code == 200

    # Verify metrics were updated
    snapshot = registry.snapshot()
    assert snapshot["evolution_success_total"] == 1
    assert snapshot["evolution_failure_total"] == 0
    assert snapshot["evolution_latency_ms"] > 0


def test_evolve_endpoint_returns_history(app_module: object) -> None:
    """Test that /evolve endpoint returns evolution history."""
    from fastapi.testclient import TestClient

    # Reset registry for clean state
    registry = app_module.MetricsRegistry()  # type: ignore[attr-defined]
    app_module.METRICS_REGISTRY = registry

    client = TestClient(app_module.chainlit_app)

    response = client.post(
        "/evolve",
        headers={
            "Authorization": "Bearer test-secret-for-evolve",
            "X-Seed-Prompt": "Initial prompt",
            "X-Objective": "Improve quality",
            "X-Population": "2",
            "X-Generations": "2",
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify history structure
    history = data["history"]
    assert len(history) == 3  # gen 0, 1, 2

    for entry in history:
        assert "gen" in entry
        assert "candidates" in entry
        assert "scores" in entry
        assert "bestPrompt" in entry
        assert "evaluations" in entry