from enum import Enum
from typing import Optional

try:
    from llama_index.core.callbacks.schema import CBEventType, EventPayload
    from llama_index.core.llms import ChatMessage, ChatResponse
    from llama_index.core.schema import NodeWithScore, TextNode
except ModuleNotFoundError:  # pragma: no cover - exercised via dedicated test
    class CBEventType(str, Enum):
        RETRIEVE = "retrieve"
        LLM = "llm"

    class EventPayload(str, Enum):
        NODES = "nodes"
        RESPONSE = "response"
        PROMPT = "prompt"
        MESSAGES = "messages"
        TOOL = "tool"
        FUNCTION_CALL = "function_call"
        FUNCTION_OUTPUT = "function_output"

    class _Role:
        def __init__(self, value: str) -> None:
            self.value = value

    class ChatMessage:
        def __init__(self, content: Optional[str] = None, role: str = "assistant") -> None:
            self.content = content
            self.role = _Role(role)

    class ChatResponse:
        def __init__(self, message: ChatMessage, raw: Optional[object] = None) -> None:
            self.message = message
            self.raw = raw

    class TextNode:
        def __init__(self, text: str) -> None:
            self.text = text

        def get_text(self) -> str:
            return self.text

    class NodeWithScore:
        def __init__(self, node: TextNode, score: float) -> None:
            self.node = node
            self.score = score

import chainlit as cl


@cl.on_chat_start
async def start():
    await cl.Message(content="LlamaIndexCb").send()

    cb = cl.LlamaIndexCallbackHandler()

    cb.on_event_start(CBEventType.RETRIEVE, payload={})

    await cl.sleep(0.2)

    cb.on_event_end(
        CBEventType.RETRIEVE,
        payload={
            EventPayload.NODES: [
                NodeWithScore(node=TextNode(text="This is text1"), score=1)
            ]
        },
    )

    cb.on_event_start(CBEventType.LLM)

    await cl.sleep(0.2)

    response = ChatResponse(message=ChatMessage(content="This is the LLM response"))
    cb.on_event_end(
        CBEventType.LLM,
        payload={
            EventPayload.RESPONSE: response,
            EventPayload.PROMPT: "This is the LLM prompt",
        },
    )
