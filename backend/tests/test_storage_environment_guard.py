import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from scripts.storage_environment_guard import (
    check_environment,
    main,
    main_protection_status,
    protection_status,
)


def protected_environment():
    return {
        "can_admins_bypass": False,
        "protection_rules": [{
            "type": "required_reviewers",
            "prevent_self_review": True,
            "reviewers": [{
                "type": "User",
                "reviewer": {"login": "andersongaalves"},
            }],
        }],
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
    }


class StorageEnvironmentGuardTests(unittest.TestCase):
    def test_requires_reviewer_self_review_bypass_and_main_only(self):
        environment = protected_environment()
        policies = {"branch_policies": [{"name": "main"}]}
        self.assertEqual(protection_status(environment, policies), "protected")

        changed = protected_environment()
        changed["can_admins_bypass"] = True
        self.assertEqual(
            protection_status(changed, policies),
            "administrator_bypass_not_disabled",
        )
        changed = protected_environment()
        changed["protection_rules"][0]["prevent_self_review"] = False
        self.assertEqual(
            protection_status(changed, policies),
            "required_reviewers_missing",
        )
        self.assertEqual(
            protection_status(environment, {"branch_policies": [{"name": "main"}, {"name": "release/*"}]}),
            "deployment_branch_policy_not_main_only",
        )

    def test_solo_admin_requires_exact_authorized_reviewer_and_self_review(self):
        environment = protected_environment()
        environment["protection_rules"][0]["prevent_self_review"] = False
        policies = {"branch_policies": [{"name": "main"}]}
        self.assertEqual(
            protection_status(
                environment,
                policies,
                solo_admin_reviewer="andersongaalves",
            ),
            "protected",
        )

        environment["protection_rules"][0]["reviewers"][0]["reviewer"]["login"] = "other-user"
        self.assertEqual(
            protection_status(
                environment,
                policies,
                solo_admin_reviewer="andersongaalves",
            ),
            "solo_admin_reviewer_mismatch",
        )

        environment = protected_environment()
        environment["protection_rules"][0]["prevent_self_review"] = False
        environment["protection_rules"][0]["reviewers"].append({
            "type": "User",
            "reviewer": {"login": "other-user"},
        })
        self.assertEqual(
            protection_status(
                environment,
                policies,
                solo_admin_reviewer="andersongaalves",
            ),
            "solo_admin_reviewer_mismatch",
        )

        environment = protected_environment()
        self.assertEqual(
            protection_status(
                environment,
                policies,
                solo_admin_reviewer="andersongaalves",
            ),
            "solo_admin_reviewer_mismatch",
        )

    def test_solo_admin_still_rejects_bypass_or_unprotected_environment(self):
        environment = protected_environment()
        environment["protection_rules"][0]["prevent_self_review"] = False
        environment["can_admins_bypass"] = True
        self.assertEqual(
            protection_status(
                environment,
                {"branch_policies": [{"name": "main"}]},
                solo_admin_reviewer="andersongaalves",
            ),
            "administrator_bypass_not_disabled",
        )
        environment["can_admins_bypass"] = False
        environment["protection_rules"] = []
        self.assertEqual(
            protection_status(
                environment,
                {"branch_policies": [{"name": "main"}]},
                solo_admin_reviewer="andersongaalves",
            ),
            "solo_admin_reviewer_mismatch",
        )

    def test_main_protection_requires_pr_ci_admin_enforcement_and_no_destructive_push(self):
        protection = {
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "required_status_checks": {
                "strict": True,
                "contexts": ["storage-integration"],
                "checks": [],
            },
            "enforce_admins": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
        }
        self.assertEqual(
            main_protection_status(protection, required_check="storage-integration"),
            "protected",
        )
        changed = dict(protection, enforce_admins={"enabled": False})
        self.assertEqual(
            main_protection_status(changed, required_check="storage-integration"),
            "administrator_rules_not_enforced",
        )
        changed = dict(protection, allow_force_pushes={"enabled": True})
        self.assertEqual(
            main_protection_status(changed, required_check="storage-integration"),
            "force_push_not_blocked",
        )
        changed = dict(protection, allow_deletions={"enabled": True})
        self.assertEqual(
            main_protection_status(changed, required_check="storage-integration"),
            "branch_deletion_not_blocked",
        )
        changed = dict(
            protection,
            required_status_checks={"strict": True, "contexts": []},
        )
        self.assertEqual(
            main_protection_status(changed, required_check="storage-integration"),
            "required_ci_missing",
        )
        changed = dict(
            protection,
            required_pull_request_reviews={"required_approving_review_count": 1},
        )
        self.assertEqual(
            main_protection_status(changed, required_check="storage-integration"),
            "human_pr_review_unexpected",
        )

    def test_missing_environment_fails_closed_without_creating_it(self):
        from urllib.error import URLError

        with patch(
            "scripts.storage_environment_guard._get_json",
            side_effect=URLError("network detail"),
        ), redirect_stdout(StringIO()):
            self.assertEqual(
                main(["--environment", "storage-rollout"]),
                1,
            )

    def test_github_404_is_reported_as_missing_environment(self):
        from urllib.error import HTTPError

        with patch(
            "scripts.storage_environment_guard._get_json",
            side_effect=HTTPError("url", 404, "missing", {}, None),
        ):
            status = check_environment(
                "https://api.github.com",
                "andersongaalves/mirai-hit-studio",
                "storage-rollout",
                "test-token",
            )
        self.assertEqual(status, "environment_not_found")

    def test_non_reviewed_environment_is_never_accepted(self):
        output = StringIO()
        with patch.dict(
            "os.environ",
            {
                "GITHUB_REPOSITORY": "andersongaalves/mirai-hit-studio",
                "GITHUB_API_URL": "https://api.github.com",
                "GH_TOKEN": "test-token",
            },
            clear=True,
        ), patch(
            "scripts.storage_environment_guard._get_json",
            side_effect=[protected_environment(), {"branch_policies": []}],
        ), redirect_stdout(output):
            self.assertEqual(main(["--environment", "storage-rollout"]), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(
            report["environments"]["storage-rollout"],
            "deployment_branch_policy_not_main_only",
        )
        self.assertNotIn("test-token", output.getvalue())

    def test_environment_variable_cannot_replace_real_github_protection(self):
        output = StringIO()
        with patch.dict(
            "os.environ",
            {
                "GITHUB_REPOSITORY": "andersongaalves/mirai-hit-studio",
                "GITHUB_API_URL": "https://api.github.com",
                "GH_TOKEN": "test-token",
                "SOLO_ADMIN_APPROVED": "true",
            },
            clear=True,
        ), patch(
            "scripts.storage_environment_guard._get_json",
            side_effect=[
                {
                    "can_admins_bypass": True,
                    "protection_rules": [],
                    "deployment_branch_policy": None,
                },
                {"branch_policies": []},
            ],
        ), redirect_stdout(output):
            self.assertEqual(main([
                "--environment",
                "storage-rollout",
                "--solo-admin-reviewer",
                "andersongaalves",
            ]), 1)
        self.assertEqual(
            json.loads(output.getvalue())["environments"]["storage-rollout"],
            "administrator_bypass_not_disabled",
        )


if __name__ == "__main__":
    unittest.main()
