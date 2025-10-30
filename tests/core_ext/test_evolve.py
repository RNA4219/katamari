from __future__ import annotations

from typing import Dict, List

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
