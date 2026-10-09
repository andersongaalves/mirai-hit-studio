import unittest
from pathlib import Path


class ProductionReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parents[2]
            / ".github"
            / "workflows"
            / "production-release.yml"
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

    def test_storage_preflight_and_v2_off_are_mandatory(self):
        self.assertIn("--require-rollout-ready", self.source)
        self.assertIn("COMMERCIAL_PIPELINE_V2_ENABLED", self.source)
        self.assertNotIn("COMMERCIAL_PIPELINE_V2_ENABLED: true", self.source)


if __name__ == "__main__":
    unittest.main()
