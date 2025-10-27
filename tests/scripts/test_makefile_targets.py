from __future__ import annotations

import shutil
import subprocess

import pytest


if shutil.which("make") is None:
    pytest.skip("'make' command not found", allow_module_level=True)


def run_make_dry(target: str) -> list[str]:
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
