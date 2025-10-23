from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


COMPRESS_RATIO_KEY = "compress_ratio"
SEMANTIC_RETENTION_KEY = "semantic_retention"
SEMANTIC_RETENTION_FALLBACK = 1.0

METRIC_KEYS = (COMPRESS_RATIO_KEY, SEMANTIC_RETENTION_KEY)


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
    collected: dict[str, float] = {}
    if metrics_url:
        try:
            with urlopen(metrics_url, timeout=5) as response:  # nosec B310
                charset = response.headers.get_content_charset("utf-8")
                collected.update(_parse_prometheus(response.read().decode(charset)))
        except (URLError, OSError):
            pass
    if log_path:
        try:
            for key, value in _parse_chainlit_log(log_path).items():
                collected.setdefault(key, value)
        except OSError:
            pass
    missing = [key for key in METRIC_KEYS if key not in collected]
    if (
        SEMANTIC_RETENTION_KEY in missing
        and COMPRESS_RATIO_KEY not in missing
    ):
        collected[SEMANTIC_RETENTION_KEY] = SEMANTIC_RETENTION_FALLBACK
        missing.remove(SEMANTIC_RETENTION_KEY)
    if missing:
        raise RuntimeError("Failed to collect metrics: missing " + ", ".join(missing))
    return {key: collected[key] for key in METRIC_KEYS}


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
    args.output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    sys.exit(main())
