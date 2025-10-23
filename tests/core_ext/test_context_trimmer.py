import math
from typing import Dict, List

import pytest

from src.core_ext.context_trimmer import trim_messages


tiktoken = pytest.importorskip("tiktoken")


@pytest.mark.parametrize("model", ["gpt-5-main", "gpt-4o", "gpt-4"])
def test_trim_messages_token_accuracy(model: str) -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "You are a concise assistant."},
        {"role": "user", "content": "Summarize the Katamari history and mechanics."},
        {"role": "assistant", "content": "Katamari Damacy is a puzzle-action game by Namco."},
        {"role": "user", "content": "Provide bullet points and notable releases."},
    ]
    trimmed, metrics = trim_messages(messages, target_tokens=4096, model=model)

    counter_info = metrics["token_counter"]
    assert counter_info["mode"] == "tiktoken"
    encoding = tiktoken.get_encoding(counter_info["encoding"])

    expected_total = sum(len(encoding.encode(message["content"])) for message in messages)
    tolerance = max(1, math.ceil(expected_total * 0.05))

    assert abs(metrics["input_tokens"] - expected_total) <= tolerance
    assert abs(metrics["output_tokens"] - expected_total) <= tolerance
    assert trimmed == messages


def test_trim_messages_preserves_compress_ratio() -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "x" * 200},
        {"role": "assistant", "content": "y" * 200},
        {"role": "user", "content": "z" * 200},
    ]
    _, metrics = trim_messages(messages, target_tokens=16, model="legacy-model")

    assert metrics["token_counter"]["mode"] == "heuristic"
    ratio = metrics["output_tokens"] / max(1, metrics["input_tokens"])
    assert metrics["compress_ratio"] == round(ratio, 3)


def test_trim_messages_respects_min_turns() -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "first" * 400},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]

    trimmed, _ = trim_messages(messages, target_tokens=128, model="legacy-model", min_turns=2)

    assert trimmed == [
        {"role": "system", "content": "System"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]


def test_trim_messages_defaults_preserve_behavior() -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "a" * 100},
        {"role": "assistant", "content": "b" * 100},
    ]

    trimmed, _ = trim_messages(messages, target_tokens=16, model="legacy-model")

    assert trimmed == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "a" * 100},
        {"role": "assistant", "content": "b" * 100},
    ]
