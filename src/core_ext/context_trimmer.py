from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, TypedDict, cast

tiktoken: Any
_registry: Any
_Encoding: Any
_tiktoken_mod: Any
_registry_mod: Any
_EncodingCls: Any

try:
    _tiktoken_mod = import_module("tiktoken")
except Exception:  # pragma: no cover - defensive import guard
    _tiktoken_mod = None

try:
    _registry_mod = import_module("tiktoken.registry")
except Exception:  # pragma: no cover - defensive import guard
    _registry_mod = None

try:
    _EncodingCls = getattr(import_module("tiktoken.core"), "Encoding")
except Exception:  # pragma: no cover - defensive import guard
    _EncodingCls = None

tiktoken = cast(Any, _tiktoken_mod)
_registry = cast(Any, _registry_mod)
_Encoding = cast(Any, _EncodingCls)


class ChatMessage(TypedDict, total=False):
    role: str
    content: str


TrimMetricValue = float | int | None | Dict[str, str]
TrimMetrics = Dict[str, TrimMetricValue]

_MessageSeq = Sequence[ChatMessage]
_MessageList = List[ChatMessage]

_MODEL_PREFIX_ENCODINGS: Tuple[Tuple[str, str], ...] = (
    ("gpt-5", "o200k_base"),
    ("gpt-4o", "o200k_base"),
    ("gpt-4", "cl100k_base"),
    ("gpt-3.5", "cl100k_base"),
)


def _register_ascii_encoding(name: str) -> Optional[Any]:
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


def _group_conversation_turns(conversation: _MessageSeq) -> List[_MessageList]:
    turns: List[_MessageList] = []
    current: _MessageList = []
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
            return cast(str, tiktoken.encoding_for_model(model).name)
        except Exception:
            return None

    @staticmethod
    def _load_encoding(name: Optional[str]) -> Optional[Any]:
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
        info: Dict[str, str] = {
            "mode": "tiktoken" if self._encoding is not None else "heuristic"
        }
        if self._encoding_name is not None:
            info["encoding"] = self._encoding_name
        return info


def trim_messages(
    messages: Sequence[ChatMessage],
    target_tokens: int,
    model: str,
    *,
    min_turns: int = 0,
    priority_roles: Iterable[str] | None = None,
) -> Tuple[List[ChatMessage], TrimMetrics]:
    counter = _TokenCounter(model)
    priority_role_set: Set[str] = set(priority_roles or ())
    system_messages = [m for m in messages if m.get("role") == "system"]
    kept_system_messages: List[ChatMessage] = []
    for message in system_messages:
        if not kept_system_messages or message.get("role") in priority_role_set:
            kept_system_messages.append(message)
    conversation = [m for m in messages if m.get("role") != "system"]
    base_budget = max(256, target_tokens)
    system_tokens = sum(
        counter.count(str(message.get("content", ""))) for message in kept_system_messages
    )
    budget = max(0, base_budget - system_tokens)
    required_turns = max(0, min_turns)

    turns = _group_conversation_turns(conversation)
    latest_turn = turns[-1] if turns else []

    if required_turns > 0:
        kept_turns: List[_MessageList] = []
        total = 0
        turns_kept = 0
        for turn in reversed(turns):
            turn_tokens = sum(
                counter.count(str(message.get("content", ""))) for message in turn
            )
            is_latest_turn = turn is latest_turn
            has_priority = any(message.get("role") in priority_role_set for message in turn)
            if (
                not is_latest_turn
                and total + turn_tokens > budget
                and turns_kept >= required_turns
                and not has_priority
            ):
                continue
            kept_turns.append(turn)
            total += turn_tokens
            turns_kept += 1
        if latest_turn and all(turn is not latest_turn for turn in kept_turns):
            kept_turns.append(latest_turn)
        kept = [message for turn in reversed(kept_turns) for message in turn]
    else:
        forced_ids = {id(message) for message in latest_turn}
        if priority_role_set:
            forced_ids.update(
                id(message)
                for message in conversation
                if message.get("role") in priority_role_set
            )
        kept = []
        total = 0
        for message in reversed(conversation):
            tokens = counter.count(str(message.get("content", "")))
            should_force = id(message) in forced_ids
            if not should_force and total + tokens > budget:
                break
            kept.append(message)
            total += tokens
            if should_force:
                forced_ids.discard(id(message))
        kept.reverse()

    output_messages = kept_system_messages + kept

    original_tokens = sum(counter.count(str(m.get("content", ""))) for m in messages)
    trimmed_tokens = sum(
        counter.count(str(m.get("content", ""))) for m in output_messages
    )
    ratio = trimmed_tokens / max(1, original_tokens)
    metrics: TrimMetrics = {
        "input_tokens": original_tokens,
        "output_tokens": trimmed_tokens,
        "compress_ratio": round(ratio, 3),
        "token_counter": counter.describe(),
        "semantic_retention": None,
    }
    return output_messages, metrics
