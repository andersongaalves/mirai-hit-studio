import hashlib
import unittest
from datetime import datetime, timezone

from scripts.storage_evidence import build_signed_evidence
from scripts.storage_preflight import _COMPONENTS


class StorageEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "COMMERCIAL_PIPELINE_V2_ENABLED": "false",
            "R2_ACCOUNT_ID": "a" * 32,
            "R2_ACCESS_KEY_ID": "synthetic-r2-key",
            "R2_SECRET_ACCESS_KEY": "synthetic-r2-secret",
            "R2_TEMP_BUCKET": "private-temp",
            "R2_FINAL_BUCKET": "private-final",
            "CLOUDINARY_CLOUD_NAME": "mirai-test",
            "CLOUDINARY_API_KEY": "synthetic-cloudinary-key",
            "CLOUDINARY_API_SECRET": "synthetic-cloudinary-secret",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "synthetic-supabase-key",
            "PRODUCTION_TEMP_STORAGE_BACKEND": "r2",
            "PRODUCTION_FINAL_STORAGE_BACKEND": "r2",
            "PUBLIC_IMAGE_STORAGE_BACKEND": "cloudinary",
            "PORTFOLIO_AUDIO_STORAGE_BACKEND": "supabase",
            "PROPOSTA_STORAGE_BACKEND": "supabase",
            "PRODUCAO_STORAGE_BUCKET": "production-files",
            "SUPABASE_STORAGE_BUCKET": "propostas-pdf",
            "GITHUB_REPOSITORY": "andersongaalves/mirai-hit-studio",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_WORKFLOW_REF": "andersongaalves/mirai-hit-studio/.github/workflows/storage-provider-rollout.yml@refs/heads/main",
            "GITHUB_SHA": "a" * 40,
            "STORAGE_PREFLIGHT_TARGET_SHA": "a" * 40,
            "STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY": "synthetic-signing-key-for-tests-only-0001",
            "STORAGE_ROLLOUT_AUTHORIZATION_REF": "CTRL-test-authorization",
            "GITHUB_RUN_ID": "123456789",
            "GITHUB_ACTOR": "test-approver",
            "GITHUB_SERVER_URL": "https://github.com",
        }
        self.smoke = {
            "all_passed": True,
            "components": {
                name: {
                    "connectivity": "passed",
                    "smoke": "passed",
                    "evidence_sha256": hashlib.sha256(name.encode()).hexdigest(),
                }
                for name in _COMPONENTS
            },
        }

    def test_signature_is_emitted_only_for_complete_passed_smokes(self):
        evidence = build_signed_evidence(
            self.smoke,
            self.env,
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(evidence["target_sha"], self.env["GITHUB_SHA"])
        self.assertEqual(evidence["workflow_run"]["id"], self.env["GITHUB_RUN_ID"])
        self.assertEqual(len(evidence["signature"]), 64)
        self.assertNotIn(self.env["STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY"], str(evidence))
        self.assertEqual(
            evidence["expires_at"],
            "2026-01-01T02:00:00+00:00",
        )

    def test_signer_refuses_candidate_branch_sha_or_incomplete_evidence(self):
        for name, value in (
            ("GITHUB_REF", "refs/heads/feature/untrusted"),
            ("GITHUB_SHA", "b" * 40),
            ("GITHUB_WORKFLOW_REF", "attacker/workflow.yml@refs/heads/main"),
        ):
            changed = dict(self.env)
            changed[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_signed_evidence(self.smoke, changed)

        failed = dict(self.smoke, all_passed=False)
        with self.assertRaisesRegex(ValueError, "provider_smokes_not_passed"):
            build_signed_evidence(failed, self.env)
        incomplete = {"all_passed": True, "components": {}}
        with self.assertRaisesRegex(ValueError, "provider_smoke_evidence_incomplete"):
            build_signed_evidence(incomplete, self.env)
        legacy_only = {
            "all_passed": False,
            "selected_passed": True,
            "components": {"legacy_storage": self.smoke["components"]["legacy_storage"]},
        }
        with self.assertRaisesRegex(ValueError, "provider_smokes_not_passed"):
            build_signed_evidence(legacy_only, self.env)
        legacy_only["all_passed"] = True
        with self.assertRaisesRegex(ValueError, "provider_smoke_evidence_incomplete"):
            build_signed_evidence(legacy_only, self.env)
        disabled = dict(self.env, COMMERCIAL_PIPELINE_V2_ENABLED="true")
        with self.assertRaisesRegex(ValueError, "effective_configuration_not_ready"):
            build_signed_evidence(self.smoke, disabled)


if __name__ == "__main__":
    unittest.main()
