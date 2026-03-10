"""In-memory storage implementations for testing and development."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Sequence

from .storage import (
    ConversationMessage,
    ConversationMetadata,
    EmbeddingRecord,
    EmbeddingStore,
    MessageStore,
    MetadataStore,
)

if TYPE_CHECKING:
    from .storage import MemoryStore


class InMemoryMetadataStore(MetadataStore):
    """In-memory implementation of metadata storage."""

    def __init__(self) -> None:
        self._store: Dict[str, ConversationMetadata] = {}

    async def save_conversation(self, conversation: ConversationMetadata) -> None:
        self._store[conversation.id] = conversation

    async def get_conversation(self, conversation_id: str) -> Optional[ConversationMetadata]:
        return self._store.get(conversation_id)

    async def list_conversations(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ConversationMetadata]:
        conversations = list(self._store.values())
        if user_id:
            conversations = [c for c in conversations if c.user_id == user_id]
        return conversations[offset : offset + limit]

    async def delete_conversation(self, conversation_id: str) -> bool:
        if conversation_id in self._store:
            del self._store[conversation_id]
            return True
        return False


class InMemoryMessageStore(MessageStore):
    """In-memory implementation of message storage."""

    def __init__(self) -> None:
        self._store: Dict[str, List[ConversationMessage]] = {}

    async def save_message(self, message: ConversationMessage) -> None:
        if message.conversation_id not in self._store:
            self._store[message.conversation_id] = []
        self._store[message.conversation_id].append(message)

    async def get_messages(self, conversation_id: str) -> List[ConversationMessage]:
        return self._store.get(conversation_id, [])

    async def delete_messages(self, conversation_id: str) -> int:
        count = len(self._store.get(conversation_id, []))
        if conversation_id in self._store:
            del self._store[conversation_id]
        return count


class InMemoryEmbeddingStore(EmbeddingStore):
    """In-memory implementation of embedding storage."""

    def __init__(self) -> None:
        self._by_message: Dict[str, EmbeddingRecord] = {}
        self._by_conversation: Dict[str, List[EmbeddingRecord]] = {}

    async def save_embedding(self, record: EmbeddingRecord) -> None:
        self._by_message[record.message_id] = record
        if record.conversation_id not in self._by_conversation:
            self._by_conversation[record.conversation_id] = []
        self._by_conversation[record.conversation_id].append(record)

    async def get_embedding(self, message_id: str) -> Optional[EmbeddingRecord]:
        return self._by_message.get(message_id)

    async def search_similar(
        self,
        embedding: Sequence[float],
        limit: int = 10,
        threshold: float = 0.8,
    ) -> List[EmbeddingRecord]:
        """Simple cosine similarity search (for testing only)."""
        import math

        def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        results: List[tuple[float, EmbeddingRecord]] = []
        for record in self._by_message.values():
            score = cosine_similarity(embedding, record.embedding)
            if score >= threshold:
                results.append((score, record))

        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:limit]]

    async def delete_embeddings(self, conversation_id: str) -> int:
        records = self._by_conversation.get(conversation_id, [])
        for record in records:
            self._by_message.pop(record.message_id, None)
        if conversation_id in self._by_conversation:
            del self._by_conversation[conversation_id]
        return len(records)


def create_in_memory_store() -> MemoryStore:
    """Create an in-memory MemoryStore for testing and development."""
    from .storage import MemoryStore

    return MemoryStore(
        metadata_store=InMemoryMetadataStore(),
        message_store=InMemoryMessageStore(),
        embedding_store=InMemoryEmbeddingStore(),
    )