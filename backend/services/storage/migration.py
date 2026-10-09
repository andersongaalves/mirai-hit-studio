"""Idempotent copy-and-verify primitives for legacy Storage migration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .contracts import (
    ObjectReference,
    StorageAdapter,
    StorageConflictError,
    StorageError,
    StorageScope,
)


class StorageMigrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MigrationCandidate:
    record_id: int
    scope: StorageScope
    source: ObjectReference
    content_type: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class MigrationResult:
    destination: ObjectReference
    copied: bool
    verified: bool


def destination_key(candidate: MigrationCandidate) -> str:
    prefix = candidate.scope.value.replace("_", "-")
    return f"{prefix}/migrations/{candidate.record_id}-{candidate.sha256}"


def _reference_for_key(adapter: StorageAdapter, key: str) -> ObjectReference:
    namespace = getattr(adapter, "bucket", None) or getattr(adapter, "namespace", None)
    if not namespace:
        raise StorageMigrationError("destination_namespace_unavailable")
    return ObjectReference(adapter.provider, namespace, key)


def _verify(data: bytes, candidate: MigrationCandidate) -> None:
    if len(data) != candidate.size:
        raise StorageMigrationError("storage_migration_size_mismatch")
    if hashlib.sha256(data).hexdigest() != candidate.sha256:
        raise StorageMigrationError("storage_migration_sha256_mismatch")


def migrate_candidate(
    candidate: MigrationCandidate,
    *,
    source: StorageAdapter,
    destination: StorageAdapter,
) -> MigrationResult:
    if source.scope != candidate.scope or destination.scope != candidate.scope:
        raise StorageMigrationError("storage_migration_scope_mismatch")

    try:
        data = source.read(candidate.source)
        _verify(data, candidate)
        key = destination_key(candidate)
        copied = True
        try:
            stored = destination.save(
                data,
                candidate.content_type,
                key=key,
                metadata={"source_provider": candidate.source.provider},
                sha256=candidate.sha256,
            )
            reference = stored.reference
        except StorageConflictError:
            copied = False
            reference = _reference_for_key(destination, key)
        _verify(destination.read(reference), candidate)
        metadata = destination.stat(reference)
        if metadata.size != candidate.size or metadata.sha256 != candidate.sha256:
            raise StorageMigrationError("storage_migration_metadata_mismatch")
        return MigrationResult(reference, copied, True)
    except StorageMigrationError:
        raise
    except StorageError as error:
        raise StorageMigrationError("storage_migration_provider_failure") from error
