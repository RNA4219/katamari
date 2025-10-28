from __future__ import annotations

from pathlib import Path

from scripts.cache import hash_lockfiles


def test_digest_is_stable_across_repo_locations(tmp_path, monkeypatch) -> None:
    lock_relative = Path("locks/requirements.lock")

    repo_a = tmp_path / "workspace_a"
    repo_b = tmp_path / "workspace_b"

    for repo in (repo_a, repo_b):
        target = repo / lock_relative
        target.parent.mkdir(parents=True)
        target.write_text("example-lock-data\n", encoding="utf-8")

    monkeypatch.setattr(hash_lockfiles, "_REPO_ROOT", repo_a)
    digest_a = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(repo_a / lock_relative)])
    )

    monkeypatch.setattr(hash_lockfiles, "_REPO_ROOT", repo_b)
    digest_b = hash_lockfiles._digest(
        hash_lockfiles._existing_paths([str(repo_b / lock_relative)])
    )

    assert digest_a == digest_b
