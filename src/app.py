# Katamari (Chainlit Fork) - app.py (skeleton)
# Run (dev):
#   pip install -r requirements.txt
#   export OPENAI_API_KEY=sk-...
#   chainlit run src/app.py --host 0.0.0.0 --port 8787

from __future__ import annotations

import asyncio
import math
import os
from threading import Lock
from time import perf_counter
from typing import Any, Dict, List, Mapping, Sequence, cast, Literal

import chainlit as cl
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from chainlit.input_widget import Select, Slider, TextInput, Switch
from chainlit.server import app as chainlit_app, router as chainlit_router

from core_ext.logging import InferenceLogRecord, StepLatency, StructuredLogger
from core_ext.persona_compiler import compile_persona_yaml
from core_ext.context_trimmer import ChatMessage as TrimMessage, trim_messages
from core_ext.retention import compute_semantic_retention
from core_ext.prethought import analyze_intent
from core_ext.multistep import get_chain_steps, system_hint_for_step
from providers.google_gemini_client import GoogleGeminiProvider
from providers.openai_client import OpenAIProvider

DEFAULT_MODEL = "gpt-5-main"
DEFAULT_CHAIN = "single"
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant named Katamari."

_REASONING_DEFAULT: Dict[str, Any] = {"effort": "medium", "parallel": True}

ChatMessage = TrimMessage
ChatHistory = List[ChatMessage]
MetricsPayload = Dict[str, Any]

_USER_SESSION = cast(Any, cl.user_session)


def _session_get(key: str, default: Any | None = None) -> Any:
    return _USER_SESSION.get(key, default)


def _session_set(key: str, value: Any) -> None:
    _USER_SESSION.set(key, value)


async def _send_message(**kwargs: Any) -> None:
    message = cl.Message(**kwargs)
    await cast(Any, message).send()


def _chat_message(role: str, content: Any) -> ChatMessage:
    return {"role": role, "content": content}


def _prepare_provider_options(model_id: str, base: Mapping[str, Any]) -> Dict[str, Any]:
    opts = dict(base)
    if "thinking" in model_id.lower() and "reasoning" not in opts:
        opts["reasoning"] = dict(_REASONING_DEFAULT)
    return opts

_DISABLED_RETENTION_VALUES = {"", "none", "off", "0", "false"}


class MetricsRegistry:
    """Collect runtime metrics for operational endpoints."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._compress_ratio: float = 1.0
        self._semantic_retention: float | None = math.nan

    def observe_trim(
        self, *, compress_ratio: float, semantic_retention: float | None = None
    ) -> None:
        """Record the latest trimming metrics."""

        retention: float | None = semantic_retention
        if retention is not None:
            retention = float(retention)
        with self._lock:
            self._compress_ratio = float(compress_ratio)
            self._semantic_retention = retention

    def snapshot(self) -> Dict[str, float | None]:
        with self._lock:
            return {
                "compress_ratio": self._compress_ratio,
                "semantic_retention": self._semantic_retention,
            }

    def export_prometheus(self) -> str:
        metrics = self.snapshot()
        retention = metrics["semantic_retention"]
        retention_repr = "nan" if retention is None else f"{retention}"

        lines = [
            "# HELP compress_ratio Ratio of tokens kept after trimming.",
            "# TYPE compress_ratio gauge",
            f"compress_ratio {metrics['compress_ratio']}",
            "# HELP semantic_retention Semantic retention score for trimmed context.",
            "# TYPE semantic_retention gauge",
            f"semantic_retention {retention_repr}",
        ]
        return "\n".join(lines) + "\n"


METRICS_REGISTRY = MetricsRegistry()
REQUEST_LOGGER = StructuredLogger()


def _to_int(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _resolve_retryable(exc: BaseException) -> bool | None:
    flag = getattr(exc, "retryable", None)
    if isinstance(flag, bool):
        return flag
    return None


async def _ensure_semantic_retention(
    before: Sequence[ChatMessage],
    after: Sequence[ChatMessage],
    metrics: MetricsPayload,
) -> float | None:
    existing = metrics.get("semantic_retention")
    if existing is not None:
        value = _to_float(existing)
        metrics["semantic_retention"] = value
        return value

    provider = os.getenv("SEMANTIC_RETENTION_PROVIDER", "").strip().lower()
    if provider in _DISABLED_RETENTION_VALUES:
        metrics["semantic_retention"] = None
        return None

    result = await asyncio.to_thread(
        compute_semantic_retention,
        before,
        after,
    )
    metrics["semantic_retention"] = result
    return result

ops_router = APIRouter()


@ops_router.get("/healthz")
async def healthz() -> Dict[str, str]:
    """Liveness probe."""

    return {"status": "ok"}


@ops_router.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Expose runtime metrics in Prometheus text format."""

    payload = METRICS_REGISTRY.export_prometheus()
    return PlainTextResponse(payload, media_type="text/plain; version=0.0.4")

chainlit_app.include_router(ops_router, prefix=chainlit_router.prefix)
for _path in ("/metrics", "/healthz"):
    full_path = f"{chainlit_router.prefix}{_path}"
    for route in list(chainlit_app.router.routes):
        if getattr(route, "path", "") == full_path:
            chainlit_app.router.routes.remove(route)
            chainlit_app.router.routes.insert(0, route)
            break

def get_provider(model_id: str) -> OpenAIProvider | GoogleGeminiProvider:
    """Instantiate a provider implementation for the requested model."""

    if model_id.startswith("gemini-"):
        return GoogleGeminiProvider()
    return OpenAIProvider()

@cl.on_chat_start
async def on_start() -> None:
    _session_set("model", os.getenv("DEFAULT_MODEL", DEFAULT_MODEL))
    _session_set("chain", os.getenv("DEFAULT_CHAIN", DEFAULT_CHAIN))
    _session_set("trim_tokens", 4096)
    _session_set("min_turns", 0)
    _session_set("system", "You are a helpful assistant named Katamari.")

    chat_settings = cl.ChatSettings(
        inputs=[
            Select(id="model", label="Model",
                   values=["gpt-5-main","gpt-5-main-mini","gpt-5-thinking",
                           "gpt-5-thinking-mini","gpt-5-thinking-nano","gpt-5-thinking-pro",
                           "gemini-2.5-pro","gemini-2.5-flash"],
                   initial_index=0),
            Select(id="chain", label="Multi-step Chain", values=["single","reflect"], initial_index=0),
            Slider(id="trim_tokens", label="Trim target tokens", initial=4096, min=1024, max=8192, step=256),
            Slider(id="min_turns", label="Minimum turns to keep", initial=0, min=0, max=10, step=1),
            TextInput(id="persona_yaml", label="Persona YAML", initial="", description="name/style/forbid/notes"),
            Switch(id="show_debug", label="Show debug metrics", initial=False)
        ]
    )
    settings_payload = await cast(Any, chat_settings).send()

    await apply_settings(cast(Mapping[str, Any], settings_payload))

@cl.on_settings_update
async def on_settings_update(settings: Mapping[str, Any]) -> None:
    await apply_settings(settings)


async def apply_settings(settings: Mapping[str, Any]) -> None:
    def _sync_history_system(system_prompt: str) -> None:
        history = _session_get("history")
        system_entry = _chat_message("system", system_prompt)
        if not isinstance(history, list) or not history:
            _session_set("history", [system_entry])
            return

        first_entry = history[0]
        if isinstance(first_entry, dict) and first_entry.get("role") == "system":
            new_first = dict(first_entry)
            new_first["content"] = system_prompt
            new_history = [new_first] + list(history[1:])
        else:
            new_history = [system_entry] + list(history)

        _session_set("history", new_history)

    for key in ("model", "chain", "trim_tokens", "min_turns", "show_debug"):
        if key in settings:
            _session_set(key, settings.get(key))

    if "persona_yaml" in settings:
        yaml_raw = settings.get("persona_yaml", "")
        yaml_str = yaml_raw if isinstance(yaml_raw, str) else ""
        if yaml_str.strip() == "":
            previous = _session_get("system") or DEFAULT_SYSTEM_PROMPT
            _session_set("system", DEFAULT_SYSTEM_PROMPT)
            _sync_history_system(DEFAULT_SYSTEM_PROMPT)
            if previous != DEFAULT_SYSTEM_PROMPT:
                await _send_message(
                    content="[persona issues]\nPersona prompt reset to default."
                )
            return

        if yaml_str:
            system, issues = compile_persona_yaml(yaml_str)
            _session_set("system", system)
            _sync_history_system(system)
            if issues:
                await _send_message(content="\n".join(["[persona issues]"] + issues))

@cl.on_message
async def on_message(message: cl.Message) -> None:
    model = str(_session_get("model") or DEFAULT_MODEL)
    chain_id = str(_session_get("chain") or DEFAULT_CHAIN)
    target_tokens = _to_int(_session_get("trim_tokens"))
    if target_tokens <= 0:
        target_tokens = 4096
    min_turns = _to_int(_session_get("min_turns"))
    show_debug = bool(_session_get("show_debug"))

    # 1) Prethought (optional display as a step)
    intent = analyze_intent(message.content)
    if show_debug and intent:
        await _send_message(content=f"[prethought]\n{intent}")

    # 2) Build/trim history
    hist_data = _session_get("history") or []
    hist: ChatHistory = []
    if isinstance(hist_data, list):
        hist = [
            cast(ChatMessage, dict(cast(Mapping[str, Any], entry)))
            for entry in hist_data
            if isinstance(entry, dict)
        ]
    system = str(_session_get("system") or DEFAULT_SYSTEM_PROMPT)
    if not hist or hist[0].get("role") != "system":
        hist.insert(0, _chat_message("system", system))
    hist.append(_chat_message("user", message.content))

    trimmed_raw, metrics_raw = trim_messages(
        hist,
        target_tokens,
        model,
        min_turns=min_turns,
    )
    trimmed = cast(ChatHistory, list(trimmed_raw))
    metrics: MetricsPayload = dict(metrics_raw)
    semantic_retention_raw = await _ensure_semantic_retention(hist, trimmed, metrics)
    token_in = _to_int(metrics.get("input_tokens"))
    token_out = _to_int(metrics.get("output_tokens"))
    compress_ratio = _to_float(metrics.get("compress_ratio"))
    semantic_retention = (
        _to_float(semantic_retention_raw)
        if semantic_retention_raw is not None
        else None
    )
    metrics["semantic_retention"] = semantic_retention
    METRICS_REGISTRY.observe_trim(
        compress_ratio=compress_ratio,
        semantic_retention=semantic_retention,
    )
    _session_set("history", trimmed)
    _session_set("trim_metrics", metrics)
    if show_debug:
        base = f"[trim] tokens: {token_out}/{token_in} (ratio {compress_ratio})"
        if semantic_retention is not None:
            base += f", retention {semantic_retention}"
        await _send_message(content=base)

    # 3) Run chain
    provider = get_provider(model)
    steps = get_chain_steps(chain_id)
    step_timings: List[StepLatency] = []
    overall_start = perf_counter()
    status: Literal["success", "failure"] = "success"
    error_message: str | None = None
    retryable: bool | None = None
    try:
        for idx, step_name in enumerate(steps, start=1):
            step_label = f"Step {idx}: {step_name}"
            step_start = perf_counter()
            try:
                async with cl.Step(
                    name=step_label,
                    type="llm",
                    show_input=True,
                ) as step:
                    step.input = message.content
                    msgs: List[ChatMessage] = list(trimmed)
                    if step_name != "final":
                        msgs.append(
                            _chat_message(
                                "system", system_hint_for_step(step_name)
                            )
                        )
                    accum: List[str] = []
                    stream_opts = _prepare_provider_options(
                        model, {"temperature": 0.7}
                    )
                    provider_messages = cast(Sequence[Dict[str, Any]], msgs)
                    async for delta in provider.stream(
                        model=model, messages=provider_messages, **stream_opts
                    ):
                        if delta:
                            accum.append(delta)
                            await step.stream_token(delta)
                    output = "".join(accum)
                    step.output = output
                    trimmed.append(_chat_message("assistant", output))
                    _session_set("history", trimmed)
            finally:
                elapsed_ms = (perf_counter() - step_start) * 1000.0
                step_timings.append({"step": step_label, "latency_ms": elapsed_ms})
    except BaseException as exc:
        status = "failure"
        error_message = str(exc) or exc.__class__.__name__
        retryable = _resolve_retryable(exc)
        raise
    finally:
        total_latency_ms = (perf_counter() - overall_start) * 1000.0
        REQUEST_LOGGER.emit(
            InferenceLogRecord(
                status=status,
                model=model,
                chain=chain_id,
                token_in=token_in,
                token_out=token_out,
                compress_ratio=compress_ratio,
                semantic_retention=semantic_retention,
                step_latency_ms=step_timings,
                latency_ms=total_latency_ms,
                retryable=retryable,
                error=error_message,
            )
        )

    # Mirror last output as normal message
    if trimmed and trimmed[-1]["role"] == "assistant":
        await _send_message(content=str(trimmed[-1]["content"]))
