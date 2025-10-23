from __future__ import annotations

from typing import Dict, List, Optional, Tuple

try:
    import tiktoken
    from tiktoken import registry as _registry
    from tiktoken.core import Encoding as _Encoding
except Exception:  # pragma: no cover - defensive import guard
    tiktoken = None  # type: ignore[assignment]
    _registry = None  # type: ignore[assignment]
    _Encoding = None  # type: ignore[assignment]

_MODEL_PREFIX_ENCODINGS: Tuple[Tuple[str, str], ...] = (
    ("gpt-5", "o200k_base"),
    ("gpt-4o", "o200k_base"),
    ("gpt-4", "cl100k_base"),
    ("gpt-3.5", "cl100k_base"),
)


def _register_ascii_encoding(name: str) -> Optional[_Encoding]:
    if _registry is None or _Encoding is None:
        return None
    encoding = _registry.ENCODINGS.get(name)
    if encoding is not None:
        return encoding
    mergeable_ranks = {bytes([i]): i for i in range(256)}
    encoding = _Encoding(
        name=name,
        pat_str=r"(?s:.)",
        mergeable_ranks=mergeable_ranks,
        special_tokens={"<|endoftext|>": len(mergeable_ranks)},
    )
    _registry.ENCODINGS[name] = encoding
    return encoding


def _group_conversation_turns(conversation: List[Dict]) -> List[List[Dict]]:
    turns: List[List[Dict]] = []
    current: List[Dict] = []
    for message in conversation:
        role = message.get("role")
        if role == "user":
            if current:
                turns.append(current)
            current = [message]
        else:
            if not current:
                current = [message]
            else:
                current.append(message)
    if current:
        turns.append(current)
    return turns


class _TokenCounter:
    def __init__(self, model: str) -> None:
        self._encoding_name = self._resolve_encoding_name(model)
        self._encoding = self._load_encoding(self._encoding_name)

    @staticmethod
    def _resolve_encoding_name(model: str) -> Optional[str]:
        if tiktoken is None:
            return None
        normalized = model.lower()
        for prefix, encoding in _MODEL_PREFIX_ENCODINGS:
            if normalized.startswith(prefix):
                return encoding
        try:
            return tiktoken.encoding_for_model(model).name
        except Exception:
            return None

    @staticmethod
    def _load_encoding(name: Optional[str]) -> Optional[_Encoding]:
        if name is None or tiktoken is None:
            return None
        try:
            return tiktoken.get_encoding(name)
        except Exception:
            return _register_ascii_encoding(name)

    def count(self, text: str) -> int:
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return max(1, len(text) // 4)

    def describe(self) -> Dict[str, str]:
        info: Dict[str, str] = {"mode": "tiktoken" if self._encoding is not None else "heuristic"}
        if self._encoding_name is not None:
            info["encoding"] = self._encoding_name
        return info


def trim_messages(
    messages: List[Dict],
    target_tokens: int,
    model: str,
    *,
    min_turns: int = 0,
) -> Tuple[List[Dict], Dict]:
    counter = _TokenCounter(model)
    system_messages = [m for m in messages if m.get("role") == "system"]
    conversation = [m for m in messages if m.get("role") != "system"]
    budget = max(256, target_tokens)
    required_turns = max(0, min_turns)

    if required_turns > 0:
        turns = _group_conversation_turns(conversation)
        kept_turns: List[List[Dict]] = []
        total = 0
        turns_kept = 0
        for turn in reversed(turns):
            turn_tokens = sum(counter.count(message.get("content", "")) for message in turn)
            if total + turn_tokens > budget and turns_kept >= required_turns:
                break
            kept_turns.append(turn)
            total += turn_tokens
            turns_kept += 1
        kept = [message for turn in reversed(kept_turns) for message in turn]
    else:
        kept = []
        total = 0
        for message in reversed(conversation):
            tokens = counter.count(message.get("content", ""))
            if total + tokens > budget:
                break
            kept.append(message)
            total += tokens
        kept.reverse()

    output_messages = (system_messages[:1] if system_messages else []) + kept

    original_tokens = sum(counter.count(m.get("content", "")) for m in messages)
    trimmed_tokens = sum(counter.count(m.get("content", "")) for m in output_messages)
    ratio = trimmed_tokens / max(1, original_tokens)
    metrics = {
        "input_tokens": original_tokens,
        "output_tokens": trimmed_tokens,
        "compress_ratio": round(ratio, 3),
        "token_counter": counter.describe(),
        "semantic_retention": None,
    }
    return output_messages, metrics
