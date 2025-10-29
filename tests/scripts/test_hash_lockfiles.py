"""Tests for scripts.cache.hash_lockfiles."""

from __future__ import annotations

import os

import pytest

from scripts.cache import hash_lockfiles


def test_digest_is_stable_with_duplicate_paths(tmp_path) -> None:
    lockfile = tmp_path / "requirements.lock"
    lockfile.write_text("dep==1.0\n", encoding="utf-8")

    single_digest = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(lockfile)])
    )
    duplicate_digest = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(lockfile), str(lockfile)])
    )

    assert duplicate_digest == single_digest


def test_digest_is_stable_with_equivalent_paths(tmp_path) -> None:
    lockfile = tmp_path / "requirements.lock"
    lockfile.write_text("dep==1.0\n", encoding="utf-8")

    alt_representation = tmp_path / "nested" / ".." / "requirements.lock"

    single_digest = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(lockfile)])
    )
    equivalent_digest = hash_lockfiles._digest(
        hash_lockfiles._existing_paths(
            [
                str(lockfile),
                str(alt_representation),
                str(lockfile),
            ]
        )
    )

    assert equivalent_digest == single_digest


def test_digest_is_stable_across_repository_roots(tmp_path, monkeypatch) -> None:
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"

    for repo in (repo_a, repo_b):
        repo.mkdir()
        lockfile = repo / "requirements.lock"
        lockfile.write_text("dep==1.0\n", encoding="utf-8")

    monkeypatch.setattr(hash_lockfiles, "_REPOSITORY_ROOT", repo_a)
    digest_a = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(repo_a / "requirements.lock")])
    )
    monkeypatch.setattr(hash_lockfiles, "_REPOSITORY_ROOT", repo_b)
    digest_b = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(repo_b / "requirements.lock")])
    )

    assert digest_a == digest_b


def test_digest_is_location_independent(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    worktree = repo_root / "work" / "tree"
    worktree.mkdir(parents=True)
    lockfile = repo_root / "requirements.lock"
    lockfile.write_text("dep==1.0\n", encoding="utf-8")

    monkeypatch.setattr(hash_lockfiles, "_REPOSITORY_ROOT", repo_root)

    monkeypatch.chdir(repo_root)
    from_root = hash_lockfiles._existing_paths(["requirements.lock"])
    assert [entry[0] for entry in from_root] == ["requirements.lock"]
    digest_from_root = hash_lockfiles._digest(from_root)

    monkeypatch.chdir(worktree)
    relative_path = os.path.relpath(lockfile, start=worktree)
    from_nested = hash_lockfiles._existing_paths([relative_path])
    assert from_root == from_nested
    digest_from_nested = hash_lockfiles._digest(from_nested)

    assert digest_from_root == digest_from_nested


def test_existing_paths_expands_home_directory(tmp_path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    lockfile = home_dir / "requirements.lock"
    lockfile.write_text("dep==1.0\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home_dir))

    existing = hash_lockfiles._existing_paths(["~/requirements.lock"])

    expected = lockfile.resolve()
    assert existing == [(expected.as_posix(), expected)]


def test_existing_paths_deduplicates_home_and_absolute(tmp_path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    lockfile = home_dir / "requirements.lock"
    lockfile.write_text("dep==1.0\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home_dir))

    absolute_path = lockfile.resolve()
    existing = hash_lockfiles._existing_paths(
        [str(absolute_path), "~/requirements.lock", str(absolute_path)]
    )

    assert existing == [(absolute_path.as_posix(), absolute_path)]


def test_missing_path_raises_error(tmp_path) -> None:
    missing = tmp_path / "requirements.lock"

    with pytest.raises(FileNotFoundError) as excinfo:
        hash_lockfiles._existing_paths([str(missing)])

    assert str(missing) in str(excinfo.value)
