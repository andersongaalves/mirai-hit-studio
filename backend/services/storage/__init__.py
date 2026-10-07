"""Multi-provider storage core (not wired into existing product flows yet)."""

from .contracts import (
    ObjectMetadata,
    ObjectReference,
    ObjectVisibility,
    PresignedRequest,
    StorageAdapter,
    StorageConfigurationError,
    StorageConflictError,
    StorageDeleteError,
    StorageError,
    StorageInvalidReference,
    StorageNotFound,
    StorageOperationNotSupported,
    StorageScope,
    StorageUnavailable,
    StorageUploadError,
    StorageValidationError,
    StoredObject,
)
from .registry import StorageRegistry, storage_for

__all__ = [
    "ObjectMetadata",
    "ObjectReference",
    "ObjectVisibility",
    "PresignedRequest",
    "StorageAdapter",
    "StorageConfigurationError",
    "StorageConflictError",
    "StorageDeleteError",
    "StorageError",
    "StorageInvalidReference",
    "StorageNotFound",
    "StorageOperationNotSupported",
    "StorageRegistry",
    "StorageScope",
    "StorageUnavailable",
    "StorageUploadError",
    "StorageValidationError",
    "StoredObject",
    "storage_for",
]
