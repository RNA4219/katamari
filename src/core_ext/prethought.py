import re
from typing import Iterable, Sequence


_SECTION_KEYWORDS = {
    "目的": ("目的", "狙い", "したい", "したく", "求め", "目標", "ゴール"),
    "制約": ("制約", "条件", "以内", "以下", "禁止", "must", "should", "必要"),
    "視点": ("視点", "ユーザー", "顧客", "担当", "開発者", "オーナー", "マネージャー"),
    "期待": ("期待", "成果", "結果", "出力", "生成", "欲しい", "求める"),
}


_SECTION_PREFIX_PATTERN = re.compile(r"^(目的|制約|視点|期待)\s*[:：]\s*(.+)$")


def _split_sentences(text: str) -> list[str]:
    sentences = [segment.strip() for segment in re.split(r"[。\.\n!?！？]+", text) if segment.strip()]
    return sentences or [text.strip()] if text.strip() else []


def _strip_section_prefix(label: str, sentence: str) -> str:
    return re.sub(rf"^\s*{label}\s*[:：]\s*", "", sentence).strip() or sentence.strip()


def _extract_explicit_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for line in text.splitlines():
        match = _SECTION_PREFIX_PATTERN.match(line.strip())
        if match:
            label, content = match.groups()
            if content:
                sections[label] = content.strip()
    return sections


def _find_matching_sentences(
    label: str, sentences: Sequence[str], keywords: Iterable[str]
) -> list[str]:
    lowered_keywords = [keyword.lower() for keyword in keywords]
    matches: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        normalized = sentence.strip()
        if not normalized:
            continue
        lower_sentence = normalized.lower()
        if any(keyword in lower_sentence for keyword in lowered_keywords):
            sanitized = _strip_section_prefix(label, normalized)
            if sanitized not in seen:
                matches.append(sanitized)
                seen.add(sanitized)
    return matches


def _extract_fallback_phrase(sentences: Sequence[str]) -> str:
    tokens: list[str] = []
    for sentence in sentences:
        chunks = re.split(r"[、,\s]+", sentence)
        for chunk in chunks:
            normalized = chunk.strip()
            if len(normalized) >= 2 and not normalized.isdigit():
                tokens.append(normalized)
        if tokens:
            break
    return " / ".join(tokens[:2])


def analyze_intent(text: str) -> str:
    sentences = _split_sentences(text)
    if not sentences:
        return "\n".join(
            [
                "目的: ユーザーの入力を達成する",
                "制約: 安全/簡潔/正確",
                "視点: ユースケースに即した実装志向",
                "期待: 具体・短文・即使える成果物",
            ]
        )

    explicit_sections = _extract_explicit_sections(text)

    sections: dict[str, str] = {}
    for label, keywords in _SECTION_KEYWORDS.items():
        if label in explicit_sections:
            sections[label] = explicit_sections[label]
            continue

        matches = _find_matching_sentences(label, sentences, keywords)
        if matches:
            sections[label] = " / ".join(matches[:2])
            continue
        fallback = _extract_fallback_phrase(sentences)
        sections[label] = fallback if fallback else sentences[0]

    return "\n".join(f"{label}: {sections[label]}" for label in ("目的", "制約", "視点", "期待"))
