import hashlib
import unittest
from pathlib import Path


class ProductionReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        cls.source = (
            root
            / ".github"
            / "workflows"
            / "production-release.yml"
        ).read_text(encoding="utf-8")
        cls.integration_source = (
            root
            / ".github"
            / "workflows"
            / "storage-integration-gate.yml"
        ).read_text(encoding="utf-8")
        cls.guard_path = root / "backend" / "scripts" / "production_release_guard.py"
        cls.issuer_source = (
            root / ".github" / "workflows" / "storage-provider-rollout.yml"
        ).read_text(encoding="utf-8")
        cls.preflight_source = (
            root / ".github" / "workflows" / "storage-publication-gate.yml"
        ).read_text(encoding="utf-8")

    def test_release_is_manual_serial_and_main_bound(self):
        self.assertIn("workflow_dispatch:", self.source)
        self.assertNotIn("pull_request:", self.source)
        self.assertNotIn("\n  push:", self.source)
        self.assertIn("group: protected-production-release", self.source)
        self.assertIn("cancel-in-progress: false", self.source)
        self.assertIn("github.ref == 'refs/heads/main'", self.source)
        self.assertIn('test "$TARGET_SHA" = "$GITHUB_SHA"', self.source)

    def test_deploy_requires_protected_environments_and_provider_readiness(self):
        for environment in (
            "storage-rollout",
            "render-production",
            "cloudflare-pages-production",
        ):
            self.assertIn(f"environment: {environment}", self.source)
            self.assertIn(f"--environment {environment}", self.source)
        self.assertIn('--solo-admin-reviewer "$GITHUB_REPOSITORY_OWNER"', self.source)
        self.assertIn("--require-main-protection", self.source)
        self.assertIn("--required-check storage-integration", self.source)
        guard = Path(__file__).resolve().parents[1].joinpath(
            "scripts/production_release_guard.py"
        ).read_text(encoding="utf-8")
        self.assertIn("render_auto_deploy_not_disabled", guard)
        self.assertIn("cloudflare_auto_deploy_not_disabled", guard)
        self.assertIn("needs: [render-readiness, cloudflare-readiness]", self.source)

    def test_dry_run_has_no_deployment_api_or_provider_credentials(self):
        start = self.source.index("  dry-run:")
        end = self.source.index("  render-readiness:")
        dry_run = self.source[start:end]
        self.assertNotIn("RENDER_API_KEY", dry_run)
        self.assertNotIn("CLOUDFLARE_API_TOKEN", dry_run)
        self.assertNotIn("api.render.com", dry_run)
        self.assertNotIn("wrangler", dry_run)

    def test_plan_only_has_no_environment_secret_provider_or_deploy_access(self):
        start = self.source.index("  plan-only:")
        end = self.source.index("  verify-storage-evidence:")
        plan = self.source[start:end]
        self.assertNotIn("environment:", plan)
        self.assertNotIn("secrets.", plan)
        self.assertNotIn("RENDER_API_KEY", plan)
        self.assertNotIn("CLOUDFLARE_API_TOKEN", plan)
        self.assertNotIn("storage_preflight", plan)
        self.assertIn("SIMULATION ONLY", plan)
        self.assertIn("does not authorize publication", plan)

    def test_storage_preflight_and_v2_off_are_mandatory(self):
        self.assertIn("--require-rollout-ready", self.source)
        self.assertIn("COMMERCIAL_PIPELINE_V2_ENABLED", self.source)
        self.assertNotIn("COMMERCIAL_PIPELINE_V2_ENABLED: true", self.source)

    def test_optional_storage_settings_keep_the_application_defaults(self):
        for source in (self.source, self.issuer_source, self.preflight_source):
            self.assertIn("vars.R2_PRESIGN_MAX_SECONDS || '900'", source)
            self.assertIn("vars.PROPOSAL_DOCUMENT_STORAGE_BACKEND || 'legacy'", source)

    def test_integration_ci_runs_on_main_but_release_rejects_branch_evidence(self):
        self.assertIn(
            "branches: [main, phase/3.8-integration-gate]", self.integration_source
        )
        self.assertIn("pull_request:", self.integration_source)
        self.assertIn("branches: [main]", self.integration_source)
        self.assertIn('test "$GITHUB_BASE_REF" = "main"', self.integration_source)
        self.assertIn(
            "main|phase/3.8-integration-gate", self.integration_source
        )
        self.assertIn('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"', self.integration_source)
        guard = Path(__file__).resolve().parents[1].joinpath(
            "scripts/production_release_guard.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"head_branch": "main"', guard)
        self.assertIn('allowed_events=("workflow_dispatch",)', guard)

    def test_render_readiness_requires_effective_v2_off(self):
        self.assertIn(
            "/env-vars/COMMERCIAL_PIPELINE_V2_ENABLED", self.source
        )
        self.assertIn("validate_render_v2_environment", self.source)

    def test_hmac_issuer_and_preflight_require_solo_admin_main_protection(self):
        for source in (self.issuer_source, self.preflight_source):
            self.assertIn('--solo-admin-reviewer "$GITHUB_REPOSITORY_OWNER"', source)
            self.assertIn("--require-main-protection", source)
            self.assertIn("--required-check storage-integration", source)
        self.assertIn("github.ref == 'refs/heads/main'", self.issuer_source)

    def test_release_guard_source_pin_matches_the_reviewed_script(self):
        digest = hashlib.sha256(self.guard_path.read_bytes()).hexdigest()
        self.assertIn(f"RELEASE_GUARD_SHA256: {digest}", self.source)


if __name__ == "__main__":
    unittest.main()
