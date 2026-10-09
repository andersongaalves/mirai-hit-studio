"""Unit coverage for the provider-neutral storage core; no real provider calls."""

import unittest
from datetime import datetime, timezone

import httpx

from services.storage.cloudinary import CloudinaryImageStorage
from services.storage.config import StorageSettings
from services.storage.contracts import (
    ObjectReference,
    StorageConfigurationError,
    StorageConflictError,
    StorageInvalidReference,
    StorageScope,
    StorageUnavailable,
    StorageUploadError,
    StorageValidationError,
)
from services.storage.legacy import SupabasePortfolioAudioAdapter
from services.storage.memory import InMemoryStorage
from services.storage.policies import StoragePolicy
from services.storage.r2 import R2Storage
from services.storage.registry import StorageRegistry

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
ACCOUNT_ID = "a" * 32
SECRET = "server-only-r2-secret"


class ReferenceAndRegistryTests(unittest.TestCase):
    def test_reference_round_trip_and_rejects_ambiguous_or_secret_values(self):
        reference = ObjectReference("r2", "production-temp", "production-temp/a" * 1 + ".pdf")
        self.assertEqual(ObjectReference.parse(str(reference)), reference)

        invalid = [
            "r2://bucket/../secret",
            "r2://user:password@bucket/key",
            "r2://bucket/key?token=secret",
            "r2://bucket/a%2Fb",
            "https://bucket/key#fragment",
            "r2://bucket/a\\b",
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(StorageInvalidReference):
                ObjectReference.parse(value)

    def test_registry_resolves_scope_once(self):
        settings = StorageSettings(backends={StorageScope.PUBLIC_IMAGE: "memory"})
        registry = StorageRegistry(settings)
        first = registry.storage_for("public_image")
        self.assertIs(first, registry.storage_for(StorageScope.PUBLIC_IMAGE))
        self.assertIsInstance(first, InMemoryStorage)

    def test_registry_rejects_unknown_scope_provider_and_missing_configuration(self):
        with self.assertRaises(StorageConfigurationError):
            StorageRegistry(StorageSettings()).storage_for("not-a-scope")
        with self.assertRaises(StorageConfigurationError):
            StorageRegistry(StorageSettings(backends={StorageScope.PUBLIC_IMAGE: "invalid"})).storage_for(
                StorageScope.PUBLIC_IMAGE
            )
        with self.assertRaises(StorageConfigurationError):
            StorageRegistry(StorageSettings()).storage_for(StorageScope.PUBLIC_IMAGE)


class R2AdapterTests(unittest.TestCase):
    def new_storage(self, handler, *, policy=None):
        return R2Storage(
            scope=StorageScope.PRODUCTION_TEMP,
            account_id=ACCOUNT_ID,
            access_key_id="test-access-key",
            secret_access_key=SECRET,
            bucket="production-temp",
            policy=policy,
            transport=httpx.MockTransport(handler),
            now=lambda: NOW,
        )

    def test_upload_read_stat_delete_and_checksum_is_not_etag(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.method == "PUT":
                self.assertEqual(request.headers["if-none-match"], "*")
                self.assertEqual(request.headers["content-type"], "application/pdf")
                self.assertEqual(request.headers["x-amz-meta-stage"], "test")
                return httpx.Response(200, headers={"ETag": '"multipart-etag-2"'})
            if request.method == "GET":
                return httpx.Response(200, content=b"%PDF-test")
            if request.method == "HEAD":
                return httpx.Response(200, headers={
                    "Content-Length": "9",
                    "Content-Type": "application/pdf",
                    "ETag": '"multipart-etag-2"',
                    "x-amz-meta-sha256": "b" * 64,
                })
            if request.method == "DELETE":
                return httpx.Response(204)
            return httpx.Response(500)

        storage = self.new_storage(handler)
        stored = storage.save(
            b"%PDF-test",
            "application/pdf",
            key="production-temp/opaque.pdf",
            metadata={"stage": "test"},
        )
        self.assertEqual(str(stored.reference), "r2://production-temp/production-temp/opaque.pdf")
        self.assertEqual(stored.metadata.etag, "multipart-etag-2")
        self.assertNotEqual(stored.metadata.sha256, stored.metadata.etag)
        self.assertEqual(storage.read(stored.reference), b"%PDF-test")
        remote = storage.stat(stored.reference)
        self.assertEqual(remote.sha256, "b" * 64)
        self.assertEqual(remote.etag, "multipart-etag-2")
        storage.delete(stored.reference)
        self.assertEqual([request.method for request in requests], ["PUT", "GET", "HEAD", "DELETE"])
        self.assertTrue(all(SECRET not in str(request.url) for request in requests))

    def test_presigned_get_and_put_are_short_lived_operation_specific_and_immutable(self):
        storage = self.new_storage(lambda request: httpx.Response(500))
        reference = ObjectReference("r2", "production-temp", "production-temp/opaque.pdf")
        download = storage.presign_get(reference, expires_seconds=120)
        self.assertEqual(download.method, "GET")
        self.assertIn("X-Amz-Expires=120", download.url)
        self.assertIn("production-temp/opaque.pdf", download.url)
        self.assertNotIn(SECRET, download.url)

        upload = storage.presign_put(
            "application/pdf",
            9,
            key="production-temp/new.pdf",
            expires_seconds=90,
            sha256="c" * 64,
        )
        self.assertEqual(upload.method, "PUT")
        self.assertEqual(upload.headers["Content-Length"], "9")
        self.assertEqual(upload.headers["If-None-Match"], "*")
        self.assertEqual(upload.headers["x-amz-meta-sha256"], "c" * 64)
        self.assertIn("X-Amz-Expires=90", upload.url)
        with self.assertRaises(StorageConfigurationError):
            storage.presign_get(reference, expires_seconds=901)

    def test_invalid_mime_size_signature_key_and_overwrite_are_rejected(self):
        calls = []

        def conflict(request):
            calls.append(request)
            return httpx.Response(412)

        policy = StoragePolicy(frozenset({"application/pdf"}), 16)
        storage = self.new_storage(conflict, policy=policy)
        with self.assertRaises(StorageValidationError):
            storage.save(b"%PDF-test", "text/plain")
        with self.assertRaises(StorageValidationError):
            storage.save(b"not-a-pdf", "application/pdf")
        with self.assertRaises(StorageValidationError):
            storage.save(b"%PDF-" + b"x" * 20, "application/pdf")
        with self.assertRaises(StorageInvalidReference):
            storage.save(b"%PDF-test", "application/pdf", key="../escape.pdf")
        with self.assertRaises(StorageConflictError):
            storage.save(b"%PDF-test", "application/pdf", key="production-temp/fixed.pdf")
        self.assertEqual(len(calls), 1)

    def test_remote_failure_is_normalized_and_does_not_leak_secrets(self):
        storage = self.new_storage(
            lambda request: httpx.Response(500, text=f"provider payload {SECRET}")
        )
        with self.assertRaises(StorageUploadError) as raised:
            storage.save(b"%PDF-test", "application/pdf")
        self.assertNotIn(SECRET, str(raised.exception))
        self.assertNotIn(ACCOUNT_ID, str(raised.exception))

        unavailable = self.new_storage(
            lambda request: (_ for _ in ()).throw(httpx.ConnectError(f"connect {SECRET}"))
        )
        with self.assertRaises(StorageUnavailable) as raised:
            unavailable.read(ObjectReference("r2", "production-temp", "production-temp/x.pdf"))
        self.assertNotIn(SECRET, str(raised.exception))

    def test_rejects_non_cloudflare_endpoint_to_avoid_configured_ssrf(self):
        with self.assertRaises(StorageConfigurationError):
            R2Storage(
                scope=StorageScope.PRODUCTION_TEMP,
                account_id=ACCOUNT_ID,
                access_key_id="access",
                secret_access_key=SECRET,
                bucket="production-temp",
                endpoint="https://127.0.0.1/internal",
            )


class CloudinaryAdapterTests(unittest.TestCase):
    def test_upload_public_url_and_delete(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.url.path.endswith("/image/upload"):
                self.assertNotIn("cloudinary-secret", request.content.decode(errors="ignore"))
                return httpx.Response(200, json={
                    "public_id": "public-images/opaque",
                    "bytes": 7,
                    "etag": "provider-etag",
                })
            if request.url.path.endswith("/image/destroy"):
                return httpx.Response(200, json={"result": "ok"})
            return httpx.Response(404)

        storage = CloudinaryImageStorage(
            cloud_name="mirai-test",
            api_key="cloudinary-key",
            api_secret="cloudinary-secret",
            transport=httpx.MockTransport(handler),
            now=lambda: NOW,
        )
        stored = storage.save(
            b"\xff\xd8\xfftest",
            "image/jpeg",
            key="public-images/opaque",
        )
        self.assertEqual(str(stored.reference), "cloudinary://mirai-test/public-images/opaque")
        self.assertEqual(
            stored.public_url,
            "https://res.cloudinary.com/mirai-test/image/upload/"
            "f_auto,q_auto,c_limit,w_1600/public-images/opaque",
        )
        self.assertEqual(storage.reference_from_public_url(stored.public_url), stored.reference)
        self.assertEqual(
            storage.reference_from_public_url(
                "https://res.cloudinary.com/mirai-test/image/upload/public-images/opaque"
            ),
            stored.reference,
        )
        self.assertIsNone(storage.reference_from_public_url("https://example.invalid/cover.jpg"))
        storage.delete(stored.reference)
        self.assertEqual(len(requests), 2)

    def test_invalid_image_and_remote_error_are_normalized(self):
        storage = CloudinaryImageStorage(
            cloud_name="mirai-test",
            api_key="cloudinary-key",
            api_secret="cloudinary-secret",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(500, json={"error": "cloudinary-secret provider detail"})
            ),
            now=lambda: NOW,
        )
        with self.assertRaises(StorageValidationError):
            storage.save(b"plain text", "image/jpeg")
        with self.assertRaises(StorageUploadError) as raised:
            storage.save(b"\x89PNG\r\n\x1a\nrest", "image/png")
        self.assertNotIn("cloudinary-secret", str(raised.exception))


class LegacyAndFakeTests(unittest.TestCase):
    def test_supabase_portfolio_wrapper_reuses_legacy_adapter(self):
        class FakeLegacyStorage:
            bucket = "portfolio-audio"

            def __init__(self):
                self.deleted = []

            def save(self, data, project_id, slot):
                self.saved = (data, project_id, slot)
                return f"projects/{project_id}/{slot}-{'a' * 32}.mp3"

            def delete(self, key):
                self.deleted.append(key)

            def public_url(self, key):
                return "https://project.supabase.co/storage/v1/object/public/portfolio-audio/" + key

        legacy = FakeLegacyStorage()
        adapter = SupabasePortfolioAudioAdapter(legacy)
        stored = adapter.save(
            b"ID3synthetic",
            "audio/mpeg",
            metadata={"project_id": "27", "slot": "before"},
        )
        self.assertEqual(legacy.saved[1:], (27, "before"))
        self.assertTrue(stored.public_url.endswith(".mp3"))
        adapter.delete(stored.reference)
        self.assertEqual(legacy.deleted, [stored.reference.key])

    def test_in_memory_adapter_supports_save_read_stat_delete_signed_urls_and_no_overwrite(self):
        storage = InMemoryStorage(StorageScope.PRODUCTION_FINAL)
        stored = storage.save(
            b"%PDF-test",
            "application/pdf",
            key="production-final/fixed.pdf",
        )
        self.assertEqual(storage.read(stored.reference), b"%PDF-test")
        self.assertEqual(storage.stat(stored.reference).size, 9)
        self.assertEqual(storage.presign_get(stored.reference).method, "GET")
        self.assertEqual(
            storage.presign_put("application/pdf", 9, key="production-final/new.pdf").method,
            "PUT",
        )
        with self.assertRaises(StorageConflictError):
            storage.save(b"%PDF-test", "application/pdf", key="production-final/fixed.pdf")
        storage.delete(stored.reference)
        self.assertNotIn(stored.reference.key, storage.objects)


if __name__ == "__main__":
    unittest.main()
