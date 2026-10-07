"""Opaque, immutable object-key generation."""

from __future__ import annotations

from uuid import uuid4

from .contracts import StorageScope, StorageValidationError, validate_object_key


_PREFIXES = {
    StorageScope.PUBLIC_IMAGE: "public-images",
    StorageScope.PORTFOLIO_AUDIO: "portfolio-audio",
    StorageScope.PRODUCTION_TEMP: "production-temp",
    StorageScope.PRODUCTION_FINAL: "production-final",
    StorageScope.PROPOSAL_DOCUMENT: "proposal-documents",
}

_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/flac": ".flac",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "video/mp4": ".mp4",
    "application/zip": ".zip",
    "application/pdf": ".pdf",
}


def generate_object_key(scope: StorageScope, content_type: str, *, group: str | None = None) -> str:
    try:
        extension = _EXTENSIONS[content_type]
    except KeyError:
        raise StorageValidationError("Tipo de arquivo nao permitido para a chave.") from None
    segments = [_PREFIXES[scope]]
    if group:
        # Group identifiers must already be opaque, not user filenames or free text.
        validate_object_key(group)
        if "/" in group:
            raise StorageValidationError("Grupo da chave invalido.")
        segments.append(group)
    segments.append(f"{uuid4().hex}{extension}")
    return "/".join(segments)
