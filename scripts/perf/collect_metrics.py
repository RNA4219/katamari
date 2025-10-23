from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


COMPRESS_RATIO_KEY = "compress_ratio"
SEMANTIC_RETENTION_KEY = "semantic_retention"
SEMANTIC_RETENTION_FALLBACK: float = 1.0

METRIC_KEYS = (COMPRESS_RATIO_KEY, SEMANTIC_RETENTION_KEY)


def _is_finite(value: float) -> bool:
    try:
        return math.isfinite(value)
    except (TypeError, ValueError):
        return False


def _is_nan(value: float | None) -> bool:
    try:
        return math.isnan(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _parse_prometheus(body: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, *rest = line.split()
        if name in METRIC_KEYS and rest:
            try:
                metrics[name] = float(rest[0])
            except ValueError:
                continue
    return metrics


def _parse_chainlit_log(path: Path) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "compress_ratio" not in line and "semantic_retention" not in line:
            continue
        start, end = line.find("{"), line.rfind("}")
        if start == -1 or end <= start:
            continue
        try:
            payload: Any = json.loads(line[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("metrics"), dict):
            payload = payload["metrics"]
        if not isinstance(payload, dict):
            continue
        for key in METRIC_KEYS:
            if key in payload:
                try:
                    metrics[key] = float(payload[key])
                except (TypeError, ValueError):
                    continue
    return metrics


def _collect(metrics_url: str | None, log_path: Path | None) -> dict[str, float]:
    http_metrics: dict[str, float] = {}
    if metrics_url:
        try:
            with urlopen(metrics_url, timeout=5) as response:  # nosec B310
                charset = response.headers.get_content_charset("utf-8")
                http_metrics.update(
                    _parse_prometheus(response.read().decode(charset))
                )
        except (URLError, OSError):
            pass

    log_metrics: dict[str, float] = {}
    if log_path:
        try:
            for key, value in _parse_chainlit_log(log_path).items():
                if _is_finite(value):
                    log_metrics[key] = value
        except OSError:
            pass

    sanitized: dict[str, float] = {}
    missing: list[str] = []

    for key in METRIC_KEYS:
        candidate: float | None = None

        http_value = http_metrics.get(key)
        http_candidate: float | None = None
        if http_value is not None:
            if _is_nan(http_value):
                http_candidate = None
            elif _is_finite(http_value):
                http_candidate = http_value

        log_value = log_metrics.get(key)
        log_candidate: float | None = None
        if log_value is not None and _is_finite(log_value):
            log_candidate = log_value

        if http_candidate is not None:
            candidate = http_candidate
        elif log_candidate is not None:
            candidate = log_candidate

        if candidate is None:
            if (
                key == SEMANTIC_RETENTION_KEY
                and COMPRESS_RATIO_KEY in sanitized
            ):
                sanitized[key] = SEMANTIC_RETENTION_FALLBACK
                continue
            missing.append(key)
            continue

        sanitized[key] = candidate

    if missing:
        raise RuntimeError("Failed to collect metrics: missing " + ", ".join(missing))

    return sanitized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect performance metrics.")
    parser.add_argument("--metrics-url", help="Prometheus metrics endpoint URL")
    parser.add_argument("--log-path", type=Path, help="Chainlit log file path")
    parser.add_argument("--output", required=True, type=Path, help="JSON output path")
    args = parser.parse_args(argv)
    if not args.metrics_url and not args.log_path:
        parser.error("At least one of --metrics-url or --log-path is required.")
    try:
        metrics = _collect(args.metrics_url, args.log_path)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metrics, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
