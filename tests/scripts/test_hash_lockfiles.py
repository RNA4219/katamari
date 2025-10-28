from __future__ import annotations

from scripts.cache.hash_lockfiles import _digest, _existing_paths


def test_digest_is_stable_with_duplicate_paths(tmp_path) -> None:
    lockfile = tmp_path / "requirements.txt"
    lockfile.write_text("example==1.0.0\n", encoding="utf-8")

    single_digest = _digest(_existing_paths([str(lockfile)]))
    duplicated_digest = _digest(
        _existing_paths([str(lockfile), str(lockfile)])
    )

    assert duplicated_digest == single_digest
