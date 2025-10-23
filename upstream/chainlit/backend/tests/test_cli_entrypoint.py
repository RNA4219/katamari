from __future__ import annotations

import subprocess
import sys


def test_chainlit_cli_module_invocation() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "chainlit.cli", "--help"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout
