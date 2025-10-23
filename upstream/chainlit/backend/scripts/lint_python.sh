#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".mypy-venv"

use_local_venv() {
  if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
    "${VENV_DIR}/bin/pip" install --upgrade pip
    "${VENV_DIR}/bin/pip" install -e '.[mypy]'
  fi

  if "${VENV_DIR}/bin/dmypy" run -- chainlit/ tests/; then
    exit 0
  fi

  echo "dmypy in virtualenv failed, falling back to mypy" >&2
  exec "${VENV_DIR}/bin/python" -m mypy --config-file pyproject.toml chainlit tests/
}

if command -v uv >/dev/null 2>&1; then
  if uv run dmypy run -- chainlit/ tests/; then
    exit 0
  fi
  echo "uv run failed, falling back to virtualenv" >&2
fi

use_local_venv
