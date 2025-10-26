import pytest

from src.core_ext.prethought import analyze_intent


@pytest.fixture
def sample_prompt() -> str:
    return (
        "目的: ユーザーオンボーディングを10日で完了させる\n"
        "制約: セキュリティ監査を通過しつつ既存APIだけで構築する\n"
        "視点: CSチームと新規顧客の双方が迷わない運用ガイドにする\n"
        "期待: 30分以内に読めるチェックリストとKPIテンプレート"
    )


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
