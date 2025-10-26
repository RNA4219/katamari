import pytest
from textwrap import dedent

from src.core_ext.prethought import analyze_intent


@pytest.fixture
def sample_prompt() -> str:
    return (
        "目的: ユーザーオンボーディングを10日で完了させる\n"
        "制約: セキュリティ監査を通過しつつ既存APIだけで構築する\n"
        "視点: CSチームと新規顧客の双方が迷わない運用ガイドにする\n"
        "期待: 30分以内に読めるチェックリストとKPIテンプレート"
    )


def test_analyze_intent_reflects_user_keywords() -> None:
    text = dedent(
        """
        目的:
        - B2B SaaSの解約率を10%改善
        制約:
        - 2週間でPoC完了
        - PIIは日本リージョンに限定
        視点:
        - カスタマーサクセス部門の手離れを減らす
        期待:
        - 日次レポート雛形とSlack通知案
        """
    ).strip()

    result = analyze_intent(text)
    sections = dict(line.split(": ", 1) for line in result.splitlines())

    assert sections["目的"].startswith("B2B SaaSの解約率")
    assert "PoC完了" in sections["制約"]
    assert "日本リージョン" in sections["制約"]
    assert "カスタマーサクセス" in sections["視点"]
    assert sections["期待"].endswith("Slack通知案")


def test_analyze_intent_reflects_explicit_sections(sample_prompt: str) -> None:
    result = analyze_intent(sample_prompt)
    sections = dict(line.split(": ", 1) for line in result.splitlines())

    assert sections["目的"] == "ユーザーオンボーディングを10日で完了させる"
    assert (
        sections["制約"]
        == "セキュリティ監査を通過しつつ既存APIだけで構築する"
    )
    assert (
        sections["視点"] == "CSチームと新規顧客の双方が迷わない運用ガイドにする"
    )
    assert sections["期待"] == "30分以内に読めるチェックリストとKPIテンプレート"
