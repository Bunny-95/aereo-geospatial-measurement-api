"""Interfaces shared by upload storage implementations."""

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StoredObject:
    """Safe metadata describing an object persisted by a storage backend."""

    key: str
    size_bytes: int
    sha256: str
    path: str


class StorageBackend(Protocol):
    """Minimal contract for replaceable object storage backends."""

    def save(self, stream: BinaryIO, extension: str, max_size_bytes: int) -> StoredObject:
        """Store a stream and return generated object metadata."""

    def delete(self, key: str) -> None:
        """Remove a stored object when compensating for a failed operation."""
