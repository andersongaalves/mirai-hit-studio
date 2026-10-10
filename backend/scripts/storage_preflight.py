"""Sanitized storage configuration report and explicit rollout gate."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

_COMPONENTS = (
    "r2_private_temp",
    "r2_private_final",
    "cloudinary",
    "supabase_audio",
    "legacy_storage",
)
_SHA256 = re.compile(r"[a-f0-9]{64}")
_COMMIT_SHA = re.compile(r"[a-f0-9]{40}")
_CONFIG_KEYS = (
    "COMMERCIAL_PIPELINE_V2_ENABLED",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_ENDPOINT",
    "R2_REGION",
    "R2_PRESIGN_MAX_SECONDS",
    "R2_TEMP_BUCKET",
    "R2_FINAL_BUCKET",
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "PORTFOLIO_AUDIO_STORAGE_BUCKET",
    "PORTFOLIO_AUDIO_MAX_BYTES",
    "PRODUCAO_STORAGE_BUCKET",
    "SUPABASE_STORAGE_BUCKET",
    "PRODUCTION_TEMP_STORAGE_BACKEND",
    "PRODUCTION_FINAL_STORAGE_BACKEND",
    "PUBLIC_IMAGE_STORAGE_BACKEND",
    "PORTFOLIO_AUDIO_STORAGE_BACKEND",
    "PROPOSAL_DOCUMENT_STORAGE_BACKEND",
    "PROPOSTA_STORAGE_BACKEND",
)


def _https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


def _bucket(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", value or ""))


def _component(env, name, required, valid, backend=None, allowed_backends=None):
    present = all(bool(env.get(key, "").strip()) for key in required)
    report = {
        "configuration_present": present,
        "configuration_valid": bool(present and valid),
        "provider_accessible": "not_checked",
        "smoke": "not_run",
    }
    if allowed_backends is not None:
        report["write_backend"] = backend
        report["write_backend_valid"] = backend in allowed_backends
    return report


def _parse_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _configuration_fingerprint(env, key):
    effective_config = {name: env.get(name, "") for name in _CONFIG_KEYS}
    canonical = json.dumps(effective_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


def _verify_evidence(env, evidence, now=None):
    """Verify a protected-process HMAC attestation; never trust status env vars."""
    if not isinstance(evidence, dict):
        return False, "not_provided"

    key = env.get("STORAGE_PREFLIGHT_EVIDENCE_HMAC_KEY", "")
    signature = evidence.get("signature")
    if len(key.encode("utf-8")) < 32 or not isinstance(signature, str):
        return False, "signature_missing"

    unsigned = {name: value for name, value in evidence.items() if name != "signature"}
    try:
        canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        return False, "invalid_document"
    expected_signature = hmac.new(key.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return False, "signature_invalid"

    if evidence.get("schema_version") != 1:
        return False, "schema_invalid"
    target_sha = env.get("GITHUB_SHA", "").lower()
    if (
        not _COMMIT_SHA.fullmatch(target_sha)
        or evidence.get("target_sha") != target_sha
    ):
        return False, "target_sha_mismatch"
    if evidence.get("configuration_fingerprint") != _configuration_fingerprint(env, key):
        return False, "configuration_mismatch"

    repository = env.get("GITHUB_REPOSITORY", "")
    allowed_verifiers = {
        f"{repository}/.github/workflows/storage-provider-rollout.yml@refs/heads/main",
        f"{repository}/.github/workflows/storage-publication-gate.yml@refs/heads/main",
        f"{repository}/.github/workflows/production-release.yml@refs/heads/main",
    }
    if (
        env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_WORKFLOW_REF") not in allowed_verifiers
        or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
    ):
        return False, "untrusted_verification_context"
    run = evidence.get("workflow_run")
    if not isinstance(run, dict):
        return False, "workflow_run_missing"
    run_id = run.get("id")
    run_url = run.get("url")
    parsed_url = urlsplit(run_url) if isinstance(run_url, str) else None
    if (
        not repository
        or not isinstance(run_id, str)
        or not re.fullmatch(r"[1-9][0-9]*", run_id)
        or (
            bool(env.get("STORAGE_PREFLIGHT_EXPECTED_ISSUER_RUN_ID"))
            and run_id != env.get("STORAGE_PREFLIGHT_EXPECTED_ISSUER_RUN_ID")
        )
        or parsed_url is None
        or parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
        or parsed_url.path != f"/{repository}/actions/runs/{run_id}"
        or parsed_url.query
        or parsed_url.fragment
        or not isinstance(run.get("actor"), str)
        or not run["actor"].strip()
        or run.get("workflow_ref")
        != f"{repository}/.github/workflows/storage-provider-rollout.yml@refs/heads/main"
        or not isinstance(run.get("authorization_ref"), str)
        or not run["authorization_ref"].strip()
    ):
        return False, "workflow_run_invalid"

    issued_at = _parse_timestamp(evidence.get("issued_at"))
    expires_at = _parse_timestamp(evidence.get("expires_at"))
    current_time = now or datetime.now(timezone.utc)
    if (
        issued_at is None
        or expires_at is None
        or issued_at > current_time + timedelta(minutes=5)
        or expires_at <= current_time
        or expires_at <= issued_at
        or expires_at - issued_at > timedelta(hours=4)
    ):
        return False, "evidence_expired_or_invalid"

    components = evidence.get("components")
    if not isinstance(components, dict) or set(components) != set(_COMPONENTS):
        return False, "component_evidence_incomplete"
    for component in components.values():
        if (
            not isinstance(component, dict)
            or component.get("connectivity") != "passed"
            or component.get("smoke") != "passed"
            or not isinstance(component.get("evidence_sha256"), str)
            or not _SHA256.fullmatch(component["evidence_sha256"])
        ):
            return False, "component_evidence_invalid"
    return True, "verified"


def build_report(environ=None, evidence=None, now=None):
    env = environ if environ is not None else os.environ
    account_id = env.get("R2_ACCOUNT_ID", "").strip().lower()
    endpoint = (env.get("R2_ENDPOINT", "").strip() or f"https://{account_id}.r2.cloudflarestorage.com").rstrip("/")
    r2_valid = (
        bool(re.fullmatch(r"[a-f0-9]{32}", account_id))
        and bool(env.get("R2_ACCESS_KEY_ID", "").strip())
        and bool(env.get("R2_SECRET_ACCESS_KEY", ""))
        and endpoint == f"https://{account_id}.r2.cloudflarestorage.com"
    )
    supabase_url = env.get("SUPABASE_URL", "").strip()
    supabase_key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_valid = _https_url(supabase_url) and bool(supabase_key)
    temp_backend = env.get("PRODUCTION_TEMP_STORAGE_BACKEND", "r2").strip().lower()
    final_backend = env.get("PRODUCTION_FINAL_STORAGE_BACKEND", "r2").strip().lower()
    cloudinary_name = env.get("CLOUDINARY_CLOUD_NAME", "").strip()

    components = {
        "r2_private_temp": _component(
            env,
            "R2_TEMP",
            ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_TEMP_BUCKET"),
            r2_valid and _bucket(env.get("R2_TEMP_BUCKET", "").strip()),
            temp_backend,
            {"r2", "supabase"},
        ),
        "r2_private_final": _component(
            env,
            "R2_FINAL",
            ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_FINAL_BUCKET"),
            r2_valid and _bucket(env.get("R2_FINAL_BUCKET", "").strip()),
            final_backend,
            {"r2", "supabase"},
        ),
        "cloudinary": _component(
            env,
            "CLOUDINARY",
            ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"),
            bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", cloudinary_name))
            and bool(env.get("CLOUDINARY_API_KEY", "").strip())
            and bool(env.get("CLOUDINARY_API_SECRET", "")),
            env.get("PUBLIC_IMAGE_STORAGE_BACKEND", "cloudinary").strip().lower(),
            {"cloudinary"},
        ),
        "supabase_audio": _component(
            env,
            "SUPABASE_AUDIO",
            ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"),
            supabase_valid
            and _bucket(env.get("PORTFOLIO_AUDIO_STORAGE_BUCKET", "portfolio-audio").strip()),
            env.get("PORTFOLIO_AUDIO_STORAGE_BACKEND", "supabase").strip().lower(),
            {"supabase"},
        ),
        "legacy_storage": _component(
            env,
            "LEGACY_STORAGE",
            ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "PROPOSTA_STORAGE_BACKEND"),
            supabase_valid
            and env.get("PROPOSTA_STORAGE_BACKEND", "local").strip().lower() == "supabase"
            and _bucket(env.get("PRODUCAO_STORAGE_BUCKET", "producao-arquivos").strip())
            and _bucket(env.get("SUPABASE_STORAGE_BUCKET", "propostas-pdf").strip()),
            env.get("PROPOSAL_DOCUMENT_STORAGE_BACKEND", "legacy").strip().lower(),
            {"legacy"},
        ),
    }
    evidence_valid, evidence_status = _verify_evidence(env, evidence, now=now)
    if evidence_valid:
        for component_name, component_evidence in evidence["components"].items():
            components[component_name]["provider_accessible"] = "verified_from_evidence"
            components[component_name]["smoke"] = "passed_with_evidence"
            components[component_name]["evidence_sha256"] = component_evidence["evidence_sha256"]

    v2 = env.get("COMMERCIAL_PIPELINE_V2_ENABLED")
    ready = (
        v2 == "false"
        and evidence_valid
        and all(
            component["configuration_valid"]
            and component.get("write_backend_valid", True)
            and component["provider_accessible"] == "verified_from_evidence"
            and component["smoke"] == "passed_with_evidence"
            for component in components.values()
        )
    )
    return {
        "components": components,
        "commercial_pipeline_v2": "off" if v2 == "false" else "not_confirmed_off",
        "provider_connectivity_probed": False,
        "provider_connectivity_evidence_verified": evidence_valid,
        "evidence_status": evidence_status,
        "rollout_ready": ready,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-rollout-ready",
        action="store_true",
        help="exit nonzero unless config, signed provider evidence and V2-off gates pass",
    )
    parser.add_argument(
        "--evidence",
        default=os.environ.get("STORAGE_PREFLIGHT_EVIDENCE_PATH"),
        help="path to the sanitized, HMAC-signed provider smoke evidence document",
    )
    args = parser.parse_args(argv)
    evidence = None
    if args.evidence:
        try:
            with open(args.evidence, encoding="utf-8") as evidence_file:
                evidence = json.load(evidence_file)
        except (OSError, json.JSONDecodeError):
            evidence = None
    report = build_report(evidence=evidence)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["rollout_ready"] or not args.require_rollout_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
