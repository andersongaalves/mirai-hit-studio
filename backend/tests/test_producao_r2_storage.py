"""Provider-neutral production-file storage integration tests."""

import unittest

import test_bootstrap_database as isolated

from services.producao_arquivo_storage import (
    FILE_TYPE_SCOPE,
    ProducaoArquivoStorageError,
    ProductionFileStorage,
    new_production_file_storage,
)
from services.storage.config import StorageSettings
from services.storage.contracts import (
    ObjectMetadata,
    ObjectReference,
    ObjectVisibility,
    StorageAdapter,
    StorageInvalidReference,
    StorageScope,
    StoredObject,
)
from services.storage.legacy import SupabaseProductionAdapter
from services.storage.memory import InMemoryStorage
from services.storage.registry import StorageRegistry


class FakeRegistry:
    def __init__(self):
        self.adapters = {
            StorageScope.PRODUCTION_TEMP: InMemoryStorage(StorageScope.PRODUCTION_TEMP),
            StorageScope.PRODUCTION_FINAL: InMemoryStorage(StorageScope.PRODUCTION_FINAL),
        }

    def storage_for(self, scope):
        return self.adapters[scope]

    def storage_for_reference(self, scope, reference):
        adapter = self.adapters[scope]
        if reference.provider != adapter.provider or reference.namespace != adapter.namespace:
            raise StorageInvalidReference("Referencia de fake invalida.")
        return adapter


class FakePrivateProvider(StorageAdapter):
    visibility = ObjectVisibility.PRIVATE

    def __init__(self, provider, scope, namespace):
        self.provider = provider
        self.scope = scope
        self.bucket = namespace
        self.objects = {}
        self.deleted = []

    def save(self, data, content_type, *, key=None, metadata=None, sha256=None):
        key = key or f"{self.scope.value}/opaque"
        reference = ObjectReference(self.provider, self.bucket, key)
        self.objects[str(reference)] = data
        return StoredObject(reference, ObjectMetadata(len(data), content_type, sha256=sha256))

    def read(self, reference):
        reference = reference if isinstance(reference, ObjectReference) else ObjectReference.parse(reference)
        return self.objects[str(reference)]

    def delete(self, reference):
        reference = reference if isinstance(reference, ObjectReference) else ObjectReference.parse(reference)
        self.deleted.append(str(reference))
        self.objects.pop(str(reference), None)


class ProviderSwitchRegistry(StorageRegistry):
    def __init__(self, selected_provider, providers):
        settings = StorageSettings(backends={
            StorageScope.PRODUCTION_TEMP: selected_provider,
            StorageScope.PRODUCTION_FINAL: selected_provider,
        })
        factories = {
            provider: (lambda scope, _settings, provider=provider: providers[(provider, scope)])
            for provider in {"r2", "supabase"}
        }
        super().__init__(settings, factories=factories)


class FakeLegacyStorage:
    bucket = "producao-arquivos"

    def __init__(self):
        self.objects = {}
        self.deleted = []

    def read(self, key):
        return self.objects[key]

    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)


class ProductionFileStorageTests(unittest.TestCase):
    def test_types_are_split_between_temporary_and_final_scopes(self):
        self.assertEqual(StorageScope(FILE_TYPE_SCOPE["material"]), StorageScope.PRODUCTION_TEMP)
        self.assertEqual(StorageScope(FILE_TYPE_SCOPE["referencia"]), StorageScope.PRODUCTION_TEMP)
        self.assertEqual(StorageScope(FILE_TYPE_SCOPE["previa"]), StorageScope.PRODUCTION_TEMP)
        self.assertEqual(StorageScope(FILE_TYPE_SCOPE["entrega"]), StorageScope.PRODUCTION_FINAL)
        self.assertEqual(StorageScope(FILE_TYPE_SCOPE["comprovante"]), StorageScope.PRODUCTION_FINAL)

    def test_new_objects_persist_opaque_reference_and_round_trip(self):
        registry = FakeRegistry()
        storage = ProductionFileStorage(StorageScope.PRODUCTION_TEMP, registry=registry)

        reference = storage.save(b"ID3synthetic", "audio/mpeg")

        self.assertRegex(reference, r"^memory://production-temp/production-temp/")
        self.assertNotIn("synthetic", reference)
        self.assertEqual(storage.read(reference), b"ID3synthetic")
        storage.delete(reference)
        self.assertEqual(registry.adapters[StorageScope.PRODUCTION_TEMP].objects, {})

    def test_legacy_raw_supabase_key_remains_readable_and_deletable(self):
        raw_key = "arquivos/" + "a" * 32 + "/" + "b" * 32
        for scope in (StorageScope.PRODUCTION_TEMP, StorageScope.PRODUCTION_FINAL):
            with self.subTest(scope=scope):
                registry = FakeRegistry()
                legacy = FakeLegacyStorage()
                legacy.objects[raw_key] = b"%PDF-legacy"
                adapter = SupabaseProductionAdapter(scope, legacy)
                storage = ProductionFileStorage(
                    scope,
                    registry=registry,
                    legacy_factory=lambda: adapter,
                )

                self.assertEqual(storage.read(raw_key), b"%PDF-legacy")
                storage.delete(raw_key)
                self.assertEqual(legacy.deleted, [raw_key])

    def test_persisted_provider_references_remain_readable_after_write_backend_switch(self):
        payload = b"synthetic-file"
        for scope in (StorageScope.PRODUCTION_TEMP, StorageScope.PRODUCTION_FINAL):
            with self.subTest(scope=scope):
                providers = {
                    ("r2", scope): FakePrivateProvider("r2", scope, f"r2-{scope.value}"),
                    ("supabase", scope): FakePrivateProvider("supabase", scope, f"sb-{scope.value}"),
                }
                r2_writer = ProductionFileStorage(
                    scope,
                    registry=ProviderSwitchRegistry("r2", providers),
                )
                r2_reference = r2_writer.save(payload, "application/pdf")
                supabase_writer = ProductionFileStorage(
                    scope,
                    registry=ProviderSwitchRegistry("supabase", providers),
                )
                self.assertEqual(supabase_writer.read(r2_reference), payload)
                supabase_reference = supabase_writer.save(payload, "application/pdf")
                self.assertEqual(r2_writer.read(supabase_reference), payload)

    def test_reference_namespace_is_bound_to_configured_bucket_and_scope(self):
        scope = StorageScope.PRODUCTION_TEMP
        providers = {
            ("r2", scope): FakePrivateProvider("r2", scope, "approved-r2-temp"),
            ("supabase", scope): FakePrivateProvider("supabase", scope, "approved-supabase-temp"),
        }
        registry = ProviderSwitchRegistry("supabase", providers)
        storage = ProductionFileStorage(scope, registry=registry)
        for reference in (
            "r2://attacker-bucket/production-temp/opaque",
            "unknown://approved-supabase-temp/production-temp/opaque",
        ):
            with self.subTest(reference=reference), self.assertRaises(ProducaoArquivoStorageError):
                storage.read(reference)

    def test_provider_failure_keeps_reference_and_never_falls_back_to_writer(self):
        scope = StorageScope.PRODUCTION_FINAL
        providers = {
            ("r2", scope): FakePrivateProvider("r2", scope, "old-final"),
            ("supabase", scope): FakePrivateProvider("supabase", scope, "new-final"),
        }
        old_writer = ProductionFileStorage(scope, registry=ProviderSwitchRegistry("r2", providers))
        reference = old_writer.save(b"old-object", "application/pdf")

        class MissingOldProviderRegistry(ProviderSwitchRegistry):
            def storage_for_reference(self, scope, reference):
                if reference.provider == "r2":
                    from services.storage.contracts import StorageConfigurationError

                    raise StorageConfigurationError("old provider credentials unavailable")
                return super().storage_for_reference(scope, reference)

        switched = ProductionFileStorage(
            scope,
            registry=MissingOldProviderRegistry("supabase", providers),
        )
        with self.assertRaisesRegex(ProducaoArquivoStorageError, "credentials unavailable"):
            switched.read(reference)
        self.assertIn(reference, providers[("r2", scope)].objects)
        self.assertEqual(providers[("supabase", scope)].objects, {})

    def test_delete_uses_origin_provider_and_namespace(self):
        scope = StorageScope.PRODUCTION_TEMP
        providers = {
            ("r2", scope): FakePrivateProvider("r2", scope, "r2-temp"),
            ("supabase", scope): FakePrivateProvider("supabase", scope, "sb-temp"),
        }
        writer = ProductionFileStorage(scope, registry=ProviderSwitchRegistry("r2", providers))
        reference = writer.save(b"old-object", "application/pdf")
        reader = ProductionFileStorage(scope, registry=ProviderSwitchRegistry("supabase", providers))
        reader.delete(reference)
        self.assertEqual(providers[("r2", scope)].deleted, [reference])
        self.assertEqual(providers[("supabase", scope)].deleted, [])

    def test_download_rejects_content_with_database_hash_mismatch(self):
        isolated.BootstrapTests().run_case(r'''
from types import SimpleNamespace
from unittest.mock import patch
from services import producao_arquivo_service

model = SimpleNamespace(
    id=17, producao_id=9, tipo="entrega",
    object_key="opaque-reference", sha256="0" * 64)
storage = SimpleNamespace(read=lambda value: b"%PDF-tampered")
with patch.object(producao_arquivo_service.logger, "error") as logged:
    try:
        producao_arquivo_service.read(model, storage=storage)
    except producao_arquivo_service.ProducaoArquivoUnavailable as error:
        assert str(error) == "Integridade do arquivo nao confirmada."
    else:
        raise AssertionError("hash mismatch accepted")
    assert logged.call_args.args[0].startswith("production_file_integrity_mismatch")
    assert "opaque-reference" not in str(logged.call_args)
''')

    def test_factory_rejects_unknown_file_type(self):
        with self.assertRaisesRegex(Exception, "Tipo de arquivo"):
            new_production_file_storage("desconhecido")


if __name__ == "__main__":
    unittest.main()
