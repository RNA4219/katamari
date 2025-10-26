import re
from textwrap import dedent

from src.core_ext.prethought import analyze_intent


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

    sections = dict(
        line.split(":", 1)
        for line in re.split(r"\n+", result)
        if ":" in line
    )

    assert all(keyword in sections.get("目的", "") for keyword in ["B2B", "解約率"])
    assert all(keyword in sections.get("制約", "") for keyword in ["2週間", "日本リージョン"])
    assert "カスタマーサクセス" in sections.get("視点", "")
    assert all(keyword in sections.get("期待", "") for keyword in ["日次レポート", "Slack"])
