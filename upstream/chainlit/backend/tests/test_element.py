import asyncio
from unittest.mock import AsyncMock, Mock

from chainlit.context import ChainlitContext, context_var
from chainlit.element import File
from chainlit.session import WebsocketSession


def test_create_returns_false_when_already_persisted():
    async def run() -> None:
        element = File(
            url="https://example.com/test.txt",
            thread_id="test-thread",
        )
        element.persisted = True
        element.updatable = False

        result = await element._create()

        assert result is False

    asyncio.run(run())


def test_create_returns_true_when_persisting_new_file():
    async def run() -> None:
        element = File(path="/tmp/file.txt", thread_id="test-thread")

        session = Mock(spec=WebsocketSession)
        session.thread_id = "test-thread"
        session.persist_file = AsyncMock(return_value={"id": "persisted"})
        session.emit = AsyncMock()

        context = ChainlitContext(session)
        token = context_var.set(context)
        try:
            result = await element._create()
        finally:
            context_var.reset(token)

        assert result is True
        assert element.chainlit_key == "persisted"

    asyncio.run(run())
