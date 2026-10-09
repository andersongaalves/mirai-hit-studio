"""Storage preflight reports configuration without probing live providers."""

import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from scripts.storage_preflight import build_report, main


class StoragePreflightTests(unittest.TestCase):
    def valid_environment(self):
        env = {
            "R2_ACCOUNT_ID": "a" * 32,
            "R2_ACCESS_KEY_ID": "test-key-id",
            "R2_SECRET_ACCESS_KEY": "test-secret",
            "R2_TEMP_BUCKET": "private-temp",
            "R2_FINAL_BUCKET": "private-final",
            "CLOUDINARY_CLOUD_NAME": "mirai-test",
            "CLOUDINARY_API_KEY": "test-api-key",
            "CLOUDINARY_API_SECRET": "test-api-secret",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
            "PRODUCTION_TEMP_STORAGE_BACKEND": "r2",
            "PRODUCTION_FINAL_STORAGE_BACKEND": "r2",
            "PUBLIC_IMAGE_STORAGE_BACKEND": "cloudinary",
            "PORTFOLIO_AUDIO_STORAGE_BACKEND": "supabase",
            "COMMERCIAL_PIPELINE_V2_ENABLED": "false",
        }
        return env

    def test_presence_and_validity_do_not_claim_connectivity_or_smoke(self):
        env = self.valid_environment()
        report = build_report(env)
        self.assertTrue(report["components"]["r2_private_temp"]["configuration_valid"])
        self.assertTrue(report["components"]["legacy_storage"]["configuration_valid"])
        self.assertEqual(report["components"]["r2_private_temp"]["provider_accessible"], "not_checked")
        self.assertEqual(report["components"]["r2_private_temp"]["smoke"], "not_run")
        self.assertFalse(report["rollout_ready"])
        self.assertNotIn("test-secret", str(report))
        self.assertNotIn("test-service-key", str(report))

    def test_rollout_gate_requires_each_provider_attestation_and_v2_off(self):
        env = self.valid_environment()
        for component in ("R2_TEMP", "R2_FINAL", "CLOUDINARY", "SUPABASE_AUDIO", "LEGACY_STORAGE"):
            env[f"STORAGE_PREFLIGHT_{component}_ACCESSIBLE"] = "true"
            env[f"STORAGE_PREFLIGHT_{component}_SMOKE"] = "approved"
        self.assertTrue(build_report(env)["rollout_ready"])
        env["COMMERCIAL_PIPELINE_V2_ENABLED"] = "true"
        self.assertFalse(build_report(env)["rollout_ready"])

    def test_supabase_can_be_selected_for_new_production_writes_while_r2_stays_ready(self):
        env = self.valid_environment()
        env["PRODUCTION_TEMP_STORAGE_BACKEND"] = "supabase"
        env["PRODUCTION_FINAL_STORAGE_BACKEND"] = "supabase"
        report = build_report(env)
        self.assertTrue(report["components"]["r2_private_temp"]["configuration_valid"])
        self.assertTrue(report["components"]["r2_private_temp"]["write_backend_valid"])
        self.assertEqual(report["components"]["r2_private_temp"]["write_backend"], "supabase")

    def test_missing_or_invalid_configuration_blocks_rollout(self):
        env = self.valid_environment()
        env["R2_TEMP_BUCKET"] = "Bad Bucket"
        report = build_report(env)
        self.assertFalse(report["components"]["r2_private_temp"]["configuration_valid"])
        self.assertFalse(report["rollout_ready"])

    def test_require_ready_returns_failure_when_provider_smoke_is_unverified(self):
        env = self.valid_environment()
        output = StringIO()
        with patch.dict("os.environ", env, clear=True), redirect_stdout(output):
            self.assertEqual(main(["--require-rollout-ready"]), 1)
        self.assertIn('"provider_connectivity_probed": false', output.getvalue())


if __name__ == "__main__":
    unittest.main()
