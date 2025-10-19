from __future__ import annotations

from pathlib import Path


def test_readme_guides_repository_layout() -> None:
    project_root = Path(__file__).resolve().parents[1]
    readme = project_root / "README.md"

    content = readme.read_text(encoding="utf-8")

    assert "## Repository structure" in content, "README.md に Repository structure セクションを追加してください"

    for relative_path in (
        "workflow-cookbook/logs",
        "workflow-cookbook/reports",
        "workflow-cookbook/scripts",
    ):
        assert (
            relative_path in content
        ), f"README.md は {relative_path} のように正しい相対パスを案内する必要があります"

    assert (
        "Priority Score は必須" in content
    ), "README.md の PR チェックリストに Priority Score が必須である旨を明記してください"
    assert (
        "`Priority Score: <number> / <justification>`" in content
    ), "README.md の PR チェックリストで Priority Score の形式を `<number> / <justification>` と明記してください"
