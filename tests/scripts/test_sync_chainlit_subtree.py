"""sync_chainlit_subtree.sh のドライラン挙動とエラー処理を検証する。"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Sequence

import pytest

_SCRIPT = Path("scripts/sync_chainlit_subtree.sh").resolve()


def _ensure_bash_available() -> None:
    """bash が検出できるかどうかを検証する。"""
    if shutil.which("bash") is None:
        pytest.skip("bash が必要なテストスイート")


@pytest.fixture(name="fake_repo")
def fixture_fake_repo(tmp_path: Path) -> Path:
    """擬似的な git リポジトリ構造を生成する。"""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    return repo_dir


@pytest.fixture(name="subprocess_calls")
def fixture_subprocess_calls(monkeypatch: pytest.MonkeyPatch) -> List[List[str]]:
    """subprocess.run の呼び出しを記録する。"""
    recorded: List[List[str]] = []
    real_run = subprocess.run

    def _spy(cmd: Sequence[str] | str, *args, **kwargs):  # type: ignore[override]
        if isinstance(cmd, (list, tuple)):
            recorded.append([str(part) for part in cmd])
        else:
            recorded.append([str(cmd)])
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _spy)
    return recorded


def _write_git_stub(base_dir: Path, *, fail_on_subtree: bool) -> tuple[Path, Path]:
    bin_dir = base_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    log_path = base_dir / "git_stub.log"
    fail_flag = "1" if fail_on_subtree else "0"
    script_path = bin_dir / "git"
    script_path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail

printf "%s\\n" "$0 $*" >> "{log_path}"

if [[ "$1" == "subtree" && "$2" == "pull" ]]; then
    if [[ "{fail_flag}" == "1" ]]; then
        printf "forced subtree failure\\n" >&2
        exit 42
    fi
fi

exit 0
""".format(log_path=log_path, fail_flag=fail_flag),
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return script_path, log_path


def _base_command() -> List[str]:
    return [
        str(_SCRIPT),
        "--prefix",
        "upstream/chainlit",
        "--repo",
        "https://example.com/chainlit.git",
        "--tag",
        "v1.2.3",
    ]


def test_dry_run_prints_expected_commands(
    fake_repo: Path, subprocess_calls: List[List[str]], tmp_path: Path
) -> None:
    _ensure_bash_available()

    git_bin, log_path = _write_git_stub(tmp_path, fail_on_subtree=False)
    env = os.environ.copy()
    env["GIT_BIN"] = str(git_bin)

    completed = subprocess.run(
        [*_base_command(), "--dry-run"],
        check=True,
        capture_output=True,
        text=True,
        cwd=fake_repo,
        env=env,
    )

    assert subprocess_calls[0][0].endswith("sync_chainlit_subtree.sh")
    assert "git fetch https://example.com/chainlit.git refs/tags/v1.2.3:refs/tags/v1.2.3" in completed.stdout
    assert "git subtree pull --prefix upstream/chainlit https://example.com/chainlit.git v1.2.3" in completed.stdout
    assert not log_path.exists()


def test_subtree_failure_bubbles_up(
    fake_repo: Path, subprocess_calls: List[List[str]], tmp_path: Path
) -> None:
    _ensure_bash_available()

    git_bin, log_path = _write_git_stub(tmp_path, fail_on_subtree=True)
    env = os.environ.copy()
    env["GIT_BIN"] = str(git_bin)

    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        subprocess.run(
            _base_command(),
            check=True,
            capture_output=True,
            text=True,
            cwd=fake_repo,
            env=env,
        )

    assert subprocess_calls[0][0].endswith("sync_chainlit_subtree.sh")
    assert excinfo.value.returncode == 42
    log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert any("git fetch" in line for line in log_lines)
    assert any("git subtree pull" in line for line in log_lines)


def test_remote_is_used_for_subtree_pull(
    fake_repo: Path, subprocess_calls: List[List[str]], tmp_path: Path
) -> None:
    _ensure_bash_available()

    git_bin, log_path = _write_git_stub(tmp_path, fail_on_subtree=False)
    env = os.environ.copy()
    env["GIT_BIN"] = str(git_bin)

    subprocess.run(
        [*_base_command(), "--remote", "origin"],
        check=True,
        capture_output=True,
        text=True,
        cwd=fake_repo,
        env=env,
    )

    assert subprocess_calls[0][0].endswith("sync_chainlit_subtree.sh")
    assert subprocess_calls[0][-1] == "origin"

    log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    subtree_line = next(
        (line for line in log_lines if "git subtree pull" in line),
        "",
    )
    assert "git subtree pull --prefix upstream/chainlit origin v1.2.3" in subtree_line


def test_skips_when_bash_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    with pytest.raises(pytest.skip.Exception):
        _ensure_bash_available()
