"""collect_metrics CLI の挙動を検証するテスト。"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

def _run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    script = Path("scripts/perf/collect_metrics.py")
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _serve_metrics(payload: str) -> tuple[str, Callable[[], None]]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(payload.encode("utf-8"))

        def log_message(self, *_args) -> None:  # noqa: D401
            """Silence HTTP access log."""

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    def _shutdown() -> None:
        server.shutdown()
        server.server_close()
        thread.join()

    return f"http://{host}:{port}/metrics", _shutdown


def test_collects_metrics_from_http_endpoint(tmp_path: Path) -> None:
    payload = (
        "# HELP compress_ratio Ratio of tokens kept after trimming.\n"
        "# TYPE compress_ratio gauge\n"
        "compress_ratio 0.42\n"
        "# HELP semantic_retention Semantic retention score for trimmed context.\n"
        "# TYPE semantic_retention gauge\n"
        "semantic_retention 0.73"
    )
    url, shutdown = _serve_metrics(payload)
    try:
        output_path = tmp_path / "metrics.json"
        _run_cli("--metrics-url", url, "--output", str(output_path))

        assert json.loads(output_path.read_text(encoding="utf-8")) == {
            "compress_ratio": 0.42,
            "semantic_retention": 0.73,
        }
    finally:
        shutdown()


def test_normalizes_nan_semantic_retention_from_prometheus(tmp_path: Path) -> None:
    payload = (
        "# HELP compress_ratio Ratio of tokens kept after trimming.\n"
        "# TYPE compress_ratio gauge\n"
        "compress_ratio 0.42\n"
        "# HELP semantic_retention Semantic retention score for trimmed context.\n"
        "# TYPE semantic_retention gauge\n"
        "semantic_retention nan"
    )
    url, shutdown = _serve_metrics(payload)
    try:
        output_path = tmp_path / "metrics_nan.json"
        _run_cli("--metrics-url", url, "--output", str(output_path))

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["compress_ratio"] == 0.42
        assert data["semantic_retention"] == 1.0
    finally:
        shutdown()


def test_collects_metrics_from_chainlit_log(tmp_path: Path) -> None:
    log_path = tmp_path / "chainlit.log"
    log_path.write_text(
        "INFO start\nINFO metrics={\"compress_ratio\": 0.64, \"semantic_retention\": 0.88}\nINFO done",
        encoding="utf-8",
    )
    output_path = tmp_path / "log_metrics.json"

    _run_cli("--log-path", str(log_path), "--output", str(output_path))

    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "compress_ratio": 0.64,
        "semantic_retention": 0.88,
    }


def test_missing_semantic_retention_falls_back(tmp_path: Path) -> None:
    log_path = tmp_path / "fallback.log"
    log_path.write_text(
        "INFO metrics={\"compress_ratio\": 0.55}\nINFO done",
        encoding="utf-8",
    )
    output_path = tmp_path / "fallback.json"

    _run_cli("--log-path", str(log_path), "--output", str(output_path))

    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "compress_ratio": 0.55,
        "semantic_retention": 1.0,
    }


def test_exit_code_is_non_zero_on_missing_metrics(tmp_path: Path) -> None:
    empty_log = tmp_path / "empty.log"
    empty_log.write_text("INFO nothing", encoding="utf-8")
    output_path = tmp_path / "missing.json"

    completed = _run_cli(
        "--log-path",
        str(empty_log),
        "--output",
        str(output_path),
        check=False,
    )

    assert completed.returncode != 0
    assert not output_path.exists()
    assert "compress_ratio" in completed.stderr
