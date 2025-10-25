"""collect_metrics CLI のサニタイズ挙動を検証するテスト群。

技術仕様書（Katamari Technical Spec v1）は semantic_retention が欠損した場合、
JSON では null（Python では None）を配信することを期待値として定義している。
現実装は `SEMANTIC_RETENTION_FALLBACK` を介して欠損・異常値入力を正規化しつつ、
HTTP／ログ由来のサニタイズとセーフガードで移行期間の後方互換性を担保する。本
テスト群はこの仕様と実装の橋渡しとなり、欠損・異常値シナリオにおける期待値が
他テストと矛盾しないことを保証する。"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts.perf import collect_metrics


def test_semantic_retention_fallback_value() -> None:
    assert collect_metrics.SEMANTIC_RETENTION_FALLBACK == pytest.approx(1.0)

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


@pytest.fixture()
def negative_semantic_retention_metrics() -> Iterator[str]:
    payload = (
        "# HELP compress_ratio Ratio of tokens kept after trimming.\n"
        "# TYPE compress_ratio gauge\n"
        "compress_ratio 0.42\n"
        "# HELP semantic_retention Semantic retention score for trimmed context.\n"
        "# TYPE semantic_retention gauge\n"
        "semantic_retention -0.12"
    )
    url, shutdown = _serve_metrics(payload)
    try:
        yield url
    finally:
        shutdown()


def test_preserves_negative_semantic_retention_from_http(
    negative_semantic_retention_metrics: str, tmp_path: Path
) -> None:
    output_path = tmp_path / "metrics_negative.json"
    _run_cli(
        "--metrics-url",
        negative_semantic_retention_metrics,
        "--output",
        str(output_path),
    )

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["semantic_retention"] == -0.12
    assert data["compress_ratio"] == 0.42


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


def test_cli_writes_fallback_for_nan_semantic_retention(tmp_path: Path) -> None:
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
        result = _run_cli("--metrics-url", url, "--output", str(output_path))

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

        data = json.loads(output_path.read_text(encoding="utf-8"))

        assert data["compress_ratio"] == 0.42
        assert (
            data["semantic_retention"]
            == collect_metrics.SEMANTIC_RETENTION_FALLBACK
        )
    finally:
        shutdown()


def test_cli_writes_fallback_when_semantic_retention_missing(tmp_path: Path) -> None:
    payload = (
        "# HELP compress_ratio Ratio of tokens kept after trimming.\n"
        "# TYPE compress_ratio gauge\n"
        "compress_ratio 0.37"
    )
    url, shutdown = _serve_metrics(payload)
    try:
        output_path = tmp_path / "metrics_missing.json"
        result = _run_cli("--metrics-url", url, "--output", str(output_path))

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

        data = json.loads(output_path.read_text(encoding="utf-8"))

        assert data["compress_ratio"] == 0.37
        assert (
            data["semantic_retention"]
            == collect_metrics.SEMANTIC_RETENTION_FALLBACK
        )
    finally:
        shutdown()


def test_prefers_chainlit_log_over_nan_http_metric(tmp_path: Path) -> None:
    payload = (
        "# HELP semantic_retention Semantic retention score for trimmed context.\n"
        "# TYPE semantic_retention gauge\n"
        "semantic_retention nan"
    )
    url, shutdown = _serve_metrics(payload)
    log_path = tmp_path / "chainlit.log"
    log_path.write_text(
        "INFO metrics={\"compress_ratio\": 0.51, \"semantic_retention\": 0.88}",
        encoding="utf-8",
    )
    try:
        output_path = tmp_path / "metrics_override.json"
        _run_cli(
            "--metrics-url",
            url,
            "--log-path",
            str(log_path),
            "--output",
            str(output_path),
        )

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["compress_ratio"] == 0.51
        assert data["semantic_retention"] == 0.88
    finally:
        shutdown()


def test_cli_fails_when_compress_ratio_is_null_and_no_http_candidate(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "chainlit_null.log"
    log_path.write_text(
        "INFO metrics={\"compress_ratio\": null, \"semantic_retention\": 0.72}",
        encoding="utf-8",
    )

    output_path = tmp_path / "metrics_unavailable.json"
    result = _run_cli(
        "--log-path",
        str(log_path),
        "--output",
        str(output_path),
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Failed to collect metrics" in result.stderr
    assert not output_path.exists()


def test_uses_http_compress_ratio_when_log_reports_null(
    tmp_path: Path,
) -> None:
    payload = (
        "# HELP compress_ratio Ratio of tokens kept after trimming.\n"
        "# TYPE compress_ratio gauge\n"
        "compress_ratio 0.47\n"
        "# HELP semantic_retention Semantic retention score for trimmed context.\n"
        "# TYPE semantic_retention gauge\n"
        "semantic_retention 0.88"
    )
    url, shutdown = _serve_metrics(payload)
    log_path = tmp_path / "chainlit_compress_null_override.log"
    log_path.write_text(
        "INFO metrics={\"compress_ratio\": null, \"semantic_retention\": 0.88}",
        encoding="utf-8",
    )
    try:
        output_path = tmp_path / "metrics_http_override.json"
        _run_cli(
            "--metrics-url",
            url,
            "--log-path",
            str(log_path),
            "--output",
            str(output_path),
        )

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["compress_ratio"] == 0.47
        assert data["semantic_retention"] == 0.88
    finally:
        shutdown()


def test_replaces_nan_http_metric_with_log_value(tmp_path: Path) -> None:
    payload = (
        "# HELP compress_ratio Ratio of tokens kept after trimming.\n"
        "# TYPE compress_ratio gauge\n"
        "compress_ratio 0.42\n"
        "# HELP semantic_retention Semantic retention score for trimmed context.\n"
        "# TYPE semantic_retention gauge\n"
        "semantic_retention nan"
    )
    url, shutdown = _serve_metrics(payload)
    log_path = tmp_path / "chainlit_nan_override.log"
    log_path.write_text(
        "INFO metrics={\"compress_ratio\": 0.51, \"semantic_retention\": 0.91}",
        encoding="utf-8",
    )
    try:
        output_path = tmp_path / "metrics_http_nan.json"
        _run_cli(
            "--metrics-url",
            url,
            "--log-path",
            str(log_path),
            "--output",
            str(output_path),
        )

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["compress_ratio"] == 0.42
        assert data["semantic_retention"] == 0.91
        assert data["semantic_retention"] is not None
    finally:
        shutdown()


def test_uses_http_metric_when_log_reports_null(tmp_path: Path) -> None:
    payload = (
        "# HELP compress_ratio Ratio of tokens kept after trimming.\n"
        "# TYPE compress_ratio gauge\n"
        "compress_ratio 0.45\n"
        "# HELP semantic_retention Semantic retention score for trimmed context.\n"
        "# TYPE semantic_retention gauge\n"
        "semantic_retention 0.83"
    )
    url, shutdown = _serve_metrics(payload)
    log_path = tmp_path / "chainlit_null_override.log"
    log_path.write_text(
        "INFO metrics={\"semantic_retention\": null}",
        encoding="utf-8",
    )
    try:
        output_path = tmp_path / "metrics_log_null.json"
        _run_cli(
            "--metrics-url",
            url,
            "--log-path",
            str(log_path),
            "--output",
            str(output_path),
        )

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["compress_ratio"] == 0.45
        assert data["semantic_retention"] == 0.83
    finally:
        shutdown()


def test_ignores_out_of_range_http_metrics_in_favor_of_log(tmp_path: Path) -> None:
    payload = (
        "# HELP compress_ratio Ratio of tokens kept after trimming.\n"
        "# TYPE compress_ratio gauge\n"
        "compress_ratio -0.2\n"
        "# HELP semantic_retention Semantic retention score for trimmed context.\n"
        "# TYPE semantic_retention gauge\n"
        "semantic_retention 1.3"
    )
    url, shutdown = _serve_metrics(payload)
    log_path = tmp_path / "chainlit_out_of_range_override.log"
    log_path.write_text(
        "INFO metrics={\"compress_ratio\": 0.52, \"semantic_retention\": 0.89}",
        encoding="utf-8",
    )
    try:
        output_path = tmp_path / "metrics_out_of_range.json"
        _run_cli(
            "--metrics-url",
            url,
            "--log-path",
            str(log_path),
            "--output",
            str(output_path),
        )

        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["compress_ratio"] == 0.52
        assert data["semantic_retention"] == 0.89
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


def test_missing_semantic_retention_uses_fallback_value(tmp_path: Path) -> None:
    log_path = tmp_path / "fallback.log"
    log_path.write_text(
        "INFO metrics={\"compress_ratio\": 0.55}\nINFO done",
        encoding="utf-8",
    )
    output_path = tmp_path / "fallback.json"

    _run_cli("--log-path", str(log_path), "--output", str(output_path))

    data = json.loads(output_path.read_text(encoding="utf-8"))

    assert data["compress_ratio"] == 0.55
    assert (
        data["semantic_retention"]
        == collect_metrics.SEMANTIC_RETENTION_FALLBACK
    )


def test_latest_log_entry_with_null_semantic_retention_uses_fallback_value(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "chainlit_null.log"
    log_path.write_text(
        (
            "INFO metrics={\"compress_ratio\": 0.64, \"semantic_retention\": 0.88}\n"
            "INFO metrics={\"compress_ratio\": 0.64, \"semantic_retention\": null}"
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "chainlit_null_metrics.json"

    _run_cli("--log-path", str(log_path), "--output", str(output_path))

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["compress_ratio"] == 0.64
    assert (
        data["semantic_retention"]
        == collect_metrics.SEMANTIC_RETENTION_FALLBACK
    )


def test_latest_log_entry_without_semantic_retention_uses_fallback(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "chainlit_missing.log"
    log_path.write_text(
        (
            "INFO metrics={\"compress_ratio\": 0.64, \"semantic_retention\": 0.88}\n"
            "INFO metrics={\"compress_ratio\": 0.64}"
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "chainlit_missing_metrics.json"

    _run_cli("--log-path", str(log_path), "--output", str(output_path))

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["compress_ratio"] == 0.64
    assert (
        data["semantic_retention"]
        == collect_metrics.SEMANTIC_RETENTION_FALLBACK
    )


def test_cli_outputs_semantic_retention_fallback_when_log_reports_null(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "chainlit_null_cli.log"
    log_path.write_text(
        "INFO metrics={\"compress_ratio\": 0.57, \"semantic_retention\": null}",
        encoding="utf-8",
    )
    output_path = tmp_path / "chainlit_null_cli_metrics.json"

    completed = _run_cli("--log-path", str(log_path), "--output", str(output_path))
    assert completed.returncode == 0

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["compress_ratio"] == 0.57
    assert (
        data["semantic_retention"]
        == collect_metrics.SEMANTIC_RETENTION_FALLBACK
    )


def test_non_zero_exit_when_latest_log_missing_compress_ratio(tmp_path: Path) -> None:
    log_path = tmp_path / "chainlit_missing_compress.log"
    log_path.write_text(
        (
            "INFO metrics={\"compress_ratio\": 0.64, \"semantic_retention\": 0.88}\n"
            "INFO metrics={\"semantic_retention\": 0.91}"
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "chainlit_missing_compress_metrics.json"

    completed = _run_cli(
        "--log-path",
        str(log_path),
        "--output",
        str(output_path),
        check=False,
    )

    assert completed.returncode != 0
    assert completed.stdout == ""
    assert "compress_ratio" in completed.stderr
    assert not output_path.exists()


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
