from __future__ import annotations

from typing import Dict, List
from unittest.mock import Mock

import pytest

from src.core_ext import evolve


class _DeterministicGenerator:
    def __init__(self, generations: Dict[int, List[str]]) -> None:
        self.generations = generations
        self.requested: List[int] = []

    def __call__(
        self,
        seed_prompt: str,
        generation_index: int,
        population: int,
        previous_best: str,
    ) -> List[str]:
        self.requested.append(generation_index)
        if generation_index == 0:
            return [seed_prompt]
        try:
            return self.generations[generation_index]
        except KeyError as exc:  # pragma: no cover - guard rail
            raise AssertionError(f"unexpected generation {generation_index}") from exc


@pytest.fixture
def metric_functions() -> Dict[str, evolve.PromptEvaluator]:
    metric_values: Dict[str, Dict[str, float]] = {
        "bertscore": {
            "seed": 0.2,
            "candidate-a": 0.4,
            "candidate-b": 0.6,
            "candidate-c": 0.9,
            "candidate-d": 0.3,
        },
        "rouge": {
            "seed": 0.1,
            "candidate-a": 0.2,
            "candidate-b": 0.5,
            "candidate-c": 0.8,
            "candidate-d": 0.4,
        },
        "rule": {
            "seed": 0.5,
            "candidate-a": 0.7,
            "candidate-b": 0.2,
            "candidate-c": 0.95,
            "candidate-d": 0.3,
        },
    }

    def _build(name: str) -> evolve.PromptEvaluator:
        values = metric_values[name]

        def _metric(candidate: str, objective: str) -> float:
            assert objective == "increase conversions"
            return values[candidate]

        return _metric

    return {name: _build(name) for name in metric_values}


def test_evolve_prompts_selects_best_prompt_and_records_history(
    metric_functions: Dict[str, evolve.PromptEvaluator],
) -> None:
    generator = _DeterministicGenerator(
        {1: ["candidate-a", "candidate-b"], 2: ["candidate-c", "candidate-d"]}
    )

    result = evolve.evolve_prompts(
        seed_prompt="seed",
        objective="increase conversions",
        pop=2,
        gen=2,
        metric_functions=metric_functions,
        candidate_generator=generator,
    )

    assert result["bestPrompt"] == "candidate-c"

    history = result["history"]
    assert [entry["gen"] for entry in history] == [0, 1, 2]

    generation_two = history[2]
    assert generation_two["candidates"] == ["candidate-c", "candidate-d"]
    assert generation_two["scores"][0] == pytest.approx(0.883333, rel=1e-6)

    candidate_metrics = generation_two["evaluations"][0]
    assert candidate_metrics["prompt"] == "candidate-c"
    assert candidate_metrics["metrics"] == {
        "bertscore": 0.9,
        "rouge": 0.8,
        "rule": 0.95,
    }
    assert candidate_metrics["totalScore"] == pytest.approx(0.883333, rel=1e-6)

    assert result["history"][1]["bestPrompt"] == "candidate-a"
    assert result["history"][1]["scores"] == [
        pytest.approx(0.433333, rel=1e-6),
        pytest.approx(0.433333, rel=1e-6),
    ]

    assert generator.requested == [0, 1, 2]


@pytest.fixture()
def mock_metrics() -> Dict[str, evolve.PromptEvaluator]:
    scorer_a = Mock(name="scorer_a")
    scorer_b = Mock(name="scorer_b")

    def _score(candidate: str, *_: str) -> float:
        if candidate == "seed":
            return 0.2
        if candidate == "better":
            return 0.6
        if candidate == "best":
            return 0.95
        return 0.1

    scorer_a.side_effect = _score
    scorer_b.side_effect = lambda candidate, *_: _score(candidate) - 0.05

    return {"a": scorer_a, "b": scorer_b}


def test_evolve_prompts_updates_history_and_best_prompt(mock_metrics: Dict[str, evolve.PromptEvaluator]) -> None:
    candidate_plan = {
        0: ["seed"],
        1: ["seed", "better"],
        2: ["better", "best"],
    }
    candidate_generator = Mock(
        side_effect=lambda seed, generation, population, prev_best: candidate_plan[generation]
    )

    result = evolve.evolve_prompts(
        seed_prompt="seed",
        objective="maximize goodness",
        pop=2,
        gen=2,
        metric_functions=mock_metrics,
        candidate_generator=candidate_generator,
    )

    assert result["bestPrompt"] == "best"
    assert [entry["bestPrompt"] for entry in result["history"]] == ["seed", "better", "best"]
    assert [entry["gen"] for entry in result["history"]] == [0, 1, 2]

    assert candidate_generator.call_args_list[0].args == ("seed", 0, 2, "seed")
    assert candidate_generator.call_args_list[1].args == ("seed", 1, 2, "seed")
    assert candidate_generator.call_args_list[2].args == ("seed", 2, 2, "better")

    for scorer in mock_metrics.values():
        recorded_calls = [args.args for args in scorer.call_args_list]
        assert ("seed", "maximize goodness") in recorded_calls
        assert ("better", "maximize goodness") in recorded_calls
        assert ("best", "maximize goodness") in recorded_calls

    history_entry = result["history"][2]
    assert history_entry["evaluations"][1]["prompt"] == "best"
    assert history_entry["evaluations"][1]["metrics"]["a"] > history_entry["evaluations"][0]["metrics"]["a"]
