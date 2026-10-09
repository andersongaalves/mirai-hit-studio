"""Create the short-lived HMAC envelope after trusted real-provider smokes."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from scripts.storage_preflight import (
    _COMPONENTS,
    _configuration_fingerprint,
    build_report,
)


def build_signed_evidence(smoke_report: object, env=None, now=None) -> dict:
    env = env if env is not None else os.environ
    repository = env.get("GITHUB_REPOSITORY", "")
    workflow_ref = f"{repository}/.github/workflows/storage-provider-rollout.yml@refs/heads/main"
    target_sha = env.get("GITHUB_SHA", "").lower()
    key = env.get("STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY", "")
    authorization_ref = env.get("STORAGE_ROLLOUT_AUTHORIZATION_REF", "")
    if (
        env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or env.get("GITHUB_WORKFLOW_REF") != workflow_ref
        or not re.fullmatch(r"[a-f0-9]{40}", target_sha)
        or env.get("STORAGE_PREFLIGHT_TARGET_SHA", "").lower() != target_sha
        or len(key.encode("utf-8")) < 32
        or not re.fullmatch(r"CTRL-[A-Za-z0-9._-]{3,100}", authorization_ref)
        or not re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ID", ""))
        or not env.get("GITHUB_ACTOR", "").strip()
    ):
        raise ValueError("trusted_signing_context_invalid")
    configuration = build_report(env)
    if (
        configuration["commercial_pipeline_v2"] != "off"
        or not all(
            component["configuration_valid"]
            and component.get("write_backend_valid", True)
            for component in configuration["components"].values()
        )
    ):
        raise ValueError("effective_configuration_not_ready")
    if not isinstance(smoke_report, dict) or smoke_report.get("all_passed") is not True:
        raise ValueError("provider_smokes_not_passed")
    results = smoke_report.get("components")
    if not isinstance(results, dict) or set(results) != set(_COMPONENTS):
        raise ValueError("provider_smoke_evidence_incomplete")
    components = {}
    for name, result in results.items():
        digest = result.get("evidence_sha256") if isinstance(result, dict) else None
        if (
            result.get("connectivity") != "passed"
            or result.get("smoke") != "passed"
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise ValueError("provider_smoke_failed")
        components[name] = {
            "connectivity": "passed",
            "smoke": "passed",
            "evidence_sha256": digest,
        }

    run_id = env["GITHUB_RUN_ID"]
    server_url = env.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    parsed = server_url == "https://github.com"
    if not parsed:
        raise ValueError("github_server_invalid")
    issued = now or datetime.now(timezone.utc)
    evidence = {
        "schema_version": 1,
        "target_sha": target_sha,
        "configuration_fingerprint": _configuration_fingerprint(env, key),
        "workflow_run": {
            "id": run_id,
            "url": f"{server_url}/{repository}/actions/runs/{run_id}",
            "actor": env["GITHUB_ACTOR"],
            "workflow_ref": workflow_ref,
            "authorization_ref": authorization_ref,
        },
        "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(hours=2)).isoformat(),
        "components": components,
    }
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    evidence["signature"] = hmac.new(key.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return evidence


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: python -m scripts.storage_evidence SMOKE_JSON OUTPUT_JSON", file=sys.stderr)
        return 2
    smoke_path, output_path = args
    try:
        with open(smoke_path, encoding="utf-8") as file:
            smoke_report = json.load(file)
        evidence = build_signed_evidence(smoke_report)
        with open(output_path, "x", encoding="utf-8") as file:
            json.dump(evidence, file, sort_keys=True)
    except (OSError, json.JSONDecodeError, ValueError):
        print("storage_evidence_signing=blocked", file=sys.stderr)
        return 1
    print("storage_evidence_signing=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
