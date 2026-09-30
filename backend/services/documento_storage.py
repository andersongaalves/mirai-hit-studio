"""Private document storage adapters selected explicitly by configuration."""
import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx


class DocumentoIndisponivel(Exception):
    pass


LOCAL_KEY = re.compile(r"proposta-\d+-v\d+-[a-f0-9]{32}\.pdf")
SUPABASE_REFERENCE = re.compile(
    r"supabase://(?P<bucket>[a-z0-9][a-z0-9._-]{1,99})/"
    r"(?P<key>propostas/\d+/v\d+/[a-f0-9]{32}\.pdf)"
)


class LocalDocumentoStorage:
    def __init__(self):
        directory = os.environ.get("PROPOSTA_PDF_DIR", "")
        if not directory or not Path(directory).is_absolute():
            raise DocumentoIndisponivel("Configure PROPOSTA_PDF_DIR com um diretorio absoluto persistente.")
        self.directory = Path(directory).resolve()

    def _path(self, key):
        if not LOCAL_KEY.fullmatch(key or ""):
            raise DocumentoIndisponivel("Referencia de documento invalida; gere o PDF novamente.")
        path = (self.directory / key).resolve()
        if path.parent != self.directory:
            raise DocumentoIndisponivel("Referencia de documento invalida.")
        return path

    def salvar(self, data, proposta_id, versao):
        key = f"proposta-{proposta_id}-v{versao}-{uuid4().hex}.pdf"
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self._path(key)
            temporary = path.with_suffix(".tmp")
            with temporary.open("xb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(path)
        except OSError:
            raise DocumentoIndisponivel("Nao foi possivel armazenar o PDF.") from None
        return key

    def ler(self, key):
        try:
            return self._path(key).read_bytes()
        except OSError:
            raise DocumentoIndisponivel("PDF indisponivel no armazenamento; gere novamente.") from None


class SupabaseDocumentoStorage:
    """Server-only Supabase Storage adapter; object replacement is never allowed."""

    def __init__(self, *, base_url=None, service_key=None, bucket=None, transport=None):
        self.project_url = (base_url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.service_key = service_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.bucket = bucket or os.environ.get("SUPABASE_STORAGE_BUCKET", "propostas-pdf")
        self.transport = transport
        parsed = urlparse(self.project_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise DocumentoIndisponivel("Configure SUPABASE_URL com uma URL HTTPS valida.")
        if not self.service_key:
            raise DocumentoIndisponivel("Configure a credencial server-only do Supabase Storage.")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,99}", self.bucket):
            raise DocumentoIndisponivel("Nome do bucket de documentos invalido.")

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
                timeout=10,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                return client.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise DocumentoIndisponivel("Supabase Storage indisponivel.") from None

    def _bucket_privado(self):
        bucket_path = "bucket/" + quote(self.bucket, safe="")
        response = self._request("GET", bucket_path)
        if response.status_code == 404:
            created = self._request("POST", "bucket", json={
                "id": self.bucket,
                "name": self.bucket,
                "public": False,
                "file_size_limit": 20 * 1024 * 1024,
                "allowed_mime_types": ["application/pdf"],
            })
            if created.status_code not in (200, 201, 409):
                raise DocumentoIndisponivel("Nao foi possivel preparar o bucket privado de documentos.")
            response = self._request("GET", bucket_path)
        if response.status_code != 200:
            raise DocumentoIndisponivel("Bucket privado de documentos indisponivel.")
        try:
            metadata = response.json()
        except ValueError:
            raise DocumentoIndisponivel("Resposta invalida do Supabase Storage.") from None
        if metadata.get("public") is not False:
            raise DocumentoIndisponivel("O bucket de documentos deve ser privado.")

    def _reference(self, key):
        return f"supabase://{self.bucket}/{key}"

    def _key(self, reference):
        match = SUPABASE_REFERENCE.fullmatch(reference or "")
        if not match or match.group("bucket") != self.bucket:
            raise DocumentoIndisponivel("Referencia de documento invalida.")
        return match.group("key")

    def salvar(self, data, proposta_id, versao):
        self._bucket_privado()
        key = f"propostas/{proposta_id}/v{versao}/{uuid4().hex}.pdf"
        path = "object/" + quote(self.bucket, safe="") + "/" + quote(key, safe="/")
        response = self._request(
            "POST",
            path,
            content=data,
            headers={"Content-Type": "application/pdf", "x-upsert": "false"},
        )
        if response.status_code not in (200, 201):
            raise DocumentoIndisponivel("Nao foi possivel armazenar o PDF de forma duravel.")
        return self._reference(key)

    def ler(self, reference):
        key = self._key(reference)
        path = (
            "object/authenticated/"
            + quote(self.bucket, safe="")
            + "/"
            + quote(key, safe="/")
        )
        response = self._request("GET", path)
        if response.status_code != 200:
            raise DocumentoIndisponivel("PDF indisponivel no armazenamento duravel.")
        return response.content


def novo_documento_storage():
    backend = os.environ.get("PROPOSTA_STORAGE_BACKEND", "local").strip().lower()
    if backend == "local":
        return LocalDocumentoStorage()
    if backend == "supabase":
        return SupabaseDocumentoStorage()
    raise DocumentoIndisponivel("Backend de armazenamento de documentos invalido.")


def storage_para_referencia(reference):
    if SUPABASE_REFERENCE.fullmatch(reference or ""):
        return SupabaseDocumentoStorage()
    return LocalDocumentoStorage()
