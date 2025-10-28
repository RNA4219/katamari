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


def test_digest_is_independent_of_clone_location(tmp_path, monkeypatch) -> None:
    relative_lock = Path("locks/requirements.lock")

    def prepare_clone(name: str) -> Path:
        clone_root = tmp_path / name
        lock_path = clone_root / relative_lock
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("dep==1.0\n", encoding="utf-8")
        return clone_root

    def compute_digest(clone_root: Path) -> str:
        monkeypatch.setattr(hash_lockfiles, "_REPO_ROOT", clone_root, raising=False)
        lockfile = clone_root / relative_lock
        return hash_lockfiles._digest(
            hash_lockfiles._existing_paths([str(lockfile)])
        )

    clone_a = prepare_clone("clone_a")
    clone_b = prepare_clone("clone_b")

    digest_a = compute_digest(clone_a)
    digest_b = compute_digest(clone_b)

    assert digest_a == digest_b
