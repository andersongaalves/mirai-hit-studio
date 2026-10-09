"""Private, server-only storage for production files."""

import os
import re
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx

MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/zip",
    "audio/flac",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "video/mp4",
}
OBJECT_KEY = re.compile(r"arquivos/[a-f0-9]{32}/[a-f0-9]{32}")


class ProducaoArquivoStorageError(Exception):
    pass


class SupabaseProducaoArquivoStorage:
    """Immutable object adapter. Authorization is enforced before this layer."""

    def __init__(self, *, base_url=None, service_key=None, bucket=None, transport=None):
        self.project_url = (base_url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.service_key = service_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.bucket = bucket or os.environ.get(
            "PRODUCAO_STORAGE_BUCKET",
            "producao-arquivos",
        )
        self.transport = transport
        parsed = urlparse(self.project_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ProducaoArquivoStorageError("Configure SUPABASE_URL com uma URL HTTPS valida.")
        if not self.service_key:
            raise ProducaoArquivoStorageError("Configure a credencial server-only do Storage.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,99}", self.bucket):
            raise ProducaoArquivoStorageError("Nome do bucket de producao invalido.")

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
                timeout=20,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                return client.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise ProducaoArquivoStorageError("Storage de producao indisponivel.") from None

    def ensure_private_bucket(self):
        bucket_path = "bucket/" + quote(self.bucket, safe="")
        response = self._request("GET", bucket_path)
        missing_bucket = response.status_code == 404
        if response.status_code == 400:
            try:
                missing_bucket = response.json().get("code") == "NoSuchBucket"
            except ValueError:
                missing_bucket = False
        if missing_bucket:
            response = self._request(
                "POST",
                "bucket",
                json={
                    "id": self.bucket,
                    "name": self.bucket,
                    "public": False,
                    "file_size_limit": MAX_FILE_SIZE,
                    "allowed_mime_types": sorted(ALLOWED_MIME_TYPES),
                },
            )
            if response.status_code not in (200, 201, 409):
                raise ProducaoArquivoStorageError("Nao foi possivel preparar o bucket privado.")
            response = self._request("GET", bucket_path)
        if response.status_code != 200:
            raise ProducaoArquivoStorageError("Bucket privado de producao indisponivel.")
        try:
            metadata = response.json()
        except ValueError:
            raise ProducaoArquivoStorageError("Resposta invalida do Storage.") from None
        if metadata.get("public") is not False:
            raise ProducaoArquivoStorageError("O bucket de producao deve ser privado.")

    @staticmethod
    def validate_key(key):
        if not OBJECT_KEY.fullmatch(key or ""):
            raise ProducaoArquivoStorageError("Referencia de arquivo invalida.")
        return key

    def save(self, data: bytes, mime_type: str):
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ProducaoArquivoStorageError("Tipo de arquivo nao permitido.")
        if not data or len(data) > MAX_FILE_SIZE:
            raise ProducaoArquivoStorageError("Tamanho de arquivo nao permitido.")
        self.ensure_private_bucket()
        key = f"arquivos/{uuid4().hex}/{uuid4().hex}"
        path = "object/" + quote(self.bucket, safe="") + "/" + quote(key, safe="/")
        response = self._request(
            "POST",
            path,
            content=data,
            headers={"Content-Type": mime_type, "x-upsert": "false"},
        )
        if response.status_code not in (200, 201):
            raise ProducaoArquivoStorageError("Nao foi possivel armazenar o arquivo.")
        return key

    def read(self, key):
        key = self.validate_key(key)
        path = (
            "object/authenticated/"
            + quote(self.bucket, safe="")
            + "/"
            + quote(key, safe="/")
        )
        response = self._request("GET", path)
        if response.status_code != 200:
            raise ProducaoArquivoStorageError("Arquivo indisponivel no Storage.")
        return response.content

    def delete(self, key):
        key = self.validate_key(key)
        path = "object/" + quote(self.bucket, safe="")
        response = self._request("DELETE", path, json={"prefixes": [key]})
        if response.status_code not in (200, 204):
            raise ProducaoArquivoStorageError("Nao foi possivel compensar o upload.")


FILE_TYPE_SCOPE = {
    "material": "production_temp",
    "referencia": "production_temp",
    "previa": "production_temp",
    "entrega": "production_final",
    "comprovante": "production_final",
}


class ProductionFileStorage:
    """Provider-neutral facade with lazy compatibility for legacy Supabase keys."""

    def __init__(self, scope, *, registry=None, legacy_factory=None):
        from services.storage.contracts import StorageError, StorageScope

        self.scope = StorageScope(scope)
        if self.scope not in {
            StorageScope.PRODUCTION_TEMP,
            StorageScope.PRODUCTION_FINAL,
        }:
            raise ProducaoArquivoStorageError("Escopo de arquivo de Producao invalido.")
        try:
            if registry is None:
                from services.storage.config import StorageSettings
                from services.storage.registry import StorageRegistry

                registry = StorageRegistry(StorageSettings.from_env())
            self.registry = registry
        except StorageError as exc:
            raise ProducaoArquivoStorageError(str(exc)) from None
        self._legacy_factory = legacy_factory
        self._legacy = None

    def _legacy_adapter(self):
        from services.storage.contracts import StorageError

        if self._legacy is None:
            try:
                if self._legacy_factory is None:
                    from services.storage.legacy import SupabaseProductionAdapter

                    self._legacy = SupabaseProductionAdapter(self.scope)
                else:
                    self._legacy = self._legacy_factory()
            except StorageError as exc:
                raise ProducaoArquivoStorageError(str(exc)) from None
        return self._legacy

    def _adapter(self):
        from services.storage.contracts import StorageError

        try:
            return self.registry.storage_for(self.scope)
        except StorageError as exc:
            raise ProducaoArquivoStorageError(str(exc)) from None

    def _resolve(self, value):
        from services.storage.contracts import ObjectReference, StorageError, StorageInvalidReference

        if "://" not in value:
            legacy = self._legacy_adapter()
            return legacy, ObjectReference("supabase", legacy.bucket, value)
        try:
            reference = ObjectReference.parse(value)
        except StorageInvalidReference as exc:
            raise ProducaoArquivoStorageError(str(exc)) from None
        try:
            adapter = self.registry.storage_for_reference(self.scope, reference)
        except StorageError as exc:
            raise ProducaoArquivoStorageError(str(exc)) from None
        return adapter, reference

    def save(self, data: bytes, mime_type: str):
        from services.storage.contracts import StorageError

        try:
            stored = self._adapter().save(data, mime_type)
        except StorageError as exc:
            raise ProducaoArquivoStorageError(str(exc)) from None
        reference = str(stored.reference)
        if len(reference) > 180:
            try:
                self._adapter().delete(stored.reference)
            except StorageError:
                pass
            raise ProducaoArquivoStorageError("Referencia de arquivo muito longa.")
        return reference

    def read(self, value):
        from services.storage.contracts import StorageError

        adapter, reference = self._resolve(value)
        try:
            return adapter.read(reference)
        except StorageError as exc:
            raise ProducaoArquivoStorageError(str(exc)) from None

    def delete(self, value):
        from services.storage.contracts import StorageError

        adapter, reference = self._resolve(value)
        try:
            adapter.delete(reference)
        except StorageError as exc:
            raise ProducaoArquivoStorageError(str(exc)) from None


def new_production_file_storage(file_type):
    try:
        scope = FILE_TYPE_SCOPE[file_type]
    except KeyError:
        raise ProducaoArquivoStorageError("Tipo de arquivo de Producao invalido.") from None
    return ProductionFileStorage(scope)
