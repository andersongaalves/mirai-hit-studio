"""Storage Core integration for public Portfolio audio."""

import unittest

import httpx

from services.portfolio_audio_storage import SupabasePortfolioAudioStorage
from services.portfolio_audio_storage_core import PortfolioAudioStorage
from services.storage.legacy import SupabasePortfolioAudioAdapter


class PortfolioAudioStorageCoreTests(unittest.TestCase):
    def test_new_reference_and_historical_raw_key_use_same_public_bucket(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.method == "GET" and "/bucket/" in request.url.path:
                return httpx.Response(200, json={"public": True})
            if request.method == "POST" and "/object/" in request.url.path:
                self.assertEqual(request.headers["content-type"], "audio/mpeg")
                self.assertEqual(request.headers["x-upsert"], "false")
                return httpx.Response(200)
            if request.method == "DELETE" and "/object/" in request.url.path:
                return httpx.Response(200)
            return httpx.Response(404)

        legacy = SupabasePortfolioAudioStorage(
            base_url="https://project.supabase.co",
            service_key="server-only-test-key",
            bucket="portfolio-audio",
            transport=httpx.MockTransport(handler),
        )
        storage = PortfolioAudioStorage(SupabasePortfolioAudioAdapter(legacy))

        reference = storage.save(b"ID3synthetic", 42, "before")
        self.assertRegex(
            reference,
            r"^supabase://portfolio-audio/projects/42/before-[a-f0-9]{32}\.mp3$",
        )
        public_url = storage.public_url(reference)
        self.assertIn("/storage/v1/object/public/portfolio-audio/projects/42/", public_url)

        raw_key = reference.split("/", 3)[-1]
        self.assertEqual(storage.public_url(raw_key), public_url)
        storage.delete(reference)
        storage.delete(raw_key)

        self.assertEqual([request.method for request in requests], ["GET", "POST", "DELETE", "DELETE"])
        self.assertTrue(all("server-only-test-key" not in str(request.url) for request in requests))


if __name__ == "__main__":
    unittest.main()
