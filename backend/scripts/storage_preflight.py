"""Sanitized storage configuration report and explicit rollout gate."""

from __future__ import annotations

import argparse
import json
import os
import re
from urllib.parse import urlsplit


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
        "provider_accessible": "attested" if env.get(f"STORAGE_PREFLIGHT_{name}_ACCESSIBLE") == "true" else "not_checked",
        "smoke": "approved" if env.get(f"STORAGE_PREFLIGHT_{name}_SMOKE") == "approved" else "not_run",
    }
    if allowed_backends is not None:
        report["write_backend"] = backend
        report["write_backend_valid"] = backend in allowed_backends
    return report


def build_report(environ=None):
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
            ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"),
            supabase_valid
            and _bucket(env.get("PRODUCAO_STORAGE_BUCKET", "producao-arquivos").strip())
            and _bucket(env.get("SUPABASE_STORAGE_BUCKET", "propostas-pdf").strip()),
            env.get("PROPOSAL_DOCUMENT_STORAGE_BACKEND", "legacy").strip().lower(),
            {"legacy"},
        ),
    }
    v2 = env.get("COMMERCIAL_PIPELINE_V2_ENABLED")
    ready = (
        v2 == "false"
        and all(
            component["configuration_valid"]
            and component.get("write_backend_valid", True)
            and component["provider_accessible"] == "attested"
            and component["smoke"] == "approved"
            for component in components.values()
        )
    )
    return {
        "components": components,
        "commercial_pipeline_v2": "off" if v2 == "false" else "not_confirmed_off",
        "provider_connectivity_probed": False,
        "rollout_ready": ready,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-rollout-ready",
        action="store_true",
        help="exit nonzero unless config, provider attestations, smoke and V2-off gates pass",
    )
    args = parser.parse_args(argv)
    report = build_report()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["rollout_ready"] or not args.require_rollout_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
