import unittest

from scripts.production_release_guard import build_report


class ProductionReleaseGuardTests(unittest.TestCase):
    SHA = "a" * 40
    WORKFLOW = ".github/workflows/production-release.yml"

    def context(self):
        return {
            "event_name": "workflow_dispatch",
            "ref": "refs/heads/main",
            "sha": self.SHA,
            "repository": "andersongaalves/mirai-hit-studio",
            "workflow_ref": (
                "andersongaalves/mirai-hit-studio/"
                ".github/workflows/production-release.yml@refs/heads/main"
            ),
        }

    def workflow_run(self, run_id, path, event="workflow_dispatch"):
        return {
            "id": int(run_id),
            "head_sha": self.SHA,
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
            "path": path,
            "event": event,
        }

    def report(self, **overrides):
        values = {
            "context": self.context(),
            "target_sha": self.SHA,
            "workflow_path": self.WORKFLOW,
            "integration_run": self.workflow_run("101", ".github/workflows/storage-integration-gate.yml"),
            "integration_run_id": "101",
            "issuer_run": self.workflow_run("202", ".github/workflows/storage-provider-rollout.yml"),
            "issuer_run_id": "202",
        }
        values.update(overrides)
        return build_report(**values)

    def test_exact_main_sha_and_successful_runs_are_required(self):
        self.assertTrue(self.report()["release_ready"])

        context = self.context()
        context["sha"] = "b" * 40
        report = self.report(context=context)
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["statuses"]["request"], "target_sha_mismatch")

        replay = self.workflow_run("202", ".github/workflows/storage-provider-rollout.yml")
        replay["head_sha"] = "b" * 40
        report = self.report(issuer_run=replay)
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["statuses"]["storage_evidence_issuer"], "run_head_sha_mismatch")

    def test_failed_or_wrong_workflow_run_is_rejected(self):
        failed = self.workflow_run("101", ".github/workflows/storage-integration-gate.yml")
        failed["conclusion"] = "failure"
        self.assertFalse(self.report(integration_run=failed)["release_ready"])

        wrong = self.workflow_run("101", ".github/workflows/other.yml")
        report = self.report(integration_run=wrong)
        self.assertEqual(report["statuses"]["integration_ci"], "run_path_mismatch")

    def test_only_main_ci_and_manual_main_hmac_issuer_are_accepted(self):
        branch_run = self.workflow_run(
            "101", ".github/workflows/storage-integration-gate.yml", event="push"
        )
        branch_run["head_branch"] = "phase/3.8-integration-gate"
        report = self.report(integration_run=branch_run)
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["statuses"]["integration_ci"], "run_head_branch_mismatch")

        main_push = self.workflow_run(
            "101", ".github/workflows/storage-integration-gate.yml", event="push"
        )
        self.assertTrue(self.report(integration_run=main_push)["release_ready"])

        issuer_push = self.workflow_run(
            "202", ".github/workflows/storage-provider-rollout.yml", event="push"
        )
        report = self.report(issuer_run=issuer_push)
        self.assertFalse(report["release_ready"])
        self.assertEqual(
            report["statuses"]["storage_evidence_issuer"], "run_event_mismatch"
        )

    def test_publish_requires_auto_deploy_disabled_in_both_providers(self):
        render = {"id": "srv-1", "branch": "main", "autoDeploy": "no"}
        cloudflare = {
            "name": "mirai-hit-studio",
            "production_branch": "main",
            "source": {"config": {"production_deployments_enabled": False}},
        }
        report = self.report(
            require_provider_state=True,
            render_service=render,
            render_service_id="srv-1",
            cloudflare_project=cloudflare,
        )
        self.assertTrue(report["release_ready"])

        render["autoDeploy"] = "yes"
        report = self.report(
            require_provider_state=True,
            render_service=render,
            render_service_id="srv-1",
            cloudflare_project=cloudflare,
        )
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["statuses"]["render"], "render_auto_deploy_not_disabled")

        render["autoDeploy"] = "no"
        cloudflare["source"]["config"]["production_deployments_enabled"] = True
        report = self.report(
            require_provider_state=True,
            render_service=render,
            render_service_id="srv-1",
            cloudflare_project=cloudflare,
        )
        self.assertFalse(report["release_ready"])
        self.assertEqual(
            report["statuses"]["cloudflare_pages"],
            "cloudflare_auto_deploy_not_disabled",
        )

    def test_provider_identity_and_main_branch_are_fail_closed(self):
        report = self.report(
            require_provider_state=True,
            render_service={"id": "wrong", "branch": "main", "autoDeploy": "no"},
            render_service_id="srv-1",
            cloudflare_project={
                "name": "wrong",
                "production_branch": "main",
                "source": {"config": {"production_deployments_enabled": False}},
            },
        )
        self.assertFalse(report["release_ready"])
        self.assertEqual(report["statuses"]["render"], "render_service_mismatch")
        self.assertEqual(report["statuses"]["cloudflare_pages"], "cloudflare_project_mismatch")


if __name__ == "__main__":
    unittest.main()
