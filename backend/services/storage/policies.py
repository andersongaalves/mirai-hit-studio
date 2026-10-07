"""Validation policies shared by all providers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Mapping

from .contracts import StorageScope, StorageValidationError


PRODUCTION_MIME_TYPES = frozenset({
    "application/pdf",
    "application/zip",
    "audio/flac",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "video/mp4",
})


@dataclass(frozen=True, slots=True)
class StoragePolicy:
    allowed_content_types: frozenset[str]
    max_bytes: int
    require_non_empty: bool = True

    def validate_size_and_type(self, content_type: str, size: int) -> None:
        if content_type not in self.allowed_content_types:
            raise StorageValidationError("Tipo de arquivo nao permitido.")
        if size < 0 or (self.require_non_empty and size == 0) or size > self.max_bytes:
            raise StorageValidationError("Tamanho de arquivo nao permitido.")

    def validate(self, data: bytes, content_type: str) -> None:
        self.validate_size_and_type(content_type, len(data))
        if not _matches_signature(data, content_type):
            raise StorageValidationError("Conteudo do arquivo nao corresponde ao tipo informado.")


DEFAULT_POLICIES: Mapping[StorageScope, StoragePolicy] = {
    StorageScope.PUBLIC_IMAGE: StoragePolicy(
        frozenset({"image/jpeg", "image/png", "image/webp", "image/avif"}),
        10 * 1024 * 1024,
    ),
    StorageScope.PORTFOLIO_AUDIO: StoragePolicy(
        frozenset({"audio/mpeg", "audio/mp3"}),
        30 * 1024 * 1024,
    ),
    StorageScope.PRODUCTION_TEMP: StoragePolicy(PRODUCTION_MIME_TYPES, 50 * 1024 * 1024),
    StorageScope.PRODUCTION_FINAL: StoragePolicy(PRODUCTION_MIME_TYPES, 50 * 1024 * 1024),
    StorageScope.PROPOSAL_DOCUMENT: StoragePolicy(frozenset({"application/pdf"}), 20 * 1024 * 1024),
}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_sha256(value: str | None) -> str | None:
    if value is not None and (len(value) != 64 or any(char not in "0123456789abcdef" for char in value)):
        raise StorageValidationError("Checksum SHA-256 invalido.")
    return value


def _matches_signature(data: bytes, content_type: str) -> bool:
    if content_type == "application/pdf":
        return data.startswith(b"%PDF-")
    if content_type == "application/zip":
        return data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    if content_type in {"audio/mpeg", "audio/mp3"}:
        return data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    if content_type in {"audio/wav", "audio/x-wav"}:
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE"
    if content_type == "audio/flac":
        return data.startswith(b"fLaC")
    if content_type in {"audio/mp4", "video/mp4"}:
        return len(data) >= 12 and data[4:8] == b"ftyp"
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if content_type == "image/avif":
        return len(data) >= 12 and data[4:8] == b"ftyp" and b"avif" in data[8:32]
    return False
