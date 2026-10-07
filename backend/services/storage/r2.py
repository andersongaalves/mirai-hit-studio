"""Private Cloudflare R2 adapter using its S3-compatible HTTP API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
from typing import Mapping
from urllib.parse import quote, urlsplit

import httpx

from .contracts import (
    ObjectMetadata,
    ObjectReference,
    ObjectVisibility,
    PresignedRequest,
    StorageAdapter,
    StorageConfigurationError,
    StorageConflictError,
    StorageDeleteError,
    StorageInvalidReference,
    StorageNotFound,
    StorageScope,
    StorageUnavailable,
    StorageUploadError,
    StoredObject,
    coerce_reference,
    validate_object_key,
)
from .keys import generate_object_key
from .policies import DEFAULT_POLICIES, StoragePolicy, sha256_hex, validate_sha256


_ACCOUNT_ID = re.compile(r"[a-f0-9]{32}")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
_METADATA_KEY = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")


class R2Storage(StorageAdapter):
    provider = "r2"
    visibility = ObjectVisibility.PRIVATE

    def __init__(
        self,
        *,
        scope: StorageScope,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        endpoint: str | None = None,
        region: str = "auto",
        policy: StoragePolicy | None = None,
        max_presign_seconds: int = 900,
        transport: httpx.BaseTransport | None = None,
        now=None,
    ) -> None:
        if scope not in {StorageScope.PRODUCTION_TEMP, StorageScope.PRODUCTION_FINAL}:
            raise StorageConfigurationError("Escopo invalido para R2.")
        if not _ACCOUNT_ID.fullmatch(account_id or ""):
            raise StorageConfigurationError("R2_ACCOUNT_ID invalido.")
        if not access_key_id or not secret_access_key:
            raise StorageConfigurationError("Credenciais server-side do R2 ausentes.")
        if not _BUCKET.fullmatch(bucket or ""):
            raise StorageConfigurationError("Bucket do R2 invalido.")
        endpoint = (endpoint or f"https://{account_id}.r2.cloudflarestorage.com").rstrip("/")
        parsed = urlsplit(endpoint)
        expected_host = f"{account_id}.r2.cloudflarestorage.com"
        if (
            parsed.scheme != "https"
            or parsed.hostname != expected_host
            or parsed.username
            or parsed.password
            or parsed.port is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise StorageConfigurationError("R2_ENDPOINT deve apontar para a conta configurada.")
        if not region or not 1 <= max_presign_seconds <= 3600:
            raise StorageConfigurationError("Configuracao de assinatura do R2 invalida.")
        self.scope = scope
        self.account_id = account_id
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self.bucket = bucket
        self.endpoint = endpoint
        self.region = region
        self.policy = policy or DEFAULT_POLICIES[scope]
        self.max_presign_seconds = max_presign_seconds
        self._transport = transport
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _reference(self, key: str) -> ObjectReference:
        return ObjectReference(self.provider, self.bucket, key)

    def _validated_reference(self, value: ObjectReference | str) -> ObjectReference:
        reference = coerce_reference(value)
        if reference.provider != self.provider or reference.namespace != self.bucket:
            raise StorageInvalidReference("Referencia do R2 invalida.")
        return reference

    def _path(self, key: str) -> str:
        validate_object_key(key)
        return "/" + quote(self.bucket, safe="-_.~") + "/" + quote(key, safe="/-_.~")

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _normalize_header(value: str) -> str:
        return " ".join(str(value).strip().split())

    @staticmethod
    def _encode_query(parameters: Mapping[str, str | int]) -> str:
        return "&".join(
            f"{quote(str(key), safe='-_.~')}={quote(str(value), safe='-_.~')}"
            for key, value in sorted(parameters.items())
        )

    def _signing_key(self, date_stamp: str) -> bytes:
        date_key = hmac.new(("AWS4" + self._secret_access_key).encode(), date_stamp.encode(), hashlib.sha256).digest()
        region_key = hmac.new(date_key, self.region.encode(), hashlib.sha256).digest()
        service_key = hmac.new(region_key, b"s3", hashlib.sha256).digest()
        return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()

    def _authorization_headers(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload_hash: str,
        at: datetime,
    ) -> dict[str, str]:
        amz_date = at.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = at.strftime("%Y%m%d")
        signed = {key.lower(): self._normalize_header(value) for key, value in headers.items()}
        signed.update({
            "host": f"{self.account_id}.r2.cloudflarestorage.com",
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        })
        signed_names = ";".join(sorted(signed))
        canonical_headers = "".join(f"{key}:{signed[key]}\n" for key in sorted(signed))
        canonical_request = "\n".join([
            method,
            path,
            "",
            canonical_headers,
            signed_names,
            payload_hash,
        ])
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            self._hash(canonical_request.encode()),
        ])
        signature = hmac.new(self._signing_key(date_stamp), string_to_sign.encode(), hashlib.sha256).hexdigest()
        result = {key: value for key, value in headers.items()}
        result.update({
            "Host": signed["host"],
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            "Authorization": (
                f"AWS4-HMAC-SHA256 Credential={self._access_key_id}/{scope}, "
                f"SignedHeaders={signed_names}, Signature={signature}"
            ),
        })
        return result

    def _request(self, method: str, key: str, *, data: bytes = b"", headers=None) -> httpx.Response:
        path = self._path(key)
        payload_hash = self._hash(data)
        signed_headers = self._authorization_headers(
            method,
            path,
            dict(headers or {}),
            payload_hash,
            self._now(),
        )
        try:
            with httpx.Client(timeout=30, follow_redirects=False, transport=self._transport) as client:
                return client.request(method, self.endpoint + path, content=data, headers=signed_headers)
        except httpx.HTTPError:
            raise StorageUnavailable("R2 indisponivel.") from None

    @staticmethod
    def _custom_headers(metadata: Mapping[str, str] | None) -> dict[str, str]:
        headers = {}
        for key, value in (metadata or {}).items():
            normalized_key = key.strip().lower()
            normalized_value = str(value)
            if (
                normalized_key == "sha256"
                or not _METADATA_KEY.fullmatch(normalized_key)
                or "\r" in normalized_value
                or "\n" in normalized_value
            ):
                raise StorageUploadError("Metadata de objeto invalida.")
            headers[f"x-amz-meta-{normalized_key}"] = normalized_value[:1024]
        return headers

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
        headers = {
            "Content-Type": content_type,
            "If-None-Match": "*",
            "x-amz-meta-sha256": digest,
            **self._custom_headers(metadata),
        }
        response = self._request("PUT", key, data=data, headers=headers)
        if response.status_code in {409, 412}:
            raise StorageConflictError("O objeto ja existe no R2.")
        if response.status_code not in {200, 201}:
            raise StorageUploadError("Nao foi possivel armazenar o arquivo no R2.")
        reference = self._reference(key)
        object_metadata = ObjectMetadata(
            size=len(data),
            content_type=content_type,
            etag=response.headers.get("etag", "").strip('"') or None,
            sha256=digest,
            custom=dict(metadata or {}),
        )
        return StoredObject(reference, object_metadata)

    def read(self, reference: ObjectReference | str) -> bytes:
        reference = self._validated_reference(reference)
        response = self._request("GET", reference.key)
        if response.status_code == 404:
            raise StorageNotFound("Objeto nao encontrado no R2.")
        if response.status_code != 200:
            raise StorageUnavailable("Nao foi possivel ler o objeto no R2.")
        return response.content

    def stat(self, reference: ObjectReference | str) -> ObjectMetadata:
        reference = self._validated_reference(reference)
        response = self._request("HEAD", reference.key)
        if response.status_code == 404:
            raise StorageNotFound("Objeto nao encontrado no R2.")
        if response.status_code != 200:
            raise StorageUnavailable("Nao foi possivel consultar o objeto no R2.")
        try:
            size = int(response.headers["content-length"])
        except (KeyError, ValueError):
            raise StorageUnavailable("Metadados invalidos recebidos do R2.") from None
        custom = {
            key.removeprefix("x-amz-meta-"): value
            for key, value in response.headers.items()
            if key.startswith("x-amz-meta-") and key != "x-amz-meta-sha256"
        }
        return ObjectMetadata(
            size=size,
            content_type=response.headers.get("content-type", "application/octet-stream"),
            etag=response.headers.get("etag", "").strip('"') or None,
            sha256=response.headers.get("x-amz-meta-sha256"),
            custom=custom,
        )

    def delete(self, reference: ObjectReference | str) -> None:
        reference = self._validated_reference(reference)
        response = self._request("DELETE", reference.key)
        if response.status_code not in {200, 204, 404}:
            raise StorageDeleteError("Nao foi possivel remover o objeto do R2.")

    def _validate_expiration(self, expires_seconds: int) -> None:
        if not 1 <= expires_seconds <= self.max_presign_seconds:
            raise StorageConfigurationError("Expiracao da URL assinada invalida.")

    def _presign(
        self,
        method: str,
        key: str,
        *,
        expires_seconds: int,
        required_headers: Mapping[str, str] | None = None,
    ) -> PresignedRequest:
        self._validate_expiration(expires_seconds)
        path = self._path(key)
        at = self._now()
        amz_date = at.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = at.strftime("%Y%m%d")
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        headers = {key.lower(): self._normalize_header(value) for key, value in (required_headers or {}).items()}
        headers["host"] = f"{self.account_id}.r2.cloudflarestorage.com"
        signed_names = ";".join(sorted(headers))
        parameters = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self._access_key_id}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": expires_seconds,
            "X-Amz-SignedHeaders": signed_names,
        }
        canonical_query = self._encode_query(parameters)
        canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
        canonical_request = "\n".join([
            method,
            path,
            canonical_query,
            canonical_headers,
            signed_names,
            "UNSIGNED-PAYLOAD",
        ])
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            self._hash(canonical_request.encode()),
        ])
        parameters["X-Amz-Signature"] = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode(),
            hashlib.sha256,
        ).hexdigest()
        returned_headers = {
            name: value for name, value in (required_headers or {}).items()
        }
        return PresignedRequest(
            reference=self._reference(key),
            url=self.endpoint + path + "?" + self._encode_query(parameters),
            method=method,
            expires_at=at + timedelta(seconds=expires_seconds),
            headers=returned_headers,
        )

    def presign_get(self, reference: ObjectReference | str, *, expires_seconds: int = 300) -> PresignedRequest:
        reference = self._validated_reference(reference)
        return self._presign("GET", reference.key, expires_seconds=expires_seconds)

    def presign_put(
        self,
        content_type: str,
        expected_size: int,
        *,
        key: str | None = None,
        expires_seconds: int = 300,
        sha256: str | None = None,
    ) -> PresignedRequest:
        self.policy.validate_size_and_type(content_type, expected_size)
        digest = validate_sha256(sha256)
        key = key or generate_object_key(self.scope, content_type)
        validate_object_key(key)
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(expected_size),
            "If-None-Match": "*",
        }
        if digest:
            headers["x-amz-meta-sha256"] = digest
        return self._presign(
            "PUT",
            key,
            expires_seconds=expires_seconds,
            required_headers=headers,
        )
