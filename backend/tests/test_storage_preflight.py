"""Storage preflight reports configuration without probing live providers."""

import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from io import StringIO
from unittest.mock import patch

from scripts.storage_preflight import build_report, main, _configuration_fingerprint


class StoragePreflightTests(unittest.TestCase):
    EVIDENCE_KEY = "synthetic-preflight-evidence-key-only-for-tests"
    TARGET_SHA = "a" * 40

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
            "GITHUB_SHA": self.TARGET_SHA,
            "GITHUB_REPOSITORY": "andersongaalves/mirai-hit-studio",
            "STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY": self.EVIDENCE_KEY,
        }
        return env

    def valid_evidence(self, now=None):
        now = now or datetime.now(timezone.utc)
        evidence = {
            "schema_version": 1,
            "target_sha": self.TARGET_SHA,
            "configuration_fingerprint": _configuration_fingerprint(
                self.valid_environment(), self.EVIDENCE_KEY
            ),
            "workflow_run": {
                "id": "123456789",
                "url": "https://github.com/andersongaalves/mirai-hit-studio/actions/runs/123456789",
                "actor": "storage-rollout-approver",
                "workflow_ref": "andersongaalves/mirai-hit-studio/.github/workflows/storage-provider-rollout.yml@refs/heads/main",
                "authorization_ref": "CTRL-approval-test-fixture",
            },
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "components": {
                component: {
                    "connectivity": "passed",
                    "smoke": "passed",
                    "evidence_sha256": hashlib.sha256(component.encode()).hexdigest(),
                }
                for component in (
                    "r2_private_temp",
                    "r2_private_final",
                    "cloudinary",
                    "supabase_audio",
                    "legacy_storage",
                )
            },
        }
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        evidence["signature"] = hmac.new(
            self.EVIDENCE_KEY.encode(), canonical, hashlib.sha256
        ).hexdigest()
        return evidence

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

    def test_environment_flags_cannot_attest_provider_or_smoke(self):
        env = self.valid_environment()
        for component in ("R2_TEMP", "R2_FINAL", "CLOUDINARY", "SUPABASE_AUDIO", "LEGACY_STORAGE"):
            env[f"STORAGE_PREFLIGHT_{component}_ACCESSIBLE"] = "true"
            env[f"STORAGE_PREFLIGHT_{component}_SMOKE"] = "approved"
        report = build_report(env)
        self.assertFalse(report["rollout_ready"])
        self.assertEqual(report["evidence_status"], "not_provided")
        self.assertTrue(all(
            component["provider_accessible"] == "not_checked"
            and component["smoke"] == "not_run"
            for component in report["components"].values()
        ))

    def test_valid_signed_evidence_is_commit_bound_and_traceable(self):
        env = self.valid_environment()
        report = build_report(env, self.valid_evidence())
        self.assertTrue(report["rollout_ready"])
        self.assertEqual(report["evidence_status"], "verified")
        self.assertFalse(report["provider_connectivity_probed"])
        self.assertTrue(report["provider_connectivity_evidence_verified"])
        self.assertEqual(report["components"]["r2_private_temp"]["smoke"], "passed_with_evidence")
        env["COMMERCIAL_PIPELINE_V2_ENABLED"] = "true"
        self.assertFalse(build_report(env, self.valid_evidence())["rollout_ready"])

    def test_unsigned_tampered_or_wrong_sha_evidence_fails_closed(self):
        env = self.valid_environment()
        evidence = self.valid_evidence()
        evidence["components"]["r2_private_temp"]["smoke"] = "failed"
        report = build_report(env, evidence)
        self.assertFalse(report["rollout_ready"])
        self.assertEqual(report["evidence_status"], "signature_invalid")
        evidence = self.valid_evidence()
        env["GITHUB_SHA"] = "b" * 40
        report = build_report(env, evidence)
        self.assertFalse(report["rollout_ready"])
        self.assertEqual(report["evidence_status"], "target_sha_mismatch")

    def test_configuration_change_invalidates_signed_evidence(self):
        env = self.valid_environment()
        evidence = self.valid_evidence()
        env["R2_FINAL_BUCKET"] = "different-private-bucket"
        report = build_report(env, evidence)
        self.assertFalse(report["rollout_ready"])
        self.assertEqual(report["evidence_status"], "configuration_mismatch")

    def test_evidence_from_unapproved_workflow_is_rejected(self):
        env = self.valid_environment()
        evidence = self.valid_evidence()
        evidence["workflow_run"]["workflow_ref"] = "untrusted/workflow.yml@refs/heads/main"
        evidence.pop("signature")
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        evidence["signature"] = hmac.new(
            self.EVIDENCE_KEY.encode(), canonical, hashlib.sha256
        ).hexdigest()
        report = build_report(env, evidence)
        self.assertFalse(report["rollout_ready"])
        self.assertEqual(report["evidence_status"], "workflow_run_invalid")

    def test_evidence_must_be_complete_current_and_signed_by_protected_key(self):
        now = datetime.now(timezone.utc)
        env = self.valid_environment()
        evidence = self.valid_evidence(now)
        del evidence["components"]["cloudinary"]
        evidence.pop("signature")
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        evidence["signature"] = hmac.new(
            self.EVIDENCE_KEY.encode(), canonical, hashlib.sha256
        ).hexdigest()
        self.assertEqual(build_report(env, evidence, now)["evidence_status"], "component_evidence_incomplete")
        env["STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY"] = ""
        self.assertEqual(build_report(env, self.valid_evidence(now), now)["evidence_status"], "signature_missing")
        expired = self.valid_evidence(now - timedelta(days=2))
        self.assertEqual(build_report(self.valid_environment(), expired, now)["evidence_status"], "evidence_expired_or_invalid")
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
        self.assertIn('"provider_connectivity_evidence_verified": false', output.getvalue())
        self.assertIn('"evidence_status": "not_provided"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
