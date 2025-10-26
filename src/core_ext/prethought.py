import re
from typing import Iterable, Sequence


_SECTION_ORDER = ("目的", "制約", "視点", "期待")

_SECTION_KEYWORDS = {
    "目的": ("目的", "狙い", "したい", "したく", "求め", "目標", "ゴール"),
    "制約": ("制約", "条件", "以内", "以下", "禁止", "must", "should", "必要", "制限"),
    "視点": ("視点", "ユーザー", "顧客", "担当", "開発者", "オーナー", "マネージャー", "観点"),
    "期待": ("期待", "成果", "結果", "出力", "生成", "欲しい", "求める", "期待値"),
}

_SECTION_ANCHORS = {
    "目的": ("目的", "ゴール", "目標"),
    "制約": ("制約", "条件", "制限", "constraints"),
    "視点": ("視点", "観点"),
    "期待": ("期待", "成果", "出力", "期待値"),
}


# セクション見出し検出用の追加パターン
_SECTION_PREFIX_PATTERN = re.compile(r"^(目的|制約|視点|期待)\s*[:：]\s*(.+)$")

def _append_unique(target: list[str], value: str) -> None:
    if value and value not in target:
        target.append(value)


def _clean_content_line(line: str) -> str:
    cleaned = re.sub(r"^[\s>\-・*•]+", "", line)
    cleaned = re.sub(r"^\d+(?:[.)])\s*", "", cleaned)
    return cleaned.strip()


def _detect_section_heading(line: str) -> tuple[str, str | None] | None:
    stripped = re.sub(r"^[#\s>\-・*•]+", "", line).strip()

    # まず明示的なプレフィックスパターンをチェック
    match_prefix = _SECTION_PREFIX_PATTERN.match(stripped)
    if match_prefix:
        label, content = match_prefix.groups()
        return label, content.strip() if content else None

    # 既存のアンカー判定
    for label, anchors in _SECTION_ANCHORS.items():
        for anchor in anchors:
            pattern = re.compile(
                rf"^(?:{re.escape(anchor)})\s*(?:[:：=\-]+\s*(.*))?$",
                re.IGNORECASE,
            )
            match = pattern.match(stripped)
            if match:
                trailing = match.group(1)
                content = trailing.strip() if trailing else None
                return label, content if content else None
    return None


def _parse_structured_sections(text: str) -> dict[str, list[str]]:
    sections = {label: [] for label in _SECTION_ORDER}
    current_label: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        heading = _detect_section_heading(raw_line)
        if heading:
            current_label, inline_content = heading
            if inline_content:
                _append_unique(sections[current_label], _clean_content_line(inline_content))
            continue
        if current_label:
            cleaned = _clean_content_line(raw_line)
            if cleaned:
                _append_unique(sections[current_label], cleaned)
    return sections



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

    # まず明示的に記載されたセクションを抽出
    explicit_sections = _extract_explicit_sections(text)

    # 構造化された見出し・内容を解析
    structured_sections = _parse_structured_sections(text)

    sections: dict[str, str] = {}
    for label in _SECTION_ORDER:
        # 明示的セクションが優先
        if label in explicit_sections:
            sections[label] = explicit_sections[label]
            continue

        # 構造的に抽出された内容があれば利用
        structured_values = structured_sections.get(label, [])
        if structured_values:
            sections[label] = " / ".join(structured_values[:2])
            continue

        # 最後にキーワードベースで補完
        keywords = _SECTION_KEYWORDS[label]
        matches = _find_matching_sentences(sentences, keywords)
        if matches:
            sections[label] = " / ".join(matches[:2])

        if matches:
            sections[label] = " / ".join(matches[:2])
            continue
        fallback = _extract_fallback_phrase(sentences)
        sections[label] = fallback if fallback else sentences[0]

    return "\n".join(f"{label}: {sections[label]}" for label in _SECTION_ORDER)
