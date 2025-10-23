
from textwrap import dedent

from src.core_ext.persona_compiler import compile_persona_yaml

def test_persona_default():
    sys, issues = compile_persona_yaml("")
    assert "Katamari" in sys
    assert issues == []


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
