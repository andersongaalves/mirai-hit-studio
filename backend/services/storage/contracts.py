"""Provider-neutral contracts for stored objects.

References are identifiers, never credentials or temporary URLs.  Application
layers can persist their string form without learning a provider SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
import re
from typing import Mapping
from urllib.parse import urlsplit


class StorageError(Exception):
    """Base class for sanitized storage failures."""


class StorageUnavailable(StorageError):
    pass


class StorageInvalidReference(StorageError):
    pass


class StorageValidationError(StorageError):
    pass


class StorageUploadError(StorageError):
    pass


class StorageDeleteError(StorageError):
    pass


class StorageNotFound(StorageError):
    pass


class StorageConfigurationError(StorageError):
    pass


class StorageConflictError(StorageError):
    pass


class StorageOperationNotSupported(StorageError):
    pass


class StorageScope(StrEnum):
    PUBLIC_IMAGE = "public_image"
    PORTFOLIO_AUDIO = "portfolio_audio"
    PRODUCTION_TEMP = "production_temp"
    PRODUCTION_FINAL = "production_final"
    PROPOSAL_DOCUMENT = "proposal_document"


class ObjectVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


_PROVIDER = re.compile(r"[a-z][a-z0-9_-]{0,31}")
_NAMESPACE = re.compile(r"[a-z0-9][a-z0-9._-]{0,99}")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def validate_object_key(key: str) -> str:
    if not isinstance(key, str) or not key or len(key) > 1024:
        raise StorageInvalidReference("Referencia de objeto invalida.")
    if "\\" in key or "%" in key or "?" in key or "#" in key:
        raise StorageInvalidReference("Referencia de objeto invalida.")
    segments = key.split("/")
    if any(segment in {"", ".", ".."} or not _SEGMENT.fullmatch(segment) for segment in segments):
        raise StorageInvalidReference("Referencia de objeto invalida.")
    return key


@dataclass(frozen=True, slots=True)
class ObjectReference:
    provider: str
    namespace: str
    key: str

    def __post_init__(self) -> None:
        if not _PROVIDER.fullmatch(self.provider or ""):
            raise StorageInvalidReference("Provider da referencia invalido.")
        if not _NAMESPACE.fullmatch(self.namespace or ""):
            raise StorageInvalidReference("Namespace da referencia invalido.")
        validate_object_key(self.key)

    def __str__(self) -> str:
        return f"{self.provider}://{self.namespace}/{self.key}"

    @classmethod
    def parse(cls, value: str) -> "ObjectReference":
        if not isinstance(value, str) or len(value) > 1200:
            raise StorageInvalidReference("Referencia de objeto invalida.")
        parsed = urlsplit(value)
        if (
            not parsed.scheme
            or not parsed.netloc
            or not parsed.path.startswith("/")
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise StorageInvalidReference("Referencia de objeto invalida.")
        return cls(parsed.scheme, parsed.netloc, parsed.path[1:])


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    size: int
    content_type: str
    etag: str | None = None
    sha256: str | None = None
    custom: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoredObject:
    reference: ObjectReference
    metadata: ObjectMetadata
    public_url: str | None = None


@dataclass(frozen=True, slots=True)
class PresignedRequest:
    reference: ObjectReference
    url: str
    method: str
    expires_at: datetime
    headers: Mapping[str, str] = field(default_factory=dict)


class StorageAdapter(ABC):
    provider: str
    scope: StorageScope
    visibility: ObjectVisibility

    @abstractmethod
    def save(
        self,
        data: bytes,
        content_type: str,
        *,
        key: str | None = None,
        metadata: Mapping[str, str] | None = None,
        sha256: str | None = None,
    ) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def delete(self, reference: ObjectReference | str) -> None:
        raise NotImplementedError

    def read(self, reference: ObjectReference | str) -> bytes:
        raise StorageOperationNotSupported("Leitura nao suportada por este storage.")

    def stat(self, reference: ObjectReference | str) -> ObjectMetadata:
        raise StorageOperationNotSupported("Metadados nao suportados por este storage.")

    def get_public_url(self, reference: ObjectReference | str) -> str:
        raise StorageOperationNotSupported("URL publica nao suportada por este storage.")

    def presign_get(self, reference: ObjectReference | str, *, expires_seconds: int = 300) -> PresignedRequest:
        raise StorageOperationNotSupported("Download assinado nao suportado por este storage.")

    def presign_put(
        self,
        content_type: str,
        expected_size: int,
        *,
        key: str | None = None,
        expires_seconds: int = 300,
        sha256: str | None = None,
    ) -> PresignedRequest:
        raise StorageOperationNotSupported("Upload assinado nao suportado por este storage.")


def coerce_reference(value: ObjectReference | str) -> ObjectReference:
    return value if isinstance(value, ObjectReference) else ObjectReference.parse(value)
