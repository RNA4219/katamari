from __future__ import annotations
import importlib.util
import os
import pathlib
import sys

import pytest

@pytest.fixture
def cleanup_llama_index_module() -> None:
    sys.modules.pop("llama_index", None)

@pytest.mark.usefixtures("cleanup_llama_index_module")
def test_llama_index_cb_sample_loads_without_llama_index(tmp_path: pathlib.Path) -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    chainlit_root = repo_root / "upstream" / "chainlit"
    previous_app_root = os.environ.get("CHAINLIT_APP_ROOT")
    os.environ["CHAINLIT_APP_ROOT"] = str(tmp_path)
    sys.path.insert(0, str(chainlit_root / "backend"))

    try:
        spec = importlib.util.spec_from_file_location(
            "chainlit.cypress.e2e.llama_index_cb.main",
            chainlit_root / "cypress" / "e2e" / "llama_index_cb" / "main.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    finally:
        if previous_app_root is not None:
            os.environ["CHAINLIT_APP_ROOT"] = previous_app_root
        else:
            os.environ.pop("CHAINLIT_APP_ROOT", None)
        sys.path.pop(0)

    message = module.ChatMessage(content="hello")
    response = module.ChatResponse(message=message)

    assert response.message.content == "hello"

    node = module.TextNode(text="sample text")
    wrapped = module.NodeWithScore(node=node, score=1.0)

    assert wrapped.node.get_text() == "sample text"
    assert module.EventPayload.RESPONSE.value == "response"
    assert module.CBEventType.LLM.value == "llm"
