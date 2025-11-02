"""Regression tests for the Birdseye codemap update routine."""

from __future__ import annotations

import importlib.abc
import importlib.util
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
import sys

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "codemap" / "update.py"


def _load_update_module():
    spec = importlib.util.spec_from_file_location("codemap.update", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load codemap.update module")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert isinstance(loader, importlib.abc.Loader)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


@contextmanager
def chdir(path: Path) -> Iterator[None]:
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


def _write(path: Path, content: str, *, mtime: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    timestamp = int(mtime.timestamp())
    os.utime(path, times=(timestamp, timestamp))


def test_run_update_refreshes_hot_list_metadata(tmp_path: Path) -> None:
    module = _load_update_module()
    UpdateOptions = module.UpdateOptions
    run_update = module.run_update

    project_root = tmp_path
    src = project_root / "src"
    mtime = datetime(2024, 2, 3, 4, 5, 6, tzinfo=timezone.utc)

    _write(
        src / "omega.py",
        '"""Omega module."""\n',
        mtime=mtime,
    )

    hot_path = project_root / "docs" / "birdseye" / "hot.json"
    hot_path.parent.mkdir(parents=True, exist_ok=True)
    hot_entries = [
        {"id": "src/omega.py", "reason": "Critical entry point"},
        {"id": "src/zeta.py", "reason": "Legacy integration"},
    ]
    hot_payload = {
        "generated_at": "2000-01-01T00:00:00Z",
        "entries": hot_entries,
        "mtime": "2000-01-01T00:00:00Z",
    }
    hot_path.write_text(json.dumps(hot_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    options = UpdateOptions(targets=(Path("src/omega.py"),), emit="index+caps")

    with chdir(project_root):
        run_update(options)

    index_path = project_root / "docs" / "birdseye" / "index.json"
    hot = json.loads(hot_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))

    assert hot["entries"] == hot_entries

    generated_at = hot["generated_at"]
    mtime_value = hot["mtime"]

    assert generated_at == index["generated_at"]
    assert mtime_value == index["mtime"]

    datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    datetime.fromisoformat(mtime_value.replace("Z", "+00:00"))


def test_run_update_generates_iso8601_metadata_with_two_hop_dependencies(tmp_path: Path) -> None:
    module = _load_update_module()
    UpdateOptions = module.UpdateOptions
    run_update = module.run_update

    project_root = tmp_path
    src = project_root / "src"
    mtime_base = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    _write(
        src / "alpha.py",
        '"""Alpha module."""\nimport src.beta\n',
        mtime=mtime_base,
    )
    _write(
        src / "beta.py",
        '"""Beta module."""\nimport src.gamma\n',
        mtime=mtime_base.replace(year=2023),
    )
    _write(
        src / "gamma.py",
        '"""Gamma module."""\n',
        mtime=mtime_base.replace(year=2022),
    )
    _write(
        src / "delta.py",
        '"""Delta module."""\nimport src.alpha\n',
        mtime=mtime_base.replace(year=2021),
    )
    _write(
        src / "epsilon.py",
        '"""Epsilon module."""\nimport src.delta\n',
        mtime=mtime_base.replace(year=2020),
    )

    options = UpdateOptions(targets=(Path("src/alpha.py"),), emit="index+caps")

    with chdir(project_root):
        run_update(options)

    index_path = project_root / "docs" / "birdseye" / "index.json"
    with index_path.open(encoding="utf-8") as fh:
        index = json.load(fh)

    generated_at = index["generated_at"]
    assert generated_at.endswith("Z")
    datetime.fromisoformat(generated_at.replace("Z", "+00:00"))

    expected_nodes = {
        "src/alpha.py",
        "src/beta.py",
        "src/gamma.py",
        "src/delta.py",
        "src/epsilon.py",
    }
    assert set(index["nodes"].keys()) == expected_nodes

    # Ensure mtimes are emitted in ISO8601 and match actual filesystem timestamps.
    for identifier, node in index["nodes"].items():
        mtime_value = datetime.fromisoformat(node["mtime"].replace("Z", "+00:00"))
        path = project_root / identifier
        stat = path.stat()
        assert int(stat.st_mtime) == int(mtime_value.timestamp())

    expected_edges = {
        ("src/alpha.py", "src/beta.py"),
        ("src/beta.py", "src/gamma.py"),
        ("src/delta.py", "src/alpha.py"),
        ("src/epsilon.py", "src/delta.py"),
    }
    assert {tuple(edge) for edge in index["edges"]} == expected_edges

    capsule_dir = project_root / "docs" / "birdseye" / "caps"
    for identifier in expected_nodes:
        capsule_path = capsule_dir / f"{Path(identifier).with_suffix('').as_posix().replace('/', '.')}.json"
        with capsule_path.open(encoding="utf-8") as fh:
            capsule = json.load(fh)
        assert capsule["generated_at"] == generated_at
        assert capsule["mtime"] == index["nodes"][identifier]["mtime"]


def test_run_update_rejects_non_source_targets(tmp_path: Path) -> None:
    module = _load_update_module()
    UpdateOptions = module.UpdateOptions
    run_update = module.run_update

    project_root = tmp_path
    index_path = project_root / "docs" / "birdseye" / "index.json"
    original_payload = {"generated_at": "2020-01-01T00:00:00Z", "nodes": {}, "edges": [], "mtime": "2020-01-01T00:00:00Z"}
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(original_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    options = UpdateOptions(targets=(Path("docs/birdseye/index.json"),), emit="index")

    with chdir(project_root), pytest.raises(ValueError):
        run_update(options)

    assert json.loads(index_path.read_text(encoding="utf-8")) == original_payload
