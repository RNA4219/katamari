"""Prompt evolution orchestration utilities."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Mapping, MutableMapping, Sequence, TypedDict


PromptEvaluator = Callable[[str, str], float]
"""Callable that evaluates a candidate prompt against an objective and returns a score."""


class EvaluationDetail(TypedDict):
    """JSON 互換の評価詳細を保持するレコード。"""

    prompt: str
    metrics: Dict[str, float]
    totalScore: float


class EvolutionHistoryEntry(TypedDict):
    """Serialised record of a generation during prompt evolution.

    All values are JSON 互換 (lists, strings, floats) で構成され、外部保存時に追加処理を
    必要としない。
    """

    gen: int
    candidates: List[str]
    scores: List[float]
    bestPrompt: str
    evaluations: List[EvaluationDetail]


class EvolutionResult(TypedDict):
    bestPrompt: str
    history: List[EvolutionHistoryEntry]


CandidateGenerator = Callable[[str, int, int, str], Sequence[str]]


def _mean(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    return total / count if count else 0.0


def _resolve_default_metric_functions() -> Dict[str, PromptEvaluator]:
    metric_functions: MutableMapping[str, PromptEvaluator] = {}

    def _build_bertscore() -> PromptEvaluator:
        try:
            from bert_score import score as bert_score_score
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "bert_score is required for default prompt evolution metrics"
            ) from exc

        def _metric(candidate: str, objective: str) -> float:
            _, _, f1 = bert_score_score([candidate], [objective], lang="en")
            return float(f1.mean())

        return _metric

    def _build_rouge() -> PromptEvaluator:
        try:
            from rouge_score import rouge_scorer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "rouge_score is required for default prompt evolution metrics"
            ) from exc

        scorer = rouge_scorer.RougeScorer(["rougeLsum"], use_stemmer=True)

        def _metric(candidate: str, objective: str) -> float:
            result = scorer.score(objective, candidate)
            return float(result["rougeLsum"].fmeasure)

        return _metric

    def _build_rule() -> PromptEvaluator:
        def _metric(candidate: str, objective: str) -> float:
            objective_terms = {term.lower() for term in objective.split() if term}
            if not objective_terms:
                return 0.0
            overlap = sum(1 for term in objective_terms if term in candidate.lower())
            return overlap / len(objective_terms)

        return _metric

    metric_functions["bertscore"] = _build_bertscore()
    metric_functions["rouge"] = _build_rouge()
    metric_functions["rule"] = _build_rule()
    return dict(metric_functions)


def _default_candidate_generator(
    seed_prompt: str,
    generation_index: int,
    population: int,
    previous_best: str,
) -> Sequence[str]:
    if generation_index == 0:
        return [seed_prompt]
    base = previous_best if previous_best else seed_prompt
    return [f"{base} :: variant {i + 1}" for i in range(population)]


def evolve_prompts(
    seed_prompt: str,
    objective: str,
    pop: int = 6,
    gen: int = 5,
    evaluator: str = "bertscore",
    *,
    metric_functions: Mapping[str, PromptEvaluator] | None = None,
    candidate_generator: CandidateGenerator | None = None,
) -> EvolutionResult:
    """Evolve prompts and record the scoring history across generations.

    Parameters
    ----------
    seed_prompt:
        初期プロンプト。
    objective:
        比較対象となる目的文。評価器はこの文を参照にスコアを算出する。
    pop:
        各世代で生成する候補プロンプト数。
    gen:
        実行する世代数。履歴は初期世代(0)を含めて `gen + 1` 件になる。
    evaluator:
        互換性維持のための予約引数。`metric_functions` を指定する場合は無視される。
    metric_functions:
        メトリクス名→評価関数のマッピング。指定が無い場合は BERTScore/ROUGE/ルール
        評価を読み込み、依存が不足していれば RuntimeError を送出する。
    candidate_generator:
        候補を生成するコールバック。省略時は `seed_prompt` を基点とした簡易変異を
        生成する。
    """

    del evaluator  # unused compatibility parameter

    if candidate_generator is None:
        candidate_generator = _default_candidate_generator

    metrics = dict(metric_functions or _resolve_default_metric_functions())
    if not metrics:
        raise RuntimeError("no metric functions provided for prompt evolution")

    history: List[EvolutionHistoryEntry] = []
    global_best_prompt = seed_prompt
    global_best_score = float("-inf")
    previous_best_prompt = seed_prompt

    origin_seed = seed_prompt

    for generation in range(gen + 1):
        try:
            generated = candidate_generator(
                origin_seed,
                generation,
                pop,
                previous_best_prompt,
            )
        except TypeError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError("candidate generator has an invalid signature") from exc

        candidates = list(generated)[:pop]
        if not candidates:
            candidates = [global_best_prompt]

        evaluations: List[EvaluationDetail] = []
        scores: List[float] = []
        generation_best_prompt = candidates[0]
        generation_best_score = float("-inf")

        for candidate in candidates:
            metrics_result = {
                name: float(func(candidate, objective))
                for name, func in metrics.items()
            }
            total_score = float(_mean(metrics_result.values()))
            evaluations.append(
                {
                    "prompt": candidate,
                    "metrics": metrics_result,
                    "totalScore": total_score,
                }
            )
            scores.append(total_score)

            if total_score > generation_best_score:
                generation_best_score = total_score
                generation_best_prompt = candidate

            if total_score > global_best_score:
                global_best_score = total_score
                global_best_prompt = candidate

        history.append(
            {
                "gen": generation,
                "candidates": candidates,
                "scores": scores,
                "bestPrompt": generation_best_prompt,
                "evaluations": evaluations,
            }
        )

        previous_best_prompt = generation_best_prompt

    return {"bestPrompt": global_best_prompt, "history": history}
