"""`codemap.update` のコア動作を検証するテスト。"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from importlib import util as importlib_util
from pathlib import Path
from textwrap import dedent
from types import ModuleType
from typing import Any, cast

import pytest


ISO_8601_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REPO_ROOT = Path(__file__).resolve().parents[3]

MODULE_PATH = (
    Path(__file__)
    .resolve()
    .parents[3]
    / "third_party"
    / "Day8"
    / "workflow-cookbook"
    / "tools"
    / "codemap"
    / "update.py"
)


def _load_module() -> ModuleType:
    spec = importlib_util.spec_from_file_location("codemap_update", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load codemap.update module")
    module = importlib_util.module_from_spec(spec)
    loader = cast(Any, spec.loader)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _write(path: Path, content: str, *, mtime: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    timestamp = mtime.replace(tzinfo=timezone.utc).timestamp()
    os.utime(path, (timestamp, timestamp))


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_iso(mtime: datetime) -> str:
    return mtime.replace(tzinfo=timezone.utc, microsecond=0).isoformat().replace("+00:00", "Z")


def test_hot_json_generated_at_and_mtime_are_iso8601() -> None:
    hot_path = REPO_ROOT / "docs" / "birdseye" / "hot.json"
    hot = _load(hot_path)

    generated_at = hot["generated_at"]
    mtime = hot["mtime"]

    assert isinstance(generated_at, str)
    assert isinstance(mtime, str)
    assert ISO_8601_UTC.match(generated_at)
    assert ISO_8601_UTC.match(mtime)


def test_run_update_generates_codemap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    UpdateOptions = cast(Any, getattr(module, "UpdateOptions"))
    run_update = cast(Any, getattr(module, "run_update"))

    project_root = tmp_path

    helper_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    main_time = datetime(2024, 1, 2, 9, 30, 0, tzinfo=timezone.utc)
    guide_time = datetime(2024, 1, 3, 18, 45, 0, tzinfo=timezone.utc)

    _write(
        project_root / "src/utils/helpers.py",
        dedent(
            '''\
            """Utility helpers."""

            def helper_fn() -> None:
                pass
            '''
        ),
        mtime=helper_time,
    )

    _write(
        project_root / "src/main.py",
        dedent(
            '''\
            """Main module."""

            from src.utils import helpers


            def run() -> None:
                helpers.helper_fn()
            '''
        ),
        mtime=main_time,
    )

    _write(
        project_root / "docs/guide.md",
        """# Guide\n\nSee the [main module](../src/main.py) for details.\n""",
        mtime=guide_time,
    )

    monkeypatch.chdir(project_root)

    run_update(UpdateOptions(targets=(Path("src"), Path("docs")), emit="index+caps"))

    index_path = project_root / "docs/birdseye/index.json"
    caps_dir = project_root / "docs/birdseye/caps"

    assert index_path.exists()
    assert caps_dir.is_dir()

    index = _load(index_path)
    assert isinstance(index["generated_at"], str)
    assert ISO_8601_UTC.match(index["generated_at"])  # type: ignore[arg-type]

    nodes = index["nodes"]  # type: ignore[assignment]
    assert {"src/main.py", "src/utils/helpers.py", "docs/guide.md"} <= set(nodes.keys())

    helper_caps_path = Path(nodes["src/utils/helpers.py"]["caps"])  # type: ignore[index]
    main_caps_path = Path(nodes["src/main.py"]["caps"])  # type: ignore[index]
    guide_caps_path = Path(nodes["docs/guide.md"]["caps"])  # type: ignore[index]

    helper_caps = _load(project_root / helper_caps_path)
    main_caps = _load(project_root / main_caps_path)
    guide_caps = _load(project_root / guide_caps_path)

    generated_at = index["generated_at"]
    assert helper_caps["generated_at"] == generated_at
    assert main_caps["generated_at"] == generated_at
    assert guide_caps["generated_at"] == generated_at

    assert helper_caps["deps_in"] == ["src/main.py"]
    assert helper_caps["deps_out"] == []

    assert main_caps["deps_out"] == ["src/utils/helpers.py"]
    assert main_caps["deps_in"] == ["docs/guide.md"]

    assert guide_caps["deps_in"] == []
    assert guide_caps["deps_out"] == ["src/main.py"]

    expected_helper_mtime = _as_iso(helper_time)
    expected_main_mtime = _as_iso(main_time)
    expected_guide_mtime = _as_iso(guide_time)

    assert nodes["src/utils/helpers.py"]["mtime"] == expected_helper_mtime  # type: ignore[index]
    assert nodes["src/main.py"]["mtime"] == expected_main_mtime  # type: ignore[index]
    assert nodes["docs/guide.md"]["mtime"] == expected_guide_mtime  # type: ignore[index]

    assert helper_caps["mtime"] == expected_helper_mtime
    assert main_caps["mtime"] == expected_main_mtime
    assert guide_caps["mtime"] == expected_guide_mtime

    index_edges = {tuple(edge) for edge in index["edges"]}  # type: ignore[list-item]
    assert (
        ("src/main.py", "src/utils/helpers.py") in index_edges
        and ("docs/guide.md", "src/main.py") in index_edges
    )

    assert index["mtime"] == expected_guide_mtime
