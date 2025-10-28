"""Tests for scripts.cache.hash_lockfiles."""

from __future__ import annotations

from pathlib import Path

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


def test_digest_is_stable_across_worktrees(tmp_path: Path) -> None:
    clone_a = tmp_path / "clone_a"
    clone_b = tmp_path / "clone_b"

    for clone in (clone_a, clone_b):
        clone.mkdir()
        (clone / "requirements.lock").write_text("dep==1.0\n", encoding="utf-8")

    digest_a = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(clone_a / "requirements.lock")])
    )
    digest_b = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(clone_b / "requirements.lock")])
    )

    assert digest_a == digest_b
