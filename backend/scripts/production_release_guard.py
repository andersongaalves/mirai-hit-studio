"""Fail-closed validation helpers for the protected production release workflow."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^[1-9][0-9]*$")


def validate_request(context: dict, *, target_sha: str, workflow_path: str) -> str:
    if not SHA_RE.fullmatch(target_sha):
        return "target_sha_invalid"
    expected_ref = f"{context.get('repository')}/{workflow_path}@refs/heads/main"
    checks = (
        (context.get("event_name") == "workflow_dispatch", "event_not_manual"),
        (context.get("ref") == "refs/heads/main", "ref_not_main"),
        (context.get("sha") == target_sha, "target_sha_mismatch"),
        (context.get("workflow_ref") == expected_ref, "workflow_source_untrusted"),
    )
    for passed, error in checks:
        if not passed:
            return error
    return "trusted"


def validate_workflow_run(
    run: dict,
    *,
    run_id: str,
    target_sha: str,
    workflow_path: str,
    allowed_events: tuple[str, ...],
) -> str:
    if not RUN_ID_RE.fullmatch(run_id):
        return "run_id_invalid"
    expected = {
        "id": int(run_id),
        "head_sha": target_sha,
        "head_branch": "main",
        "status": "completed",
        "conclusion": "success",
        "path": workflow_path,
    }
    for field, value in expected.items():
        if run.get(field) != value:
            return f"run_{field}_mismatch"
    if run.get("event") not in allowed_events:
        return "run_event_mismatch"
    return "verified"


def validate_render_service(service: dict, *, service_id: str) -> str:
    if not service_id or service.get("id") != service_id:
        return "render_service_mismatch"
    details = service.get("serviceDetails") or {}
    branch = service.get("branch", details.get("branch"))
    auto_deploy = service.get("autoDeploy", details.get("autoDeploy"))
    if branch != "main":
        return "render_branch_not_main"
    if auto_deploy not in {"no", False}:
        return "render_auto_deploy_not_disabled"
    return "verified"


def validate_cloudflare_project(project: dict, *, project_name: str) -> str:
    if project.get("name") != project_name:
        return "cloudflare_project_mismatch"
    source_config = ((project.get("source") or {}).get("config") or {})
    if project.get("production_branch") != "main" and source_config.get("production_branch") != "main":
        return "cloudflare_branch_not_main"
    if source_config.get("production_deployments_enabled") is not False:
        return "cloudflare_auto_deploy_not_disabled"
    return "verified"


def build_report(
    *,
    context: dict,
    target_sha: str,
    workflow_path: str,
    integration_run: dict,
    integration_run_id: str,
    issuer_run: dict,
    issuer_run_id: str,
    render_service: dict | None = None,
    render_service_id: str = "",
    cloudflare_project: dict | None = None,
    cloudflare_project_name: str = "mirai-hit-studio",
    require_provider_state: bool = False,
) -> dict:
    statuses = {
        "request": validate_request(context, target_sha=target_sha, workflow_path=workflow_path),
        "integration_ci": validate_workflow_run(
            integration_run,
            run_id=integration_run_id,
            target_sha=target_sha,
            workflow_path=".github/workflows/storage-integration-gate.yml",
            allowed_events=("push", "workflow_dispatch"),
        ),
        "storage_evidence_issuer": validate_workflow_run(
            issuer_run,
            run_id=issuer_run_id,
            target_sha=target_sha,
            workflow_path=".github/workflows/storage-provider-rollout.yml",
            allowed_events=("workflow_dispatch",),
        ),
    }
    if require_provider_state:
        statuses["render"] = validate_render_service(
            render_service or {}, service_id=render_service_id
        )
        statuses["cloudflare_pages"] = validate_cloudflare_project(
            cloudflare_project or {}, project_name=cloudflare_project_name
        )
    ready = all(value in {"trusted", "verified"} for value in statuses.values())
    return {"target_sha": target_sha, "statuses": statuses, "release_ready": ready}


def _load(path: str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--integration-run", required=True)
    parser.add_argument("--integration-run-id", required=True)
    parser.add_argument("--issuer-run", required=True)
    parser.add_argument("--issuer-run-id", required=True)
    parser.add_argument("--workflow-path", default=".github/workflows/production-release.yml")
    parser.add_argument("--render-service")
    parser.add_argument("--render-service-id", default="")
    parser.add_argument("--cloudflare-project")
    parser.add_argument("--cloudflare-project-name", default="mirai-hit-studio")
    parser.add_argument("--require-provider-state", action="store_true")
    args = parser.parse_args(argv)

    report = build_report(
        context=_load(args.context),
        target_sha=args.target_sha,
        workflow_path=args.workflow_path,
        integration_run=_load(args.integration_run),
        integration_run_id=args.integration_run_id,
        issuer_run=_load(args.issuer_run),
        issuer_run_id=args.issuer_run_id,
        render_service=_load(args.render_service) if args.render_service else None,
        render_service_id=args.render_service_id,
        cloudflare_project=_load(args.cloudflare_project) if args.cloudflare_project else None,
        cloudflare_project_name=args.cloudflare_project_name,
        require_provider_state=args.require_provider_state,
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
