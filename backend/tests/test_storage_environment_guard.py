import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from scripts.storage_environment_guard import check_environment, main, protection_status


def protected_environment():
    return {
        "can_admins_bypass": False,
        "protection_rules": [{
            "type": "required_reviewers",
            "prevent_self_review": True,
            "reviewers": [{"type": "User"}],
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


if __name__ == "__main__":
    unittest.main()
