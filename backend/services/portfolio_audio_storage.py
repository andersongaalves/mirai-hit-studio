"""Server-only public portfolio audio storage."""

import logging
import os
import re
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

DEFAULT_MAX_BYTES = 30 * 1024 * 1024
ALLOWED_MIME_TYPES = {"audio/mpeg", "audio/mp3"}
OBJECT_KEY = re.compile(r"projects/(?P<project_id>\d+)/(?P<slot>before|after)-[a-f0-9]{32}\.mp3")


class PortfolioAudioStorageError(Exception):
    pass


def max_audio_bytes() -> int:
    raw = os.environ.get("PORTFOLIO_AUDIO_MAX_BYTES", str(DEFAULT_MAX_BYTES))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_MAX_BYTES
    return max(1, value)


def validate_mp3(data: bytes, content_type: str | None) -> None:
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPAudioValidationError("Envie um arquivo MP3 valido.")
    if not data or not (data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)):
        raise HTTPAudioValidationError("O conteudo enviado nao e um MP3 valido.")


class HTTPAudioValidationError(ValueError):
    pass


class SupabasePortfolioAudioStorage:
    def __init__(self, *, base_url=None, service_key=None, bucket=None, transport=None):
        self.project_url = (base_url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.service_key = service_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.bucket = bucket or os.environ.get("PORTFOLIO_AUDIO_STORAGE_BUCKET", "portfolio-audio")
        self.transport = transport
        parsed = urlparse(self.project_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise PortfolioAudioStorageError("Configure o Storage de audio do Portfolio.")
        if not self.service_key:
            raise PortfolioAudioStorageError("Configure o Storage de audio do Portfolio.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,99}", self.bucket):
            raise PortfolioAudioStorageError("Bucket de audio invalido.")

    @property
    def _base_url(self):
        return f"{self.project_url}/storage/v1/"

    def _request(self, method, path, **kwargs):
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }
        headers.update(kwargs.pop("headers", {}))
        try:
            with httpx.Client(
                base_url=self._base_url,
                headers=headers,
                timeout=30,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                return client.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise PortfolioAudioStorageError("Storage de audio indisponivel.") from None

    def _ensure_public_bucket(self):
        bucket_path = "bucket/" + quote(self.bucket, safe="")
        response = self._request("GET", bucket_path)
        missing = response.status_code == 404
        if response.status_code == 400:
            try:
                error = response.json()
            except ValueError:
                error = {}
            missing = str(error.get("statusCode")) == "404"
        if missing:
            response = self._request(
                "POST",
                "bucket",
                json={
                    "id": self.bucket,
                    "name": self.bucket,
                    "public": True,
                    "file_size_limit": max_audio_bytes(),
                    "allowed_mime_types": ["audio/mpeg"],
                },
            )
            if response.status_code not in (200, 201, 409):
                raise PortfolioAudioStorageError("Nao foi possivel preparar o bucket de audio.")
            response = self._request("GET", bucket_path)
        if response.status_code != 200:
            raise PortfolioAudioStorageError("Bucket de audio indisponivel.")
        try:
            is_public = response.json().get("public") is True
        except ValueError:
            is_public = False
        if not is_public:
            raise PortfolioAudioStorageError("O bucket de audio deve permitir leitura publica.")

    def save(self, data: bytes, project_id: int, slot: str) -> str:
        if slot not in ("before", "after"):
            raise PortfolioAudioStorageError("Slot de audio invalido.")
        self._ensure_public_bucket()
        key = f"projects/{project_id}/{slot}-{uuid4().hex}.mp3"
        response = self._request(
            "POST",
            "object/" + quote(self.bucket, safe="") + "/" + quote(key, safe="/"),
            content=data,
            headers={"Content-Type": "audio/mpeg", "x-upsert": "false"},
        )
        if response.status_code not in (200, 201):
            logger.warning("portfolio_audio_storage_failed operation=upload project_id=%s slot=%s status=%s", project_id, slot, response.status_code)
            raise PortfolioAudioStorageError("Nao foi possivel armazenar o audio.")
        return key

    def delete(self, key: str) -> None:
        match = OBJECT_KEY.fullmatch(key or "")
        if not match:
            raise PortfolioAudioStorageError("Referencia de audio invalida.")
        response = self._request(
            "DELETE",
            "object/" + quote(self.bucket, safe="") + "/" + quote(key, safe="/"),
        )
        if response.status_code not in (200, 204, 404):
            logger.warning(
                "portfolio_audio_storage_failed operation=delete project_id=%s slot=%s status=%s",
                match.group("project_id"),
                match.group("slot"),
                response.status_code,
            )
            raise PortfolioAudioStorageError("Nao foi possivel remover o audio anterior.")

    def public_url(self, key: str) -> str:
        if not OBJECT_KEY.fullmatch(key or ""):
            raise PortfolioAudioStorageError("Referencia de audio invalida.")
        return f"{self.project_url}/storage/v1/object/public/{quote(self.bucket, safe='')}/{quote(key, safe='/')}"


def new_portfolio_audio_storage():
    return SupabasePortfolioAudioStorage()
