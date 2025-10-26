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
        目的: B2B SaaSの解約率を10%改善したい
        - 狙い: ユーザーオンボーディングを10日で完了させる
        制約:
          1) 必要: 既存APIだけで構築する
          - 条件: セキュリティ監査を通過する
        視点:
          > 顧客とCSチームの観点を両立させる
        期待:
          * 成果: Slack通知案と日次レポート雛形をまとめる
          ・出力: KPIチェックリストのテンプレート
        """
    ).strip()

    report = analyze_intent(text)
    sections = _sections_from_output(report)

    assert "狙い" in sections["目的"]
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
