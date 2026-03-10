"""Tests for memory persistence layer."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.core_ext.memory import (
    ConversationMessage,
    ConversationMetadata,
    EmbeddingRecord,
    FatalStorageError,
    InMemoryEmbeddingStore,
    InMemoryMessageStore,
    InMemoryMetadataStore,
    MemoryStore,
    MessageType,
    RetryableStorageError,
    StorageError,
    create_in_memory_store,
)


class TestConversationMessage:
    """Tests for ConversationMessage dataclass."""

    def test_to_dict_and_from_dict(self) -> None:
        msg = ConversationMessage(
            id="msg-1",
            conversation_id="conv-1",
            role=MessageType.USER,
            content="Hello, world!",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            metadata={"key": "value"},
        )

        data = msg.to_dict()
        restored = ConversationMessage.from_dict(data)

        assert restored.id == msg.id
        assert restored.conversation_id == msg.conversation_id
        assert restored.role == msg.role
        assert restored.content == msg.content
        assert restored.created_at == msg.created_at
        assert restored.metadata == msg.metadata


class TestConversationMetadata:
    """Tests for ConversationMetadata dataclass."""

    def test_to_dict_and_from_dict(self) -> None:
        meta = ConversationMetadata(
            id="conv-1",
            user_id="user-123",
            model="gpt-5-main",
            chain="reflect",
            persona="assistant",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 13, 0, 0),
            token_count=1500,
            compress_ratio=0.65,
            semantic_retention=0.85,
            metadata={"custom": "data"},
        )

        data = meta.to_dict()
        restored = ConversationMetadata.from_dict(data)

        assert restored.id == meta.id
        assert restored.user_id == meta.user_id
        assert restored.model == meta.model
        assert restored.chain == meta.chain
        assert restored.persona == meta.persona
        assert restored.token_count == meta.token_count
        assert restored.compress_ratio == meta.compress_ratio
        assert restored.semantic_retention == meta.semantic_retention


class TestEmbeddingRecord:
    """Tests for EmbeddingRecord dataclass."""

    def test_to_dict_and_from_dict(self) -> None:
        record = EmbeddingRecord(
            id="emb-1",
            message_id="msg-1",
            conversation_id="conv-1",
            embedding=[0.1, 0.2, 0.3],
            model="text-embedding-3-small",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        )

        data = record.to_dict()
        restored = EmbeddingRecord.from_dict(data)

        assert restored.id == record.id
        assert restored.message_id == record.message_id
        assert list(restored.embedding) == list(record.embedding)
        assert restored.model == record.model


class TestInMemoryMetadataStore:
    """Tests for InMemoryMetadataStore."""

    @pytest.fixture
    def store(self) -> InMemoryMetadataStore:
        return InMemoryMetadataStore()

    @pytest.mark.asyncio
    async def test_save_and_get_conversation(self, store: InMemoryMetadataStore) -> None:
        meta = ConversationMetadata(id="conv-1", model="gpt-5-main")

        await store.save_conversation(meta)
        result = await store.get_conversation("conv-1")

        assert result is not None
        assert result.id == "conv-1"
        assert result.model == "gpt-5-main"

    @pytest.mark.asyncio
    async def test_get_nonexistent_conversation(
        self, store: InMemoryMetadataStore
    ) -> None:
        result = await store.get_conversation("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_conversations_with_filter(
        self, store: InMemoryMetadataStore
    ) -> None:
        await store.save_conversation(
            ConversationMetadata(id="conv-1", user_id="user-a")
        )
        await store.save_conversation(
            ConversationMetadata(id="conv-2", user_id="user-b")
        )
        await store.save_conversation(
            ConversationMetadata(id="conv-3", user_id="user-a")
        )

        result = await store.list_conversations(user_id="user-a")
        assert len(result) == 2
        assert all(c.user_id == "user-a" for c in result)

    @pytest.mark.asyncio
    async def test_delete_conversation(self, store: InMemoryMetadataStore) -> None:
        await store.save_conversation(ConversationMetadata(id="conv-1"))

        deleted = await store.delete_conversation("conv-1")
        assert deleted is True

        result = await store.get_conversation("conv-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(
        self, store: InMemoryMetadataStore
    ) -> None:
        deleted = await store.delete_conversation("nonexistent")
        assert deleted is False


class TestInMemoryMessageStore:
    """Tests for InMemoryMessageStore."""

    @pytest.fixture
    def store(self) -> InMemoryMessageStore:
        return InMemoryMessageStore()

    @pytest.mark.asyncio
    async def test_save_and_get_messages(self, store: InMemoryMessageStore) -> None:
        msg1 = ConversationMessage(
            id="msg-1",
            conversation_id="conv-1",
            role=MessageType.USER,
            content="Hello",
        )
        msg2 = ConversationMessage(
            id="msg-2",
            conversation_id="conv-1",
            role=MessageType.ASSISTANT,
            content="Hi there!",
        )

        await store.save_message(msg1)
        await store.save_message(msg2)

        messages = await store.get_messages("conv-1")
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there!"

    @pytest.mark.asyncio
    async def test_delete_messages(self, store: InMemoryMessageStore) -> None:
        await store.save_message(
            ConversationMessage(
                id="msg-1",
                conversation_id="conv-1",
                role=MessageType.USER,
                content="Test",
            )
        )

        count = await store.delete_messages("conv-1")
        assert count == 1

        messages = await store.get_messages("conv-1")
        assert len(messages) == 0


class TestInMemoryEmbeddingStore:
    """Tests for InMemoryEmbeddingStore."""

    @pytest.fixture
    def store(self) -> InMemoryEmbeddingStore:
        return InMemoryEmbeddingStore()

    @pytest.mark.asyncio
    async def test_save_and_get_embedding(self, store: InMemoryEmbeddingStore) -> None:
        record = EmbeddingRecord(
            id="emb-1",
            message_id="msg-1",
            conversation_id="conv-1",
            embedding=[0.1, 0.2, 0.3],
            model="text-embedding-3-small",
        )

        await store.save_embedding(record)
        result = await store.get_embedding("msg-1")

        assert result is not None
        assert list(result.embedding) == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_search_similar(self, store: InMemoryEmbeddingStore) -> None:
        # Save some embeddings
        await store.save_embedding(
            EmbeddingRecord(
                id="emb-1",
                message_id="msg-1",
                conversation_id="conv-1",
                embedding=[1.0, 0.0, 0.0],
                model="test",
            )
        )
        await store.save_embedding(
            EmbeddingRecord(
                id="emb-2",
                message_id="msg-2",
                conversation_id="conv-1",
                embedding=[0.9, 0.1, 0.0],
                model="test",
            )
        )
        await store.save_embedding(
            EmbeddingRecord(
                id="emb-3",
                message_id="msg-3",
                conversation_id="conv-1",
                embedding=[0.0, 1.0, 0.0],
                model="test",
            )
        )

        # Search for similar to [1.0, 0.0, 0.0]
        results = await store.search_similar([1.0, 0.0, 0.0], limit=2, threshold=0.8)

        assert len(results) == 2
        assert results[0].id == "emb-1"  # Exact match
        assert results[1].id == "emb-2"  # Close match


class TestMemoryStore:
    """Tests for unified MemoryStore."""

    @pytest.fixture
    def store(self) -> MemoryStore:
        return create_in_memory_store()

    @pytest.mark.asyncio
    async def test_save_and_get_full_conversation(self, store: MemoryStore) -> None:
        meta = ConversationMetadata(id="conv-1", model="gpt-5-main")
        messages = [
            ConversationMessage(
                id="msg-1",
                conversation_id="conv-1",
                role=MessageType.USER,
                content="Hello",
            ),
            ConversationMessage(
                id="msg-2",
                conversation_id="conv-1",
                role=MessageType.ASSISTANT,
                content="Hi!",
            ),
        ]

        await store.save_conversation_with_messages(meta, messages)

        result = await store.get_full_conversation("conv-1")
        assert result is not None
        result_meta, result_messages = result

        assert result_meta.id == "conv-1"
        assert len(result_messages) == 2

    @pytest.mark.asyncio
    async def test_delete_conversation_full(self, store: MemoryStore) -> None:
        meta = ConversationMetadata(id="conv-1")
        msg = ConversationMessage(
            id="msg-1",
            conversation_id="conv-1",
            role=MessageType.USER,
            content="Test",
        )

        await store.save_conversation_with_messages(meta, [msg])

        deleted = await store.delete_conversation_full("conv-1")
        assert deleted is True

        result = await store.get_full_conversation("conv-1")
        assert result is None


class TestStorageErrors:
    """Tests for storage error types."""

    def test_retryable_storage_error(self) -> None:
        error = RetryableStorageError("Connection timeout")
        assert error.retryable is True
        assert "Connection timeout" in str(error)

    def test_fatal_storage_error(self) -> None:
        error = FatalStorageError("Invalid data format")
        assert error.retryable is False
        assert "Invalid data format" in str(error)

    def test_base_storage_error_default_retryable(self) -> None:
        error = StorageError("Unknown error")
        assert error.retryable is False