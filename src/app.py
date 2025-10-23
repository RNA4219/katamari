
# Katamari (Chainlit Fork) - app.py (skeleton)
# Run (dev):
#   pip install -r requirements.txt
#   export OPENAI_API_KEY=sk-...
#   chainlit run src/app.py --host 0.0.0.0 --port 8787

import asyncio
import os
from threading import Lock
from time import perf_counter
from typing import Any, Dict, List

import chainlit as cl
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from chainlit.input_widget import Select, Slider, TextInput, Switch
from chainlit.server import app as chainlit_app, router as chainlit_router

from core_ext.logging import InferenceLogRecord, StepLatency, StructuredLogger
from core_ext.persona_compiler import compile_persona_yaml
from core_ext.context_trimmer import trim_messages
from core_ext.retention import compute_semantic_retention
from core_ext.prethought import analyze_intent
from core_ext.multistep import get_chain_steps, system_hint_for_step
from providers.google_gemini_client import GoogleGeminiProvider
from providers.openai_client import OpenAIProvider

DEFAULT_MODEL = "gpt-5-main"
DEFAULT_CHAIN = "single"
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant named Katamari."

_REASONING_DEFAULT = {"effort": "medium", "parallel": True}


def _prepare_provider_options(model_id: str, base: Dict[str, Any]) -> Dict[str, Any]:
    opts = dict(base)
    if "thinking" in model_id.lower() and "reasoning" not in opts:
        opts["reasoning"] = dict(_REASONING_DEFAULT)
    return opts

_DISABLED_RETENTION_VALUES = {"", "none", "off", "0", "false"}


class MetricsRegistry:
    """Collect runtime metrics for operational endpoints."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._compress_ratio = 1.0
        self._semantic_retention = 1.0

    def observe_trim(
        self, *, compress_ratio: float, semantic_retention: float | None = None
    ) -> None:
        """Record the latest trimming metrics."""

        retention = 1.0 if semantic_retention is None else float(semantic_retention)
        with self._lock:
            self._compress_ratio = float(compress_ratio)
            self._semantic_retention = retention

    def snapshot(self) -> Dict[str, float]:
        with self._lock:
            return {
                "compress_ratio": self._compress_ratio,
                "semantic_retention": self._semantic_retention,
            }

    def export_prometheus(self) -> str:
        metrics = self.snapshot()
        lines = [
            "# HELP compress_ratio Ratio of tokens kept after trimming.",
            "# TYPE compress_ratio gauge",
            f"compress_ratio {metrics['compress_ratio']}",
            "# HELP semantic_retention Semantic retention score for trimmed context.",
            "# TYPE semantic_retention gauge",
            f"semantic_retention {metrics['semantic_retention']}",
        ]
        return "\n".join(lines) + "\n"


METRICS_REGISTRY = MetricsRegistry()
REQUEST_LOGGER = StructuredLogger()


def _to_int(value: object) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _to_float(value: object, default: float = 0.0) -> float:
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
    before: List[Dict[str, Any]],
    after: List[Dict[str, Any]],
    metrics: Dict[str, Any],
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
async def on_start():
    cl.user_session.set("model", os.getenv("DEFAULT_MODEL", DEFAULT_MODEL))
    cl.user_session.set("chain", os.getenv("DEFAULT_CHAIN", DEFAULT_CHAIN))
    cl.user_session.set("trim_tokens", 4096)
    cl.user_session.set("min_turns", 0)
    cl.user_session.set("system", "You are a helpful assistant named Katamari.")

    settings = await cl.ChatSettings(
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
    ).send()

    await apply_settings(settings)

@cl.on_settings_update
async def on_settings_update(settings: Dict):
    await apply_settings(settings)

async def apply_settings(settings: Dict):
    for k in ("model","chain","trim_tokens","min_turns","show_debug"):
        if k in settings:
            cl.user_session.set(k, settings[k])

    if "persona_yaml" in settings:
        yaml_raw = settings.get("persona_yaml", "")
        yaml_str = yaml_raw if isinstance(yaml_raw, str) else ""
        if yaml_str.strip() == "":
            previous = cl.user_session.get("system") or DEFAULT_SYSTEM_PROMPT
            cl.user_session.set("system", DEFAULT_SYSTEM_PROMPT)
            if previous != DEFAULT_SYSTEM_PROMPT:
                await cl.Message(
                    content="[persona issues]\nPersona prompt reset to default."
                ).send()
            return

        if yaml_str:
            system, issues = compile_persona_yaml(yaml_str)
            cl.user_session.set("system", system)
            if issues:
                await cl.Message(content="\n".join(["[persona issues]"]+issues)).send()

@cl.on_message
async def on_message(message: cl.Message):
    model: str = cl.user_session.get("model") or DEFAULT_MODEL
    chain_id: str = cl.user_session.get("chain") or DEFAULT_CHAIN
    target_tokens: int = int(cl.user_session.get("trim_tokens") or 4096)
    min_turns: int = _to_int(cl.user_session.get("min_turns"))
    show_debug: bool = bool(cl.user_session.get("show_debug"))

    # 1) Prethought (optional display as a step)
    intent = analyze_intent(message.content)
    if show_debug and intent:
        await cl.Message(content=f"[prethought]\n{intent}").send()

    # 2) Build/trim history
    hist: List[Dict] = cl.user_session.get("history") or []
    system = cl.user_session.get("system") or DEFAULT_SYSTEM_PROMPT
    if not hist or hist[0].get("role") != "system":
        hist = [{"role":"system","content":system}] + hist
    hist.append({"role":"user","content":message.content})

    trimmed, metrics = trim_messages(hist, target_tokens, model, min_turns=min_turns)
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
    cl.user_session.set("history", trimmed)
    cl.user_session.set("trim_metrics", metrics)
    if show_debug:
        base = f"[trim] tokens: {token_out}/{token_in} (ratio {compress_ratio})"
        if semantic_retention is not None:
            base += f", retention {semantic_retention}"
        await cl.Message(content=base).send()

    # 3) Run chain
    provider = get_provider(model)
    steps = get_chain_steps(chain_id)
    step_timings: List[StepLatency] = []
    overall_start = perf_counter()
    status: str = "success"
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
                    msgs = list(trimmed)
                    if step_name != "final":
                        msgs.append(
                            {"role": "system", "content": system_hint_for_step(step_name)}
                        )
                    accum: List[str] = []
                    stream_opts = _prepare_provider_options(
                        model, {"temperature": 0.7}
                    )
                    async for delta in provider.stream(
                        model=model, messages=msgs, **stream_opts
                    ):
                        if delta:
                            accum.append(delta)
                            await step.stream_token(delta)
                    output = "".join(accum)
                    step.output = output
                    trimmed.append({"role": "assistant", "content": output})
                    cl.user_session.set("history", trimmed)
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
        await cl.Message(content=trimmed[-1]["content"]).send()
