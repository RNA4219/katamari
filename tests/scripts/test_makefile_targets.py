from __future__ import annotations

import shutil
import subprocess

import pytest


def ensure_make_available() -> None:
    if shutil.which("make") is None:
        pytest.skip("'make' command not found", allow_module_level=True)


ensure_make_available()


def run_make_dry(target: str) -> list[str]:
    ensure_make_available()
    result = subprocess.run(
        ["make", "-n", target],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [line for line in result.stdout.splitlines() if line]


def test_make_help_lists_primary_targets() -> None:
    output_lines = run_make_dry("help")
    expected_lines = [
        "printf '%s\\n' 'Available targets:'",
        "printf '%s\\n' '  dev    Install Python dependencies'",
        "printf '%s\\n' '  run    Start Chainlit development server'",
        "printf '%s\\n' '  fmt    Format code with ruff format'",
        "printf '%s\\n' '  lint   Run ruff check .'",
        "printf '%s\\n' '  type   Run mypy --strict'",
        "printf '%s\\n' '  test   Run pytest -q'",
        "printf '%s\\n' '  check  Run lint, type, and test checks'",
    ]
    assert output_lines == expected_lines


def test_make_check_runs_quality_gates() -> None:
    output_lines = run_make_dry("check")
    expected_commands = [
        "ruff check .",
        "mypy --strict",
        "pytest -q",
    ]
    assert output_lines == expected_commands


def test_run_make_dry_skips_when_make_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    def fake_run(*args: object, **kwargs: object):
        raise FileNotFoundError("make not found")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(pytest.skip.Exception):
        run_make_dry("help")
