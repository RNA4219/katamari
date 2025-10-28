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


def test_existing_paths_expands_home_directory(tmp_path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    lockfile = home_dir / "requirements.lock"
    lockfile.write_text("dep==1.0\n", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home_dir))

    existing = hash_lockfiles._existing_paths(["~/requirements.lock"])

    assert existing == [lockfile.resolve()]


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

    assert existing == [absolute_path]
