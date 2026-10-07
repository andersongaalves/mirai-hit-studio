"""Cloudinary adapter for public images, using the signed HTTP API."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Mapping
from urllib.parse import quote

import httpx

from .contracts import (
    ObjectMetadata,
    ObjectReference,
    ObjectVisibility,
    StorageAdapter,
    StorageConfigurationError,
    StorageDeleteError,
    StorageInvalidReference,
    StorageScope,
    StorageUnavailable,
    StorageUploadError,
    StoredObject,
    coerce_reference,
    validate_object_key,
)
from .keys import generate_object_key
from .policies import DEFAULT_POLICIES, StoragePolicy, sha256_hex, validate_sha256


_CLOUD_NAME = re.compile(r"[A-Za-z0-9_-]{1,128}")


class CloudinaryImageStorage(StorageAdapter):
    provider = "cloudinary"
    scope = StorageScope.PUBLIC_IMAGE
    visibility = ObjectVisibility.PUBLIC

    def __init__(
        self,
        *,
        cloud_name: str,
        api_key: str,
        api_secret: str,
        policy: StoragePolicy | None = None,
        transport: httpx.BaseTransport | None = None,
        now=None,
    ) -> None:
        if not _CLOUD_NAME.fullmatch(cloud_name or "") or not api_key or not api_secret:
            raise StorageConfigurationError("Configuracao do Cloudinary incompleta.")
        self.cloud_name = cloud_name
        self._api_key = api_key
        self._api_secret = api_secret
        self.policy = policy or DEFAULT_POLICIES[self.scope]
        self._transport = transport
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _signature(self, parameters: Mapping[str, str | int]) -> str:
        payload = "&".join(f"{key}={value}" for key, value in sorted(parameters.items()))
        return hashlib.sha1((payload + self._api_secret).encode("utf-8")).hexdigest()

    def _request(self, action: str, *, data, files=None) -> httpx.Response:
        url = f"https://api.cloudinary.com/v1_1/{quote(self.cloud_name, safe='')}/image/{action}"
        try:
            with httpx.Client(timeout=30, follow_redirects=False, transport=self._transport) as client:
                return client.post(url, data=data, files=files)
        except httpx.HTTPError:
            raise StorageUnavailable("Cloudinary indisponivel.") from None

    def _reference(self, public_id: str) -> ObjectReference:
        return ObjectReference(self.provider, self.cloud_name, public_id)

    def _validated_reference(self, value: ObjectReference | str) -> ObjectReference:
        reference = coerce_reference(value)
        if reference.provider != self.provider or reference.namespace != self.cloud_name:
            raise StorageInvalidReference("Referencia do Cloudinary invalida.")
        return reference

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
        expected_sha256 = validate_sha256(sha256) or sha256_hex(data)
        public_id = key or generate_object_key(self.scope, content_type).rsplit(".", 1)[0]
        validate_object_key(public_id)
        timestamp = int(self._now().timestamp())
        signed = {
            "overwrite": "false",
            "public_id": public_id,
            "timestamp": timestamp,
            "type": "upload",
        }
        form = {**signed, "api_key": self._api_key, "signature": self._signature(signed)}
        response = self._request(
            "upload",
            data=form,
            files={"file": ("image", data, content_type)},
        )
        if response.status_code not in (200, 201):
            if response.status_code == 409:
                raise StorageUploadError("O objeto ja existe no Cloudinary.")
            raise StorageUploadError("Nao foi possivel armazenar a imagem.")
        try:
            payload = response.json()
            returned_id = payload["public_id"]
        except (ValueError, KeyError, TypeError):
            raise StorageUploadError("Resposta invalida do Cloudinary.") from None
        if returned_id != public_id:
            raise StorageUploadError("Resposta invalida do Cloudinary.")
        object_metadata = ObjectMetadata(
            size=int(payload.get("bytes", len(data))),
            content_type=content_type,
            etag=payload.get("etag"),
            sha256=expected_sha256,
            custom=dict(metadata or {}),
        )
        reference = self._reference(public_id)
        return StoredObject(reference, object_metadata, self.get_public_url(reference))

    def delete(self, reference: ObjectReference | str) -> None:
        reference = self._validated_reference(reference)
        timestamp = int(self._now().timestamp())
        signed = {
            "invalidate": "true",
            "public_id": reference.key,
            "timestamp": timestamp,
            "type": "upload",
        }
        form = {**signed, "api_key": self._api_key, "signature": self._signature(signed)}
        response = self._request("destroy", data=form)
        if response.status_code != 200:
            raise StorageDeleteError("Nao foi possivel remover a imagem.")
        try:
            result = response.json().get("result")
        except ValueError:
            raise StorageDeleteError("Resposta invalida do Cloudinary.") from None
        if result not in {"ok", "not found"}:
            raise StorageDeleteError("Nao foi possivel remover a imagem.")

    def get_public_url(self, reference: ObjectReference | str) -> str:
        reference = self._validated_reference(reference)
        encoded_key = "/".join(quote(segment, safe="") for segment in reference.key.split("/"))
        return f"https://res.cloudinary.com/{quote(self.cloud_name, safe='')}/image/upload/{encoded_key}"
