import ast
from pathlib import Path
from textwrap import dedent

from src.core_ext.persona_compiler import compile_persona_yaml


_APP_PATH = Path(__file__).resolve().parents[1] / "src" / "app.py"


def _get_default_system_prompt() -> str:
    module = ast.parse(_APP_PATH.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_SYSTEM_PROMPT":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, str):
                        return value
    raise AssertionError("DEFAULT_SYSTEM_PROMPT not found")


_DEFAULT_SYSTEM_PROMPT = _get_default_system_prompt()


def test_persona_default():
    sys, issues = compile_persona_yaml("")
    assert sys == _DEFAULT_SYSTEM_PROMPT
    assert issues == []


def test_persona_parse_error_falls_back_to_default():
    sys, issues = compile_persona_yaml("name: [1, 2")

    assert sys == _DEFAULT_SYSTEM_PROMPT
    assert issues and issues[0].startswith("YAML parse error:")


def test_persona_forbidden_terms_reported():
    yaml_input = dedent(
        """
        name: Classified Agent
        style: friendly but classified
        notes: |
          この指示は極秘です。Classified status を維持してください。
        forbid:
          - share classified intel
          - keep calm
        """
    )

    _, issues = compile_persona_yaml(yaml_input)

    assert issues == ["Forbidden terms detected: classified, 極秘."]
