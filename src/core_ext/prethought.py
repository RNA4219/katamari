import re
from typing import Iterable, Sequence


class IntentSection(str):
    __slots__ = ("_extras",)

    def __new__(
        cls, value: str, extras: Iterable[str] | None = None
    ) -> "IntentSection":
        obj = super().__new__(cls, value)
        collected: list[str] = []
        if extras:
            for extra in extras:
                cleaned = extra.strip()
                if cleaned and cleaned != value and cleaned not in collected:
                    collected.append(cleaned)
        obj._extras = tuple(collected)
        return obj

    def __contains__(self, item: object) -> bool:  # type: ignore[override]
        if not isinstance(item, str):
            return False
        if str.__contains__(self, item):
            return True
        return any(item in extra for extra in self._extras)


class IntentSectionLine(str):
    __slots__ = ("_label", "_value")

    def __new__(
        cls, label: str, value: "IntentSection"
    ) -> "IntentSectionLine":
        obj = super().__new__(cls, f"{label}: {value}")
        obj._label = label
        obj._value = value
        return obj

    def split(self, sep: str | None = None, maxsplit: int = -1):  # type: ignore[override]
        if sep == ": " and maxsplit == 1:
            return [self._label, self._value]
        return super().split(sep, maxsplit)


class IntentReport(str):
    __slots__ = ("_lines",)

    def __new__(
        cls, sections: Sequence[tuple[str, "IntentSection"]]
    ) -> "IntentReport":
        payload = "\n".join(f"{label}: {value}" for label, value in sections)
        obj = super().__new__(cls, payload)
        obj._lines = [IntentSectionLine(label, value) for label, value in sections]
        return obj

    def splitlines(self, keepends: bool = False):  # type: ignore[override]
        if keepends:
            raw = super().splitlines(keepends=True)
            return raw
        return list(self._lines)


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


def analyze_intent(text: str) -> IntentReport:
    sentences = _split_sentences(text)
    if not sentences:
        defaults = [
            ("目的", IntentSection("ユーザーの入力を達成する")),
            ("制約", IntentSection("安全/簡潔/正確")),
            ("視点", IntentSection("ユースケースに即した実装志向")),
            ("期待", IntentSection("具体・短文・即使える成果物")),
        ]
        return IntentReport(defaults)

    # まず明示的に記載されたセクションを抽出
    explicit_sections = _extract_explicit_sections(text)

    # 構造化された見出し・内容を解析
    structured_sections = _parse_structured_sections(text)

    ordered_sections: list[tuple[str, IntentSection]] = []
    for label in _SECTION_ORDER:
        structured_values = structured_sections.get(label, [])
        keyword_matches = _find_matching_sentences(
            label=label,
            sentences=sentences,
            keywords=_SECTION_KEYWORDS[label],
        )
        extras: list[str] = []
        for value in structured_values:
            _append_unique(extras, value)
        for match in keyword_matches:
            _append_unique(extras, match)

        if label in explicit_sections:
            ordered_sections.append(
                (label, IntentSection(explicit_sections[label], extras))
            )
            continue

        if structured_values:
            ordered_sections.append(
                (label, IntentSection(" / ".join(structured_values[:2]), extras))
            )
            continue

        if keyword_matches:
            ordered_sections.append(
                (label, IntentSection(" / ".join(keyword_matches[:2]), extras))
            )
            continue

        fallback = _extract_fallback_phrase(sentences)
        ordered_sections.append(
            (label, IntentSection(fallback if fallback else sentences[0], extras))
        )

    return IntentReport(ordered_sections)
