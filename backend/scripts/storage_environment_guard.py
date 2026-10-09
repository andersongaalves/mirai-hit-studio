"""Read-only guard for protected GitHub deployment environments."""

from __future__ import annotations

import argparse
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def _reviewer_login(entry: object) -> str:
    if not isinstance(entry, dict) or entry.get("type") != "User":
        return ""
    reviewer = entry.get("reviewer")
    if isinstance(reviewer, dict):
        return str(reviewer.get("login", "")).lower()
    return str(entry.get("login", "")).lower()


def protection_status(
    environment: object,
    branch_policies: object,
    *,
    solo_admin_reviewer: str | None = None,
) -> str:
    if not isinstance(environment, dict) or not isinstance(branch_policies, dict):
        return "environment_or_branch_policy_missing"
    if environment.get("can_admins_bypass") is not False:
        return "administrator_bypass_not_disabled"

    rules = environment.get("protection_rules")
    if not isinstance(rules, list):
        return "required_reviewers_missing"
    reviewer_rules = [rule for rule in rules if isinstance(rule, dict) and rule.get("type") == "required_reviewers"]
    if solo_admin_reviewer:
        expected = solo_admin_reviewer.lower()
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,37}[a-z0-9])?", expected):
            return "authorized_reviewer_invalid"
        matching_rules = [
            rule
            for rule in reviewer_rules
            if rule.get("prevent_self_review") is False
            and isinstance(rule.get("reviewers"), list)
            and [_reviewer_login(entry) for entry in rule["reviewers"]] == [expected]
        ]
        if len(matching_rules) != 1 or len(reviewer_rules) != 1:
            return "solo_admin_reviewer_mismatch"
    elif not any(
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


def main_protection_status(protection: object, *, required_check: str) -> str:
    if not isinstance(protection, dict):
        return "main_protection_missing"
    reviews = protection.get("required_pull_request_reviews")
    if not isinstance(reviews, dict):
        return "pull_request_not_required"
    if reviews.get("required_approving_review_count") not in {None, 0}:
        return "human_pr_review_unexpected"

    checks = protection.get("required_status_checks")
    if not isinstance(checks, dict) or checks.get("strict") is not True:
        return "required_ci_missing"
    contexts = {
        item
        for item in checks.get("contexts", [])
        if isinstance(item, str)
    }
    contexts.update(
        item.get("context")
        for item in checks.get("checks", [])
        if isinstance(item, dict) and isinstance(item.get("context"), str)
    )
    if required_check not in contexts:
        return "required_ci_missing"
    if (protection.get("enforce_admins") or {}).get("enabled") is not True:
        return "administrator_rules_not_enforced"
    if (protection.get("allow_force_pushes") or {}).get("enabled") is not False:
        return "force_push_not_blocked"
    if (protection.get("allow_deletions") or {}).get("enabled") is not False:
        return "branch_deletion_not_blocked"
    return "protected"


def ruleset_main_protection_status(ruleset: object, *, required_check: str) -> str:
    if not isinstance(ruleset, dict) or ruleset.get("target") != "branch":
        return "main_protection_missing"
    if ruleset.get("enforcement") != "active":
        return "main_protection_disabled"

    conditions = ruleset.get("conditions")
    ref_name = conditions.get("ref_name") if isinstance(conditions, dict) else None
    if (
        not isinstance(ref_name, dict)
        or ref_name.get("include") != ["refs/heads/main"]
        or ref_name.get("exclude") != []
    ):
        return "main_ruleset_scope_not_main_only"
    if (
        ruleset.get("bypass_actors") != []
        or ruleset.get("current_user_can_bypass") not in {None, "never"}
    ):
        return "administrator_rules_not_enforced"

    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        return "main_protection_missing"
    by_type = {
        rule.get("type"): rule
        for rule in rules
        if isinstance(rule, dict) and isinstance(rule.get("type"), str)
    }
    reviews = by_type.get("pull_request")
    if not isinstance(reviews, dict):
        return "pull_request_not_required"
    review_parameters = reviews.get("parameters")
    if not isinstance(review_parameters, dict):
        return "pull_request_not_required"
    if review_parameters.get("required_approving_review_count") not in {None, 0}:
        return "human_pr_review_unexpected"

    checks = by_type.get("required_status_checks")
    check_parameters = checks.get("parameters") if isinstance(checks, dict) else None
    if not isinstance(check_parameters, dict):
        return "required_ci_missing"
    contexts = {
        item.get("context")
        for item in check_parameters.get("required_status_checks", [])
        if isinstance(item, dict) and isinstance(item.get("context"), str)
    }
    if required_check not in contexts:
        return "required_ci_missing"
    if "non_fast_forward" not in by_type:
        return "force_push_not_blocked"
    if "deletion" not in by_type:
        return "branch_deletion_not_blocked"
    return "protected"


def _get_json(url: str, token: str) -> object:
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
    if not isinstance(payload, (dict, list)):
        raise TypeError("invalid_response")
    return payload


def _valid_request(api_url: str, repository: str, token: str) -> bool:
    parsed = urlsplit(api_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        return False
    return bool(token)


def check_environment(
    api_url: str,
    repository: str,
    name: str,
    token: str,
    *,
    solo_admin_reviewer: str | None = None,
) -> str:
    if not _valid_request(api_url, repository, token):
        return "request_configuration_invalid"
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,49}", name):
        return "request_configuration_invalid"

    base = f"{api_url.rstrip('/')}/repos/{repository}/environments/{quote(name, safe='')}"
    try:
        environment = _get_json(base, token)
        policies = _get_json(base + "/deployment-branch-policies", token)
    except HTTPError as error:
        return "environment_not_found" if error.code == 404 else "github_api_unavailable"
    except (URLError, TimeoutError, OSError, ValueError, TypeError):
        return "github_api_unavailable"
    return protection_status(
        environment,
        policies,
        solo_admin_reviewer=solo_admin_reviewer,
    )


def check_main_protection(
    api_url: str,
    repository: str,
    token: str,
    *,
    ruleset_token: str | None = None,
    required_check: str,
    ruleset_name: str = "mirai-main-protection",
) -> str:
    if (
        not _valid_request(api_url, repository, token)
        or not required_check
        or not ruleset_name
    ):
        return "request_configuration_invalid"
    base = f"{api_url.rstrip('/')}/repos/{repository}"
    try:
        protection = _get_json(base + "/branches/main/protection", token)
    except HTTPError as error:
        if error.code not in {403, 404}:
            return "github_api_unavailable"
    except (URLError, TimeoutError, OSError, ValueError, TypeError):
        return "github_api_unavailable"
    else:
        if main_protection_status(protection, required_check=required_check) == "protected":
            return "protected"

    ruleset_credential = ruleset_token or ""
    if not _valid_request(api_url, repository, ruleset_credential):
        return "ruleset_credential_missing"

    try:
        rulesets = _get_json(
            base + "/rulesets?includes_parents=true&targets=branch",
            ruleset_credential,
        )
        if not isinstance(rulesets, list):
            return "github_api_unavailable"
        matches = [
            item
            for item in rulesets
            if isinstance(item, dict) and item.get("name") == ruleset_name
        ]
        if len(matches) != 1 or not isinstance(matches[0].get("id"), int):
            return "main_protection_missing"
        ruleset = _get_json(
            base + f"/rulesets/{matches[0]['id']}",
            ruleset_credential,
        )
    except HTTPError as error:
        return "main_protection_missing" if error.code == 404 else "github_api_unavailable"
    except (URLError, TimeoutError, OSError, ValueError, TypeError):
        return "github_api_unavailable"
    return ruleset_main_protection_status(ruleset, required_check=required_check)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", action="append", required=True)
    parser.add_argument("--solo-admin-reviewer")
    parser.add_argument("--require-main-protection", action="store_true")
    parser.add_argument("--required-check", default="storage-integration")
    parser.add_argument("--main-ruleset", default="mirai-main-protection")
    args = parser.parse_args(argv)
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    token = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
    ruleset_token = os.environ.get("GH_RULESET_TOKEN", "")
    results = {
        name: check_environment(
            api_url,
            repository,
            name,
            token,
            solo_admin_reviewer=args.solo_admin_reviewer,
        )
        for name in args.environment
    }
    main_status = None
    if args.require_main_protection:
        main_status = check_main_protection(
            api_url,
            repository,
            token,
            ruleset_token=ruleset_token,
            required_check=args.required_check,
            ruleset_name=args.main_ruleset,
        )
    report = {"environments": results}
    if main_status is not None:
        report["main"] = main_status
    print(json.dumps(report, sort_keys=True))
    ready = all(status == "protected" for status in results.values())
    if main_status is not None:
        ready = ready and main_status == "protected"
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
