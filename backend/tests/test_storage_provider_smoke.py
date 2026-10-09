import unittest
from unittest.mock import patch

from scripts.storage_provider_smoke import run_smokes


class StorageProviderSmokeTests(unittest.TestCase):
    def test_provider_failure_is_reported_sanitized_and_blocks_attestation(self):
        with (
            patch(
                "scripts.storage_provider_smoke._r2_smoke",
                side_effect=RuntimeError("secret endpoint and object key"),
            ),
            patch(
                "scripts.storage_provider_smoke._cloudinary_smoke",
                return_value={"operations": [], "sha256": "a" * 64},
            ),
            patch(
                "scripts.storage_provider_smoke._audio_smoke",
                return_value={"operations": [], "sha256": "b" * 64},
            ),
            patch(
                "scripts.storage_provider_smoke._legacy_smoke",
                return_value={"operations": [], "sha256": "c" * 64},
            ),
        ):
            report = run_smokes()

        self.assertFalse(report["all_passed"])
        for name in ("r2_private_temp", "r2_private_final"):
            self.assertEqual(report["components"][name]["smoke"], "failed")
            self.assertEqual(report["components"][name]["failure_class"], "RuntimeError")
        self.assertNotIn("secret endpoint", str(report))
        self.assertNotIn("object key", str(report))


if __name__ == "__main__":
    unittest.main()
