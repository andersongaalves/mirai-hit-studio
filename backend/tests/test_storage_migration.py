"""Idempotent Storage migration using disposable adapters only."""

import hashlib
import unittest

import test_bootstrap_database as isolated

from services.storage.contracts import StorageScope
from services.storage.memory import InMemoryStorage
from services.storage.migration import (
    MigrationCandidate,
    StorageMigrationError,
    migrate_candidate,
)


class StorageMigrationTests(unittest.TestCase):
    def candidate(self, source, data=b"%PDF-synthetic"):
        stored = source.save(data, "application/pdf", key="production-final/source.pdf")
        return MigrationCandidate(
            record_id=17,
            scope=StorageScope.PRODUCTION_FINAL,
            source=stored.reference,
            content_type="application/pdf",
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def test_copy_verify_retry_and_preserve_source(self):
        source = InMemoryStorage(StorageScope.PRODUCTION_FINAL)
        destination = InMemoryStorage(StorageScope.PRODUCTION_FINAL)
        candidate = self.candidate(source)

        first = migrate_candidate(candidate, source=source, destination=destination)
        second = migrate_candidate(candidate, source=source, destination=destination)

        self.assertTrue(first.copied and first.verified)
        self.assertFalse(second.copied)
        self.assertEqual(first.destination, second.destination)
        self.assertEqual(source.read(candidate.source), b"%PDF-synthetic")
        self.assertEqual(destination.read(first.destination), b"%PDF-synthetic")
        self.assertEqual(source.deleted, [])

    def test_source_hash_mismatch_fails_before_copy(self):
        source = InMemoryStorage(StorageScope.PRODUCTION_FINAL)
        destination = InMemoryStorage(StorageScope.PRODUCTION_FINAL)
        candidate = self.candidate(source)
        invalid = MigrationCandidate(
            candidate.record_id,
            candidate.scope,
            candidate.source,
            candidate.content_type,
            candidate.size,
            "0" * 64,
        )
        with self.assertRaisesRegex(StorageMigrationError, "sha256_mismatch"):
            migrate_candidate(invalid, source=source, destination=destination)
        self.assertEqual(destination.objects, {})

    def test_conflicting_destination_with_different_content_fails_closed(self):
        source = InMemoryStorage(StorageScope.PRODUCTION_FINAL)
        destination = InMemoryStorage(StorageScope.PRODUCTION_FINAL)
        candidate = self.candidate(source)
        from services.storage.migration import destination_key

        destination.save(
            b"%PDF-different",
            "application/pdf",
            key=destination_key(candidate),
        )
        with self.assertRaises(StorageMigrationError):
            migrate_candidate(candidate, source=source, destination=destination)

    def test_inventory_is_sanitized_and_read_only(self):
        isolated.BootstrapTests().run_case("""
            bootstrap(engine)
            from sqlalchemy.orm import Session
            from scripts.migrate_production_files import inventory
            with Session(engine) as db:
                report = inventory(db)
            assert report == {
                'mode': 'inventory', 'total': 0, 'providers': {}, 'types': {},
                'references_printed': 0, 'deletions': 0,
            }
        """)


if __name__ == "__main__":
    unittest.main()
