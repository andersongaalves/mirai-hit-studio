"""Provider-neutral production-file storage integration tests."""

import unittest

import test_bootstrap_database as isolated

from services.producao_arquivo_storage import (
    FILE_TYPE_SCOPE,
    ProductionFileStorage,
    new_production_file_storage,
)
from services.storage.contracts import StorageScope
from services.storage.legacy import SupabaseProductionAdapter
from services.storage.memory import InMemoryStorage


class FakeRegistry:
    def __init__(self):
        self.adapters = {
            StorageScope.PRODUCTION_TEMP: InMemoryStorage(StorageScope.PRODUCTION_TEMP),
            StorageScope.PRODUCTION_FINAL: InMemoryStorage(StorageScope.PRODUCTION_FINAL),
        }

    def storage_for(self, scope):
        return self.adapters[scope]


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
        registry = FakeRegistry()
        legacy = FakeLegacyStorage()
        raw_key = "arquivos/" + "a" * 32 + "/" + "b" * 32
        legacy.objects[raw_key] = b"%PDF-legacy"
        adapter = SupabaseProductionAdapter(StorageScope.PRODUCTION_FINAL, legacy)
        storage = ProductionFileStorage(
            StorageScope.PRODUCTION_FINAL,
            registry=registry,
            legacy_factory=lambda: adapter,
        )

        self.assertEqual(storage.read(raw_key), b"%PDF-legacy")
        storage.delete(raw_key)
        self.assertEqual(legacy.deleted, [raw_key])

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
