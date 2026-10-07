"""Filesystem-backed storage for local development."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from app.core.exceptions import UploadValidationError
from app.storage.base import StoredObject

CHUNK_SIZE_BYTES = 1024 * 1024


class LocalStorage:
    """Store uploads under one configured root using generated, safe object keys."""

    def __init__(self, root_directory: Path) -> None:
        self.root_directory = root_directory.resolve()
        self.root_directory.mkdir(parents=True, exist_ok=True)

    def save(self, stream: BinaryIO, extension: str, max_size_bytes: int) -> StoredObject:
        """Write a stream in chunks while calculating its SHA-256 digest."""
        normalized_extension = self._normalize_extension(extension)
        key = f"uploads/{uuid4().hex}{normalized_extension}"
        destination = self._resolve_key(key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with destination.open("xb") as output:
                while chunk := stream.read(CHUNK_SIZE_BYTES):
                    size_bytes += len(chunk)
                    if size_bytes > max_size_bytes:
                        raise UploadValidationError(
                            "Uploaded file exceeds the configured size limit."
                        )
                    digest.update(chunk)
                    output.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        if size_bytes == 0:
            destination.unlink(missing_ok=True)
            raise UploadValidationError("Uploaded file must not be empty.")

        return StoredObject(
            key=key, size_bytes=size_bytes, sha256=digest.hexdigest(), path=str(destination)
        )

    def delete(self, key: str) -> None:
        """Delete one generated object key; invalid keys are rejected."""
        self._resolve_key(key).unlink(missing_ok=True)

    def _resolve_key(self, key: str) -> Path:
        key_path = PurePosixPath(key)
        if key_path.is_absolute() or ".." in key_path.parts:
            raise UploadValidationError("Invalid storage key.")
        resolved = (self.root_directory / Path(*key_path.parts)).resolve()
        if not resolved.is_relative_to(self.root_directory):
            raise UploadValidationError("Invalid storage key.")
        return resolved

    @staticmethod
    def _normalize_extension(extension: str) -> str:
        normalized = extension.lower()
        if not normalized.startswith(".") or any(
            marker in normalized for marker in ("/", "\\", "\x00")
        ):
            raise UploadValidationError("Invalid file extension.")
        return normalized
