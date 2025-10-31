import math
from typing import Dict, List

import pytest

from src.core_ext.context_trimmer import _TokenCounter, trim_messages


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
        {"role": "user", "content": "first" * 400},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "second"},
    ]


def test_trim_messages_min_turns_zero_keeps_latest_user_over_budget() -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "small talk"},
        {"role": "assistant", "content": "ack"},
        {"role": "user", "content": "final" * 2000},
    ]

    trimmed, _ = trim_messages(messages, target_tokens=16, model="legacy-model", min_turns=0)

    assert trimmed[-1] == {"role": "user", "content": "final" * 2000}
    assert trimmed[0]["role"] == "system"
    assert {"role": "user", "content": "small talk"} not in trimmed


def test_trim_messages_min_turns_one_keeps_latest_user_over_budget() -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "opening"},
        {"role": "assistant", "content": "short reply"},
        {"role": "user", "content": "final" * 4096},
    ]

    trimmed, _ = trim_messages(messages, target_tokens=32, model="legacy-model", min_turns=1)

    assert trimmed[-1] == {"role": "user", "content": "final" * 4096}
    assert {"role": "user", "content": "opening"} not in trimmed
    assert trimmed[0]["role"] == "system"


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

def test_trim_messages_min_turns_keeps_pairs_even_over_budget() -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "intro" * 400},
        {"role": "assistant", "content": "short"},
        {"role": "user", "content": "follow up"},
        {"role": "assistant", "content": "dense" * 400},
        {"role": "user", "content": "final question"},
        {"role": "assistant", "content": "final reply"},
    ]

    trimmed, _ = trim_messages(
        messages,
        target_tokens=64,
        model="legacy-model",
        min_turns=2,
    )

    assert trimmed == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "follow up"},
        {"role": "assistant", "content": "dense" * 400},
        {"role": "user", "content": "final question"},
        {"role": "assistant", "content": "final reply"},
    ]


def test_trim_messages_counts_system_tokens_in_budget() -> None:
    counter = _TokenCounter("gpt-4o")
    system_content = "sys " * 400
    system_tokens = counter.count(system_content)
    target_tokens = system_tokens + 48

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": "u" * 800},
        {"role": "assistant", "content": "a" * 200},
        {"role": "user", "content": "short question"},
    ]

    _, metrics = trim_messages(messages, target_tokens=target_tokens, model="gpt-4o")

    assert metrics["output_tokens"] <= target_tokens


def test_trim_messages_counts_system_tokens_in_budget_with_min_turns() -> None:
    counter = _TokenCounter("gpt-4o")
    system_content = "sys " * 400
    system_tokens = counter.count(system_content)
    target_tokens = system_tokens + 64

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": "first" * 800},
        {"role": "assistant", "content": "reply" * 200},
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": "short reply"},
        {"role": "user", "content": "final question"},
        {"role": "assistant", "content": "concise answer"},
    ]

    trimmed, metrics = trim_messages(
        messages,
        target_tokens=target_tokens,
        model="gpt-4o",
        min_turns=2,
    )

    assert metrics["output_tokens"] <= target_tokens
    assert trimmed[0]["role"] == "system"
    assert trimmed[-4:] == [
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": "short reply"},
        {"role": "user", "content": "final question"},
        {"role": "assistant", "content": "concise answer"},
    ]


def test_trim_messages_priority_roles_are_preserved_over_budget() -> None:
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "intro" * 200},
        {"role": "assistant", "content": "ack"},
        {"role": "developer", "content": "details" * 600},
        {"role": "user", "content": "final question"},
    ]

    trimmed, _ = trim_messages(
        messages,
        target_tokens=128,
        model="legacy-model",
        priority_roles=("developer",),
    )

    assert {"role": "developer", "content": "details" * 600} in trimmed
    assert trimmed[-1] == {"role": "user", "content": "final question"}
    assert {"role": "user", "content": "intro" * 200} not in trimmed


def test_trim_messages_priority_roles_survive_midstream_over_budget() -> None:
    developer_message = {"role": "developer", "content": "details" * 400}
    assistant_message = {"role": "assistant", "content": "overflow" * 4000}
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": "System"},
        developer_message,
        assistant_message,
        {"role": "user", "content": "latest"},
    ]

    trimmed, _ = trim_messages(
        messages,
        target_tokens=128,
        model="legacy-model",
        priority_roles=("developer",),
    )

    assert developer_message in trimmed
    assert assistant_message not in trimmed
    assert trimmed[-1] == {"role": "user", "content": "latest"}
