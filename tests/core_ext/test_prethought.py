import pytest
from textwrap import dedent

from src.core_ext.prethought import IntentSection, analyze_intent


@pytest.fixture
def sample_prompt() -> str:
    return (
        "目的: ユーザーオンボーディングを10日で完了させる\n"
        "- B2B SaaSの解約率を10%改善\n"
        "制約: セキュリティ監査を通過しつつ既存APIだけで構築する\n"
        "- 2週間でPoC完了\n"
        "- PIIは日本リージョンに限定\n"
        "視点: CSチームと新規顧客の双方が迷わない運用ガイドにする\n"
        "- カスタマーサクセス部門の手離れを減らす\n"
        "期待: 30分以内に読めるチェックリストとKPIテンプレート\n"
        "- 日次レポート雛形とSlack通知案"
    )


def test_analyze_intent_reflects_user_keywords() -> None:
    text = dedent(
        """
        ユーザーオンボーディングを10日で完了させたい。この狙いを達成するためにB2B SaaSの解約率を10%改善したい。
        既存APIのみを使う必要があり、セキュリティ監査を通過する条件を厳守しなければならない。
        顧客とCSチームが迷わない運用ガイドを意識した視点で対応したい。
        期待する成果は日次レポートの雛形とSlack通知案を受け取ることだ。
        """
    ).strip()

    result = analyze_intent(text)
    sections = _sections_from_output(result)

    assert "解約率" in sections["目的"]
    assert "既存API" in sections["制約"]
    assert "顧客" in sections["視点"]
    assert "Slack通知案" in sections["期待"]


def test_analyze_intent_reflects_explicit_sections(sample_prompt: str) -> None:
    result = analyze_intent(sample_prompt)
    sections = _sections_from_output(result)

    assert sections["目的"] == "ユーザーオンボーディングを10日で完了させる"
    assert (
        sections["制約"]
        == "セキュリティ監査を通過しつつ既存APIだけで構築する"
    )
    assert (
        sections["視点"] == "CSチームと新規顧客の双方が迷わない運用ガイドにする"
    )
    assert sections["期待"] == "30分以内に読めるチェックリストとKPIテンプレート"


def _sections_from_output(report: str) -> dict[str, IntentSection]:
    sections: dict[str, IntentSection] = {}
    for line in report.splitlines():
        label, section = line.split(": ", 1)
        sections[label] = section
    return sections
