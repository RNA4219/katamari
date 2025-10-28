"""Tests for scripts.cache.hash_lockfiles."""

from __future__ import annotations

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
