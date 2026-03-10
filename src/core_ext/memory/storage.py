"""Storage interfaces and error definitions for memory persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


class StorageError(Exception):
    """Base exception for storage operations."""

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class RetryableStorageError(StorageError):
    """Storage error that can be retried (e.g., connection timeout)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=True)


class FatalStorageError(StorageError):
    """Storage error that cannot be retried (e.g., invalid data)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


class MessageType(str, Enum):
    """Type of stored message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ConversationMessage:
    """A single message in a conversation."""

    id: str
    conversation_id: str
    role: MessageType
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role.value,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        return cls(
            id=data["id"],
            conversation_id=data["conversation_id"],
            role=MessageType(data["role"]),
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConversationMetadata:
    """Metadata for a conversation session."""

    id: str
    user_id: Optional[str] = None
    model: Optional[str] = None
    chain: Optional[str] = None
    persona: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    token_count: int = 0
    compress_ratio: float = 1.0
    semantic_retention: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "model": self.model,
            "chain": self.chain,
            "persona": self.persona,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "token_count": self.token_count,
            "compress_ratio": self.compress_ratio,
            "semantic_retention": self.semantic_retention,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMetadata":
        return cls(
            id=data["id"],
            user_id=data.get("user_id"),
            model=data.get("model"),
            chain=data.get("chain"),
            persona=data.get("persona"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            token_count=data.get("token_count", 0),
            compress_ratio=data.get("compress_ratio", 1.0),
            semantic_retention=data.get("semantic_retention"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class EmbeddingRecord:
    """Embedding vector with associated metadata."""

    id: str
    message_id: str
    conversation_id: str
    embedding: Sequence[float]
    model: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "embedding": list(self.embedding),
            "model": self.model,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmbeddingRecord":
        return cls(
            id=data["id"],
            message_id=data["message_id"],
            conversation_id=data["conversation_id"],
            embedding=data["embedding"],
            model=data["model"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class MetadataStore(ABC):
    """Abstract interface for metadata storage."""

    @abstractmethod
    async def save_conversation(self, conversation: ConversationMetadata) -> None:
        """Save or update conversation metadata."""
        ...

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Optional[ConversationMetadata]:
        """Retrieve conversation metadata by ID."""
        ...

    @abstractmethod
    async def list_conversations(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ConversationMetadata]:
        """List conversations with optional filtering."""
        ...

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete conversation metadata. Returns True if deleted."""
        ...


class MessageStore(ABC):
    """Abstract interface for message storage."""

    @abstractmethod
    async def save_message(self, message: ConversationMessage) -> None:
        """Save a message."""
        ...

    @abstractmethod
    async def get_messages(self, conversation_id: str) -> List[ConversationMessage]:
        """Get all messages for a conversation."""
        ...

    @abstractmethod
    async def delete_messages(self, conversation_id: str) -> int:
        """Delete all messages for a conversation. Returns count deleted."""
        ...


class EmbeddingStore(ABC):
    """Abstract interface for embedding storage."""

    @abstractmethod
    async def save_embedding(self, record: EmbeddingRecord) -> None:
        """Save an embedding record."""
        ...

    @abstractmethod
    async def get_embedding(self, message_id: str) -> Optional[EmbeddingRecord]:
        """Get embedding for a message."""
        ...

    @abstractmethod
    async def search_similar(
        self,
        embedding: Sequence[float],
        limit: int = 10,
        threshold: float = 0.8,
    ) -> List[EmbeddingRecord]:
        """Search for similar embeddings."""
        ...

    @abstractmethod
    async def delete_embeddings(self, conversation_id: str) -> int:
        """Delete embeddings for a conversation. Returns count deleted."""
        ...


class MemoryStore:
    """Unified interface for hybrid memory storage."""

    def __init__(
        self,
        metadata_store: MetadataStore,
        message_store: MessageStore,
        embedding_store: Optional[EmbeddingStore] = None,
    ) -> None:
        self._metadata = metadata_store
        self._messages = message_store
        self._embeddings = embedding_store

    @property
    def metadata(self) -> MetadataStore:
        return self._metadata

    @property
    def messages(self) -> MessageStore:
        return self._messages

    @property
    def embeddings(self) -> Optional[EmbeddingStore]:
        return self._embeddings

    async def save_conversation_with_messages(
        self,
        conversation: ConversationMetadata,
        messages: List[ConversationMessage],
    ) -> None:
        """Save conversation metadata and messages atomically."""
        await self._metadata.save_conversation(conversation)
        for message in messages:
            await self._messages.save_message(message)

    async def get_full_conversation(
        self, conversation_id: str
    ) -> Optional[tuple[ConversationMetadata, List[ConversationMessage]]]:
        """Get conversation metadata and messages together."""
        metadata = await self._metadata.get_conversation(conversation_id)
        if metadata is None:
            return None
        messages = await self._messages.get_messages(conversation_id)
        return metadata, messages

    async def delete_conversation_full(self, conversation_id: str) -> bool:
        """Delete conversation and all associated data."""
        deleted = await self._metadata.delete_conversation(conversation_id)
        if deleted:
            await self._messages.delete_messages(conversation_id)
            if self._embeddings:
                await self._embeddings.delete_embeddings(conversation_id)
        return deleted