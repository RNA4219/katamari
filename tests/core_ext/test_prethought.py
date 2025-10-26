import re

from src.core_ext.prethought import analyze_intent


def test_analyze_intent_reflects_user_keywords() -> None:
    text = (
        "ユーザーはモバイルアプリでタスク管理を高速化したい。"
        "制約はオフライン対応と応答時間30ms以下。"
        "プロダクトマネージャー視点で既存UXを壊さない。"
        "期待する出力はダークテーマUI案とQAチェックリスト。"
    )

    result = analyze_intent(text)

    sections = dict(
        line.split(":", 1)
        for line in re.split(r"\n+", result)
        if ":" in line
    )

    assert any(keyword in sections.get("目的", "") for keyword in ["モバイルアプリ", "高速化"])
    assert all(keyword in sections.get("制約", "") for keyword in ["オフライン", "30ms"])
    assert any(
        keyword in sections.get("視点", "")
        for keyword in ["プロダクトマネージャー", "UX"]
    )
    assert all(keyword in sections.get("期待", "") for keyword in ["ダークテーマ", "QA"])
