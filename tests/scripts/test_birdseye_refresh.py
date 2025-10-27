"""Birdseye refresh CLI の挙動を検証するテスト。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


@pytest.fixture(name="birdseye_workspace")
def fixture_birdseye_workspace(tmp_path: Path) -> Path:
    """Birdseye JSON 一式を一時ディレクトリにコピーする。"""
    src_dir = Path("docs/birdseye")
    dest_dir = tmp_path / "birdseye"
    shutil.copytree(src_dir, dest_dir)
    return dest_dir


def _load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _run_cli(workspace: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    script = Path("scripts/birdseye_refresh.py")
    command: list[str] = [
        sys.executable,
        str(script),
        "--docs-dir",
        str(workspace),
        *args,
    ]
    completed = subprocess.run(
        command,
        cwd=Path.cwd(),
        check=True,
        capture_output=True,
    )
    return completed


def test_run_cli_uses_sys_executable(birdseye_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom_python = "/opt/custom/python"
    monkeypatch.setattr(sys, "executable", custom_python)

    recorded_args: list[str] = []

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        recorded_args.extend(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    completed = _run_cli(birdseye_workspace, "--dry-run")

    assert recorded_args[0] == custom_python
    assert Path(recorded_args[1]) == Path("scripts/birdseye_refresh.py")
    assert completed.returncode == 0


def test_cli_handles_original_edges_without_typeerror(birdseye_workspace: Path) -> None:
    original_index = _load_json(Path("docs/birdseye/index.json"))
    workspace_index = _load_json(birdseye_workspace / "index.json")

    assert workspace_index["edges"] == original_index["edges"]

    completed = _run_cli(birdseye_workspace)
    stdout = completed.stdout.decode("utf-8")
    stderr = completed.stderr.decode("utf-8")

    assert completed.returncode == 0
    assert "TypeError" not in stdout
    assert "TypeError" not in stderr


def test_generated_at_and_mtime_are_sequential(birdseye_workspace: Path) -> None:
    _run_cli(birdseye_workspace)

    index = _load_json(birdseye_workspace / "index.json")
    hot = _load_json(birdseye_workspace / "hot.json")
    cap_files = sorted((birdseye_workspace / "caps").glob("*.json"))

    refreshed = [
        index,
        *(_load_json(path) for path in cap_files),
        hot,
    ]

    generated_values = [item["generated_at"] for item in refreshed]
    mtime_values = [item["mtime"] for item in refreshed]

    assert all(isinstance(value, str) and value.isdigit() and len(value) == 5 for value in generated_values)
    assert all(isinstance(value, str) and value.isdigit() and len(value) == 5 for value in mtime_values)

    assert generated_values == mtime_values

    expected = {f"{offset:05d}" for offset in range(1, len(generated_values) + 1)}
    assert set(generated_values) == expected


def test_caps_dependencies_follow_index_edges(birdseye_workspace: Path) -> None:
    _run_cli(birdseye_workspace)

    index = _load_json(birdseye_workspace / "index.json")
    edges: List[Tuple[str, str]] = [tuple(edge) for edge in index["edges"]]  # type: ignore[list-item]

    outgoing: Dict[str, List[str]] = {}
    incoming: Dict[str, List[str]] = {}
    for source, target in edges:
        outgoing.setdefault(source, []).append(target)
        incoming.setdefault(target, []).append(source)

    caps_dir = birdseye_workspace / "caps"
    for cap_path in caps_dir.glob("*.json"):
        cap = _load_json(cap_path)
        node_id = cap["id"]
        expected_out = sorted(outgoing.get(node_id, []))
        expected_in = sorted(incoming.get(node_id, []))

        assert cap["deps_out"] == expected_out
        assert cap["deps_in"] == expected_in


def test_dry_run_does_not_write(birdseye_workspace: Path) -> None:
    before = {
        path.relative_to(birdseye_workspace): _load_json(path)
        for path in birdseye_workspace.rglob("*.json")
    }

    _run_cli(birdseye_workspace, "--dry-run")

    after = {
        path.relative_to(birdseye_workspace): _load_json(path)
        for path in birdseye_workspace.rglob("*.json")
    }

    assert before == after
