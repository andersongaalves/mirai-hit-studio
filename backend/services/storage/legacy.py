"""Compatibility wrappers around the storage implementations already in use."""

from __future__ import annotations

import base64
import binascii

from services.documento_storage import (
    DocumentoIndisponivel,
    novo_documento_storage,
    storage_para_referencia,
)
from services.portfolio_audio_storage import (
    PortfolioAudioStorageError,
    SupabasePortfolioAudioStorage,
)
from services.producao_arquivo_storage import (
    ProducaoArquivoStorageError,
    SupabaseProducaoArquivoStorage,
)

from .contracts import (
    ObjectMetadata,
    ObjectReference,
    ObjectVisibility,
    StorageAdapter,
    StorageConfigurationError,
    StorageDeleteError,
    StorageInvalidReference,
    StorageOperationNotSupported,
    StorageScope,
    StorageUnavailable,
    StorageUploadError,
    StoredObject,
    coerce_reference,
)
from .policies import DEFAULT_POLICIES, sha256_hex, validate_sha256


class SupabasePortfolioAudioAdapter(StorageAdapter):
    provider = "supabase"
    scope = StorageScope.PORTFOLIO_AUDIO
    visibility = ObjectVisibility.PUBLIC

    def __init__(self, storage: SupabasePortfolioAudioStorage | None = None) -> None:
        try:
            self.storage = storage or SupabasePortfolioAudioStorage()
        except PortfolioAudioStorageError as exc:
            raise StorageConfigurationError(str(exc)) from None
        self.bucket = self.storage.bucket

    def _reference(self, key: str) -> ObjectReference:
        return ObjectReference(self.provider, self.bucket, key)

    def _key(self, value: ObjectReference | str) -> str:
        reference = coerce_reference(value)
        if reference.provider != self.provider or reference.namespace != self.bucket:
            raise StorageInvalidReference("Referencia do audio legado invalida.")
        return reference.key

    def save(self, data, content_type, *, key=None, metadata=None, sha256=None) -> StoredObject:
        if key is not None:
            raise StorageOperationNotSupported("O adapter legado sempre gera uma chave imutavel.")
        DEFAULT_POLICIES[self.scope].validate(data, content_type)
        metadata = dict(metadata or {})
        try:
            project_id = int(metadata["project_id"])
            slot = metadata["slot"]
        except (KeyError, TypeError, ValueError):
            raise StorageUploadError("Metadados do audio de Portfolio ausentes.") from None
        try:
            object_key = self.storage.save(data, project_id, slot)
        except PortfolioAudioStorageError:
            raise StorageUploadError("Nao foi possivel armazenar o audio.") from None
        reference = self._reference(object_key)
        digest = validate_sha256(sha256) or sha256_hex(data)
        object_metadata = ObjectMetadata(len(data), content_type, sha256=digest, custom=metadata)
        return StoredObject(reference, object_metadata, self.get_public_url(reference))

    def delete(self, reference) -> None:
        try:
            self.storage.delete(self._key(reference))
        except PortfolioAudioStorageError:
            raise StorageDeleteError("Nao foi possivel remover o audio.") from None

    def get_public_url(self, reference) -> str:
        try:
            return self.storage.public_url(self._key(reference))
        except PortfolioAudioStorageError:
            raise StorageInvalidReference("Referencia do audio legado invalida.") from None


class SupabaseProductionAdapter(StorageAdapter):
    provider = "supabase"
    visibility = ObjectVisibility.PRIVATE

    def __init__(
        self,
        scope: StorageScope,
        storage: SupabaseProducaoArquivoStorage | None = None,
    ) -> None:
        if scope not in {StorageScope.PRODUCTION_TEMP, StorageScope.PRODUCTION_FINAL}:
            raise StorageConfigurationError("Escopo invalido para o adapter Supabase de Producao.")
        self.scope = scope
        try:
            self.storage = storage or SupabaseProducaoArquivoStorage()
        except ProducaoArquivoStorageError as exc:
            raise StorageConfigurationError(str(exc)) from None
        self.bucket = self.storage.bucket

    def _reference(self, key: str) -> ObjectReference:
        return ObjectReference(self.provider, self.bucket, key)

    def _key(self, value: ObjectReference | str) -> str:
        reference = coerce_reference(value)
        if reference.provider != self.provider or reference.namespace != self.bucket:
            raise StorageInvalidReference("Referencia de Producao legada invalida.")
        return reference.key

    def save(self, data, content_type, *, key=None, metadata=None, sha256=None) -> StoredObject:
        if key is not None:
            raise StorageOperationNotSupported("O adapter legado sempre gera uma chave imutavel.")
        DEFAULT_POLICIES[self.scope].validate(data, content_type)
        try:
            object_key = self.storage.save(data, content_type)
        except ProducaoArquivoStorageError:
            raise StorageUploadError("Nao foi possivel armazenar o arquivo.") from None
        digest = validate_sha256(sha256) or sha256_hex(data)
        object_metadata = ObjectMetadata(len(data), content_type, sha256=digest, custom=dict(metadata or {}))
        return StoredObject(self._reference(object_key), object_metadata)

    def read(self, reference) -> bytes:
        try:
            return self.storage.read(self._key(reference))
        except ProducaoArquivoStorageError:
            raise StorageUnavailable("Arquivo legado indisponivel.") from None

    def delete(self, reference) -> None:
        try:
            self.storage.delete(self._key(reference))
        except ProducaoArquivoStorageError:
            raise StorageDeleteError("Nao foi possivel remover o arquivo legado.") from None


class LegacyDocumentAdapter(StorageAdapter):
    """Bridge only; the PDF flow remains on its established interfaces."""

    provider = "legacy_document"
    scope = StorageScope.PROPOSAL_DOCUMENT
    visibility = ObjectVisibility.PRIVATE

    @staticmethod
    def _encode(raw_reference: str) -> str:
        return base64.urlsafe_b64encode(raw_reference.encode("utf-8")).decode("ascii").rstrip("=")

    def _raw_reference(self, value: ObjectReference | str) -> str:
        reference = coerce_reference(value)
        if reference.provider != self.provider or reference.namespace != "documents":
            raise StorageInvalidReference("Referencia de documento legado invalida.")
        try:
            padding = "=" * (-len(reference.key) % 4)
            return base64.urlsafe_b64decode(reference.key + padding).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError):
            raise StorageInvalidReference("Referencia de documento legado invalida.") from None

    def save(self, data, content_type, *, key=None, metadata=None, sha256=None) -> StoredObject:
        if key is not None:
            raise StorageOperationNotSupported("O storage de documentos gera a propria chave.")
        DEFAULT_POLICIES[self.scope].validate(data, content_type)
        metadata = dict(metadata or {})
        try:
            proposta_id = int(metadata["proposta_id"])
            versao = int(metadata["versao"])
            raw_reference = novo_documento_storage().salvar(data, proposta_id, versao)
        except (KeyError, TypeError, ValueError):
            raise StorageUploadError("Metadados do documento ausentes.") from None
        except DocumentoIndisponivel:
            raise StorageUploadError("Nao foi possivel armazenar o documento.") from None
        reference = ObjectReference(self.provider, "documents", self._encode(raw_reference))
        digest = validate_sha256(sha256) or sha256_hex(data)
        object_metadata = ObjectMetadata(len(data), content_type, sha256=digest, custom=metadata)
        return StoredObject(reference, object_metadata)

    def delete(self, reference) -> None:
        raise StorageOperationNotSupported("Exclusao de documentos legados nao e suportada.")

    def read(self, reference) -> bytes:
        raw_reference = self._raw_reference(reference)
        try:
            return storage_para_referencia(raw_reference).ler(raw_reference)
        except DocumentoIndisponivel:
            raise StorageUnavailable("Documento legado indisponivel.") from None

    def stat(self, reference) -> ObjectMetadata:
        data = self.read(reference)
        return ObjectMetadata(len(data), "application/pdf", sha256=sha256_hex(data))
