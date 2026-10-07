"""Deterministic in-process storage used by tests and local fakes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping

from .contracts import (
    ObjectMetadata,
    ObjectReference,
    ObjectVisibility,
    PresignedRequest,
    StorageAdapter,
    StorageConfigurationError,
    StorageConflictError,
    StorageInvalidReference,
    StorageNotFound,
    StorageOperationNotSupported,
    StorageScope,
    StoredObject,
    coerce_reference,
    validate_object_key,
)
from .keys import generate_object_key
from .policies import DEFAULT_POLICIES, StoragePolicy, sha256_hex, validate_sha256


class InMemoryStorage(StorageAdapter):
    provider = "memory"

    def __init__(
        self,
        scope: StorageScope,
        *,
        visibility: ObjectVisibility | None = None,
        policy: StoragePolicy | None = None,
    ) -> None:
        self.scope = scope
        self.visibility = visibility or (
            ObjectVisibility.PUBLIC
            if scope in {StorageScope.PUBLIC_IMAGE, StorageScope.PORTFOLIO_AUDIO}
            else ObjectVisibility.PRIVATE
        )
        self.policy = policy or DEFAULT_POLICIES[scope]
        self.namespace = scope.value.replace("_", "-")
        self.objects: dict[str, tuple[bytes, ObjectMetadata]] = {}
        self.deleted: list[str] = []

    def _reference(self, key: str) -> ObjectReference:
        return ObjectReference(self.provider, self.namespace, key)

    def _key(self, value: ObjectReference | str) -> str:
        reference = coerce_reference(value)
        if reference.provider != self.provider or reference.namespace != self.namespace:
            raise StorageInvalidReference("Referencia do fake storage invalida.")
        return reference.key

    def save(
        self,
        data: bytes,
        content_type: str,
        *,
        key: str | None = None,
        metadata: Mapping[str, str] | None = None,
        sha256: str | None = None,
    ) -> StoredObject:
        self.policy.validate(data, content_type)
        digest = validate_sha256(sha256) or sha256_hex(data)
        key = key or generate_object_key(self.scope, content_type)
        validate_object_key(key)
        if key in self.objects:
            raise StorageConflictError("O objeto ja existe no fake storage.")
        object_metadata = ObjectMetadata(
            size=len(data),
            content_type=content_type,
            etag=None,
            sha256=digest,
            custom=dict(metadata or {}),
        )
        self.objects[key] = (bytes(data), object_metadata)
        reference = self._reference(key)
        public_url = self.get_public_url(reference) if self.visibility == ObjectVisibility.PUBLIC else None
        return StoredObject(reference, object_metadata, public_url)

    def read(self, reference: ObjectReference | str) -> bytes:
        key = self._key(reference)
        try:
            return self.objects[key][0]
        except KeyError:
            raise StorageNotFound("Objeto nao encontrado no fake storage.") from None

    def stat(self, reference: ObjectReference | str) -> ObjectMetadata:
        key = self._key(reference)
        try:
            return self.objects[key][1]
        except KeyError:
            raise StorageNotFound("Objeto nao encontrado no fake storage.") from None

    def delete(self, reference: ObjectReference | str) -> None:
        key = self._key(reference)
        self.objects.pop(key, None)
        self.deleted.append(key)

    def get_public_url(self, reference: ObjectReference | str) -> str:
        if self.visibility != ObjectVisibility.PUBLIC:
            raise StorageOperationNotSupported("O fake storage deste escopo e privado.")
        key = self._key(reference)
        return f"https://storage.example.invalid/{self.namespace}/{key}"

    def presign_get(self, reference: ObjectReference | str, *, expires_seconds: int = 300) -> PresignedRequest:
        self._validate_expiration(expires_seconds)
        key = self._key(reference)
        if key not in self.objects:
            raise StorageNotFound("Objeto nao encontrado no fake storage.")
        now = datetime.now(timezone.utc)
        return PresignedRequest(
            self._reference(key),
            f"https://storage.example.invalid/signed/get/{self.namespace}/{key}?expires={expires_seconds}",
            "GET",
            now + timedelta(seconds=expires_seconds),
        )

    def presign_put(
        self,
        content_type: str,
        expected_size: int,
        *,
        key: str | None = None,
        expires_seconds: int = 300,
        sha256: str | None = None,
    ) -> PresignedRequest:
        self._validate_expiration(expires_seconds)
        self.policy.validate_size_and_type(content_type, expected_size)
        validate_sha256(sha256)
        key = key or generate_object_key(self.scope, content_type)
        validate_object_key(key)
        if key in self.objects:
            raise StorageConflictError("O objeto ja existe no fake storage.")
        now = datetime.now(timezone.utc)
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(expected_size),
            "If-None-Match": "*",
        }
        return PresignedRequest(
            self._reference(key),
            f"https://storage.example.invalid/signed/put/{self.namespace}/{key}?expires={expires_seconds}",
            "PUT",
            now + timedelta(seconds=expires_seconds),
            headers,
        )

    @staticmethod
    def _validate_expiration(expires_seconds: int) -> None:
        if not 1 <= expires_seconds <= 900:
            raise StorageConfigurationError("Expiracao da URL assinada invalida.")
