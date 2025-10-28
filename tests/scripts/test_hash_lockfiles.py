"""Tests for hash_lockfiles script."""

from __future__ import annotations

from pathlib import Path

import importlib

import pytest

from scripts.cache import hash_lockfiles


@pytest.fixture(autouse=True)
def reload_module() -> None:
    importlib.reload(hash_lockfiles)


def _write_lock(repo_root: Path, relative_path: str, content: str) -> Path:
    lock_path = repo_root / relative_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(content, encoding="utf-8")
    return lock_path


def test_digest_consistent_across_repo_locations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"

    content = "pkg==1.0\n"
    lock_a = _write_lock(repo_a, "locks/requirements.txt", content)
    lock_b = _write_lock(repo_b, "locks/requirements.txt", content)

    monkeypatch.setattr(hash_lockfiles, "_REPO_ROOT", repo_a, raising=False)
    digest_a = hash_lockfiles._digest([lock_a])

    monkeypatch.setattr(hash_lockfiles, "_REPO_ROOT", repo_b, raising=False)
    digest_b = hash_lockfiles._digest([lock_b])

    assert digest_a == digest_b
