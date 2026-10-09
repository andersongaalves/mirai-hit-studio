"""Single provider registry; application code resolves storage by scope."""

from __future__ import annotations

from collections.abc import Callable

from .cloudinary import CloudinaryImageStorage
from .config import StorageSettings
from .contracts import (
    ObjectReference,
    ObjectVisibility,
    StorageAdapter,
    StorageConfigurationError,
    StorageInvalidReference,
    StorageScope,
)
from .legacy import LegacyDocumentAdapter, SupabasePortfolioAudioAdapter, SupabaseProductionAdapter
from .memory import InMemoryStorage
from .r2 import R2Storage


Factory = Callable[[StorageScope, StorageSettings], StorageAdapter]


class StorageRegistry:
    def __init__(self, settings: StorageSettings, factories: dict[str, Factory] | None = None) -> None:
        self.settings = settings
        self.factories: dict[str, Factory] = {
            "cloudinary": self._cloudinary,
            "r2": self._r2,
            "supabase": self._supabase,
            "legacy": self._legacy,
            "memory": lambda scope, settings: InMemoryStorage(scope),
        }
        if factories:
            self.factories.update(factories)
        self._instances: dict[StorageScope, StorageAdapter] = {}

    def storage_for(self, scope: StorageScope | str) -> StorageAdapter:
        try:
            normalized_scope = scope if isinstance(scope, StorageScope) else StorageScope(scope)
        except ValueError:
            raise StorageConfigurationError("Escopo de storage desconhecido.") from None
        if normalized_scope in self._instances:
            return self._instances[normalized_scope]
        provider = self.settings.backends.get(normalized_scope, "")
        try:
            factory = self.factories[provider]
        except KeyError:
            raise StorageConfigurationError(
                f"Provider de storage invalido para {normalized_scope.value}."
            ) from None
        adapter = factory(normalized_scope, self.settings)
        if adapter.scope != normalized_scope:
            raise StorageConfigurationError("Provider de storage incompativel com o escopo.")
        self._instances[normalized_scope] = adapter
        return adapter

    def storage_for_reference(
        self,
        scope: StorageScope | str,
        reference: ObjectReference,
    ) -> StorageAdapter:
        """Resolve an existing object independently of the configured write backend."""
        try:
            normalized_scope = scope if isinstance(scope, StorageScope) else StorageScope(scope)
        except ValueError:
            raise StorageInvalidReference("Escopo da referencia invalido.") from None

        if normalized_scope not in {StorageScope.PRODUCTION_TEMP, StorageScope.PRODUCTION_FINAL}:
            raise StorageInvalidReference("Referencia privada de Producao invalida.")
        if reference.provider not in {"r2", "supabase", "memory"}:
            raise StorageInvalidReference("Provider da referencia de Producao invalido.")

        try:
            factory = self.factories[reference.provider]
        except KeyError:
            raise StorageConfigurationError("Provider da referencia nao esta disponivel.") from None
        adapter = factory(normalized_scope, self.settings)
        if adapter.scope != normalized_scope or adapter.visibility != ObjectVisibility.PRIVATE:
            raise StorageInvalidReference("Escopo da referencia de Producao invalido.")

        namespace = getattr(adapter, "bucket", None) or getattr(adapter, "namespace", None)
        if namespace != reference.namespace:
            raise StorageInvalidReference("Namespace da referencia de Producao invalido.")
        return adapter

    @staticmethod
    def _cloudinary(scope: StorageScope, settings: StorageSettings) -> StorageAdapter:
        if scope != StorageScope.PUBLIC_IMAGE:
            raise StorageConfigurationError("Cloudinary permitido apenas para imagens publicas.")
        return CloudinaryImageStorage(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
        )

    @staticmethod
    def _r2(scope: StorageScope, settings: StorageSettings) -> StorageAdapter:
        bucket = (
            settings.r2_temp_bucket
            if scope == StorageScope.PRODUCTION_TEMP
            else settings.r2_final_bucket
            if scope == StorageScope.PRODUCTION_FINAL
            else ""
        )
        return R2Storage(
            scope=scope,
            account_id=settings.r2_account_id,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=bucket,
            endpoint=settings.r2_endpoint or None,
            region=settings.r2_region,
            max_presign_seconds=settings.r2_presign_max_seconds,
        )

    @staticmethod
    def _supabase(scope: StorageScope, settings: StorageSettings) -> StorageAdapter:
        if scope == StorageScope.PORTFOLIO_AUDIO:
            return SupabasePortfolioAudioAdapter()
        if scope in {StorageScope.PRODUCTION_TEMP, StorageScope.PRODUCTION_FINAL}:
            return SupabaseProductionAdapter(scope)
        raise StorageConfigurationError("Supabase legado incompativel com o escopo.")

    @staticmethod
    def _legacy(scope: StorageScope, settings: StorageSettings) -> StorageAdapter:
        if scope != StorageScope.PROPOSAL_DOCUMENT:
            raise StorageConfigurationError("Adapter legado incompativel com o escopo.")
        return LegacyDocumentAdapter()


def storage_for(scope: StorageScope | str, *, settings: StorageSettings | None = None) -> StorageAdapter:
    return StorageRegistry(settings or StorageSettings.from_env()).storage_for(scope)
