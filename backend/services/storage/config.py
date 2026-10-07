"""Explicit server-side configuration for provider resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Mapping

from .contracts import StorageConfigurationError, StorageScope


DEFAULT_BACKENDS: Mapping[StorageScope, str] = {
    StorageScope.PUBLIC_IMAGE: "cloudinary",
    StorageScope.PORTFOLIO_AUDIO: "supabase",
    StorageScope.PRODUCTION_TEMP: "r2",
    StorageScope.PRODUCTION_FINAL: "r2",
    StorageScope.PROPOSAL_DOCUMENT: "legacy",
}

_BACKEND_ENV = {
    StorageScope.PUBLIC_IMAGE: "PUBLIC_IMAGE_STORAGE_BACKEND",
    StorageScope.PORTFOLIO_AUDIO: "PORTFOLIO_AUDIO_STORAGE_BACKEND",
    StorageScope.PRODUCTION_TEMP: "PRODUCTION_TEMP_STORAGE_BACKEND",
    StorageScope.PRODUCTION_FINAL: "PRODUCTION_FINAL_STORAGE_BACKEND",
    StorageScope.PROPOSAL_DOCUMENT: "PROPOSAL_DOCUMENT_STORAGE_BACKEND",
}


@dataclass(frozen=True, slots=True)
class StorageSettings:
    backends: Mapping[StorageScope, str] = field(default_factory=lambda: dict(DEFAULT_BACKENDS))
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_temp_bucket: str = ""
    r2_final_bucket: str = ""
    r2_endpoint: str = ""
    r2_region: str = "auto"
    r2_presign_max_seconds: int = 900

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "StorageSettings":
        env = environ if environ is not None else os.environ
        backends = {
            scope: env.get(variable, DEFAULT_BACKENDS[scope]).strip().lower()
            for scope, variable in _BACKEND_ENV.items()
        }
        try:
            max_seconds = int(env.get("R2_PRESIGN_MAX_SECONDS", "900"))
        except ValueError:
            raise StorageConfigurationError("R2_PRESIGN_MAX_SECONDS invalido.") from None
        return cls(
            backends=backends,
            cloudinary_cloud_name=env.get("CLOUDINARY_CLOUD_NAME", "").strip(),
            cloudinary_api_key=env.get("CLOUDINARY_API_KEY", "").strip(),
            cloudinary_api_secret=env.get("CLOUDINARY_API_SECRET", ""),
            r2_account_id=env.get("R2_ACCOUNT_ID", "").strip().lower(),
            r2_access_key_id=env.get("R2_ACCESS_KEY_ID", "").strip(),
            r2_secret_access_key=env.get("R2_SECRET_ACCESS_KEY", ""),
            r2_temp_bucket=env.get("R2_TEMP_BUCKET", "").strip(),
            r2_final_bucket=env.get("R2_FINAL_BUCKET", "").strip(),
            r2_endpoint=env.get("R2_ENDPOINT", "").strip(),
            r2_region=env.get("R2_REGION", "auto").strip(),
            r2_presign_max_seconds=max_seconds,
        )
