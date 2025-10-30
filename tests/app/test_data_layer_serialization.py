"""データレイヤーのシリアライズ手段を検証する静的テスト。"""

from __future__ import annotations

from pathlib import Path


DATA_LAYER_ROOT = Path("upstream/chainlit/cypress/e2e/data_layer")


def test_thread_history_serialization_uses_json() -> None:
    target = DATA_LAYER_ROOT / "main.py"
    content = target.read_text(encoding="utf-8")

    assert "pickle" not in content
    assert "json" in content


def test_thread_history_artifact_extension() -> None:
    target = DATA_LAYER_ROOT / "spec.cy.ts"
    content = target.read_text(encoding="utf-8")

    assert "thread_history.json" in content
