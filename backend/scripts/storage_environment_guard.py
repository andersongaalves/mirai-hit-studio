"""Read-only guard for protected GitHub deployment environments."""

from __future__ import annotations

import argparse
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def protection_status(environment: object, branch_policies: object) -> str:
    if not isinstance(environment, dict) or not isinstance(branch_policies, dict):
        return "environment_or_branch_policy_missing"
    if environment.get("can_admins_bypass") is not False:
        return "administrator_bypass_not_disabled"

    rules = environment.get("protection_rules")
    if not isinstance(rules, list):
        return "required_reviewers_missing"
    reviewer_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("type") == "required_reviewers"]
    if not any(
        isinstance(rule.get("reviewers"), list)
        and len(rule["reviewers"]) > 0
        and rule.get("prevent_self_review") is True
        for rule in reviewer_rules
    ):
        return "required_reviewers_missing"

    branch_policy = environment.get("deployment_branch_policy")
    policies = branch_policies.get("branch_policies")
    if (
        not isinstance(branch_policy, dict)
        or branch_policy.get("custom_branch_policies") is not True
        or branch_policy.get("protected_branches") is not False
        or not isinstance(policies, list)
        or len(policies) != 1
        or not isinstance(policies[0], dict)
        or policies[0].get("name") != "main"
    ):
        return "deployment_branch_policy_not_main_only"
    return "protected"


def _get_json(url: str, token: str) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise TypeError("invalid_response")
    return payload


def check_environment(api_url: str, repository: str, name: str, token: str) -> str:
    parsed = urlsplit(api_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return "api_url_invalid"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        return "repository_invalid"
    if not token or not re.fullmatch(r"[a-z][a-z0-9-]{1,49}", name):
        return "request_configuration_invalid"

    base = f"{api_url.rstrip('/')}/repos/{repository}/environments/{quote(name, safe='')}"
    try:
        environment = _get_json(base, token)
        policies = _get_json(base + "/deployment-branch-policies", token)
    except HTTPError as error:
        return "environment_not_found" if error.code == 404 else "github_api_unavailable"
    except (URLError, TimeoutError, OSError, ValueError, TypeError):
        return "github_api_unavailable"
    return protection_status(environment, policies)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", action="append", required=True)
    args = parser.parse_args(argv)
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    token = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
    results = {
        name: check_environment(api_url, repository, name, token)
        for name in args.environment
    }
    print(json.dumps({"environments": results}, sort_keys=True))
    return 0 if all(status == "protected" for status in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
