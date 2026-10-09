"""Run bounded, run-scoped real Storage checks; never prints refs or URLs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import quote
from uuid import uuid4

import httpx

from services.documento_storage import SupabaseDocumentoStorage
from services.portfolio_audio_storage import SupabasePortfolioAudioStorage
from services.producao_arquivo_storage import SupabaseProducaoArquivoStorage
from services.storage.cloudinary import CloudinaryImageStorage
from services.storage.config import StorageSettings
from services.storage.contracts import StorageNotFound, StorageScope
from services.storage.registry import StorageRegistry

COMPONENTS = (
    "r2_private_temp",
    "r2_private_final",
    "cloudinary",
    "supabase_audio",
    "legacy_storage",
)
_PDF = b"%PDF-1.7\nMirai synthetic storage smoke\n%%EOF\n"
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b49444154789c636000020000050001a5f645400000000049454e44ae426082"
)
_MP3 = (bytes((0xFF, 0xFB, 0x90, 0x64)) + bytes(413)) * 3


def _uuid(value: str):
    return SimpleNamespace(hex=value)


def _assert_bucket(storage, *, public: bool) -> None:
    response = storage._request(
        "GET", "bucket/" + quote(storage.bucket, safe="")
    )
    if response.status_code != 200:
        raise RuntimeError("bucket_unavailable")
    try:
        if response.json().get("public") is not public:
            raise RuntimeError("bucket_visibility_mismatch")
    except (ValueError, AttributeError):
        raise RuntimeError("bucket_metadata_invalid") from None


def _object_missing(response: httpx.Response) -> bool:
    if response.status_code == 404:
        return True
    if response.status_code != 400:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    return isinstance(payload, dict) and (
        str(payload.get("statusCode")) == "404"
        or payload.get("error") in {"not_found", "NoSuchKey"}
        or payload.get("code") in {"not_found", "NoSuchKey"}
    )


def _http_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) and 100 <= status <= 599 else None


def _error_category(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "network_timeout"
    if isinstance(exc, httpx.RequestError):
        return "network_error"
    if _http_status(exc) is not None:
        return "http_error"
    return "operation_error"


class _SmokeFailure(Exception):
    def __init__(self, failure: dict, cleanup: dict | None = None):
        super().__init__(failure["category"])
        self.failure = failure
        self.cleanup = cleanup or {}


def _legacy_step(
    stage: str,
    operation,
    *,
    storage=None,
    expected_http_statuses: tuple[int, ...] = (),
):
    from contextlib import nullcontext
    from unittest.mock import patch

    observed_status = None
    request_context = nullcontext()
    if storage is not None:
        original_request = storage._request

        def recorded_request(*args, **kwargs):
            nonlocal observed_status
            response = original_request(*args, **kwargs)
            status = getattr(response, "status_code", None)
            if isinstance(status, int) and 100 <= status <= 599:
                observed_status = status
            return response

        request_context = patch.object(
            storage, "_request", side_effect=recorded_request
        )

    try:
        with request_context:
            return operation()
    except Exception as exc:  # noqa: BLE001 - retain only sanitized diagnostics.
        status = _http_status(exc) or observed_status
        category = _error_category(exc)
        if status is not None and status not in expected_http_statuses:
            category = "http_error"
        raise _SmokeFailure({
            "stage": stage,
            "category": category,
            **({"http_status": status} if status is not None else {}),
        }) from None


def _cleanup_legacy_object(storage, key: str, *, attempted: bool) -> dict:
    result = {"delete": "not_attempted", "absence": "not_verified"}
    bucket_path = "object/" + quote(storage.bucket, safe="")

    if attempted:
        try:
            response = storage._request(
                "DELETE", bucket_path, json={"prefixes": [key]}
            )
            if response.status_code in (200, 204):
                result["delete"] = "deleted"
            elif _object_missing(response):
                result["delete"] = "already_absent"
                result["delete_http_status"] = response.status_code
            else:
                result["delete"] = "failed"
                result["delete_category"] = "http_error"
                result["delete_http_status"] = response.status_code
        except Exception as exc:  # noqa: BLE001 - continue to the other object.
            result["delete"] = "failed"
            result["delete_category"] = _error_category(exc)
            if status := _http_status(exc):
                result["delete_http_status"] = status

    try:
        response = storage._request(
            "GET",
            "object/authenticated/"
            + quote(storage.bucket, safe="")
            + "/"
            + quote(key, safe="/"),
        )
        result["absence"] = (
            "confirmed" if _object_missing(response) else "not_confirmed"
        )
        result["verify_http_status"] = response.status_code
    except Exception as exc:  # noqa: BLE001 - report verification separately.
        result["absence"] = "not_verified"
        result["verify_category"] = _error_category(exc)
        if status := _http_status(exc):
            result["verify_http_status"] = status
    return result


def _safe_legacy_cleanup(storage, key: str, *, attempted: bool) -> dict:
    try:
        return _cleanup_legacy_object(storage, key, attempted=attempted)
    except Exception as exc:  # noqa: BLE001 - preserve the other object's cleanup.
        result = {
            "delete": "failed" if attempted else "not_attempted",
            "absence": "not_verified",
            "verify_category": _error_category(exc),
        }
        if status := _http_status(exc):
            result["verify_http_status"] = status
        return result


def _r2_smoke(scope: StorageScope, run_id: str) -> dict:
    settings = StorageSettings.from_env()
    backends = dict(settings.backends)
    backends[scope] = "r2"
    adapter = StorageRegistry(replace(settings, backends=backends)).storage_for(scope)
    key = f"codex-smoke/{run_id}/object.pdf"
    reference = adapter._reference(key)
    try:
        stored = adapter.save(_PDF, "application/pdf", key=key)
        if stored.reference != reference:
            raise RuntimeError("unexpected_generated_reference")
        payload = adapter.read(reference)
        metadata = adapter.stat(reference)
        if (
            payload != _PDF
            or metadata.size != len(_PDF)
            or metadata.sha256 != hashlib.sha256(_PDF).hexdigest()
        ):
            raise RuntimeError("object_integrity_mismatch")
    finally:
        adapter.delete(reference)
        try:
            adapter.read(reference)
        except StorageNotFound:
            pass
        else:
            raise RuntimeError("cleanup_verification_failed")
    return {"operations": ["put", "get", "head", "delete"], "sha256": hashlib.sha256(_PDF).hexdigest()}


def _cloudinary_smoke(run_id: str) -> dict:
    env = os.environ
    adapter = CloudinaryImageStorage(
        cloud_name=env.get("CLOUDINARY_CLOUD_NAME", ""),
        api_key=env.get("CLOUDINARY_API_KEY", ""),
        api_secret=env.get("CLOUDINARY_API_SECRET", ""),
    )
    key = f"codex-smoke/{run_id}"
    reference = adapter._reference(key)
    try:
        stored = adapter.save(_PNG, "image/png", key=key)
        if stored.reference != reference:
            raise RuntimeError("unexpected_generated_reference")
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.get(stored.public_url)
        if (
            response.status_code != 200
            or not response.headers.get("content-type", "").startswith("image/")
            or not response.content
        ):
            raise RuntimeError("public_image_read_failed")
    finally:
        adapter.delete(reference)
    return {"operations": ["signed_upload", "public_read", "delete"], "sha256": hashlib.sha256(_PNG).hexdigest()}


def _audio_smoke(run_id: str) -> dict:
    from unittest.mock import patch

    storage = SupabasePortfolioAudioStorage()
    _assert_bucket(storage, public=True)
    suffix = run_id.replace("-", "")
    generated_key = f"projects/9000000000000000000/after-{suffix}.mp3"
    reference = generated_key
    try:
        with patch.object(storage, "_ensure_public_bucket", return_value=None), patch(
            "services.portfolio_audio_storage.uuid4", return_value=_uuid(suffix)
        ):
            reference = storage.save(_MP3, 9000000000000000000, "after")
        if reference != generated_key:
            raise RuntimeError("unexpected_generated_reference")
        url = storage.public_url(reference)
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            full = client.get(url)
            ranged = client.get(url, headers={"Range": "bytes=0-3"})
        if full.status_code != 200 or full.content != _MP3:
            raise RuntimeError("audio_read_failed")
        if ranged.status_code != 206 or ranged.content != _MP3[:4] or "bytes 0-3/" not in ranged.headers.get("content-range", ""):
            raise RuntimeError("audio_range_failed")
    finally:
        storage.delete(reference)
        cleanup_check = storage._request(
            "GET",
            "object/" + quote(storage.bucket, safe="") + "/" + quote(reference, safe="/"),
        )
        if not _object_missing(cleanup_check):
            raise RuntimeError("cleanup_verification_failed")
    return {"operations": ["upload", "public_read", "range_read", "delete"], "sha256": hashlib.sha256(_MP3).hexdigest()}


def _legacy_smoke(run_id: str) -> dict:
    from unittest.mock import patch

    proposal_bucket = None
    production_bucket = None
    proposal_key = None
    production_key = None
    proposal_attempted = False
    production_attempted = False
    primary_failure = None
    cleanup = {}

    try:
        proposal_bucket = _legacy_step(
            "proposal_storage_init", SupabaseDocumentoStorage
        )
        _legacy_step(
            "proposal_bucket_check",
            lambda: _assert_bucket(proposal_bucket, public=False),
            storage=proposal_bucket,
            expected_http_statuses=(200,),
        )
        production_bucket = _legacy_step(
            "production_storage_init", SupabaseProducaoArquivoStorage
        )
        _legacy_step(
            "production_bucket_check",
            lambda: _assert_bucket(production_bucket, public=False),
            storage=production_bucket,
            expected_http_statuses=(200,),
        )

        proposal_id = 9000000000000000000
        proposal_key = f"propostas/{proposal_id}/v1/{run_id.replace('-', '')}.pdf"
        proposal_ref = proposal_bucket._reference(proposal_key)
        production_folder = run_id.replace("-", "")
        production_key = f"arquivos/{production_folder}/{production_folder}"

        proposal_attempted = True
        with patch.object(proposal_bucket, "_bucket_privado", return_value=None), patch(
            "services.documento_storage.uuid4", return_value=_uuid(run_id.replace("-", ""))
        ):
            saved_reference = _legacy_step(
                "proposal_upload",
                lambda: proposal_bucket.salvar(_PDF, proposal_id, 1),
                storage=proposal_bucket,
                expected_http_statuses=(200, 201),
            )
        if saved_reference != proposal_ref:
            raise _SmokeFailure({"stage": "proposal_reference_check", "category": "reference_mismatch"})
        proposal_payload = _legacy_step(
            "proposal_download",
            lambda: proposal_bucket.ler(saved_reference),
            storage=proposal_bucket,
            expected_http_statuses=(200,),
        )
        if proposal_payload != _PDF:
            raise _SmokeFailure({"stage": "proposal_integrity_check", "category": "content_mismatch"})

        uuid_values = iter((_uuid(production_folder), _uuid(production_folder)))
        with patch.object(production_bucket, "ensure_private_bucket", return_value=None), patch(
            "services.producao_arquivo_storage.uuid4", side_effect=lambda: next(uuid_values)
        ):
            production_attempted = True
            saved_key = _legacy_step(
                "production_upload",
                lambda: production_bucket.save(_PDF, "application/pdf"),
                storage=production_bucket,
                expected_http_statuses=(200, 201),
            )
        if saved_key != production_key:
            raise _SmokeFailure({"stage": "production_reference_check", "category": "reference_mismatch"})
        production_payload = _legacy_step(
            "production_download",
            lambda: production_bucket.read(saved_key),
            storage=production_bucket,
            expected_http_statuses=(200,),
        )
        if production_payload != _PDF:
            raise _SmokeFailure({"stage": "production_integrity_check", "category": "content_mismatch"})
    except _SmokeFailure as exc:
        primary_failure = exc.failure
    except Exception as exc:  # noqa: BLE001 - never include provider exception text.
        primary_failure = {
            "stage": "legacy_setup",
            "category": _error_category(exc),
            **({"http_status": _http_status(exc)} if _http_status(exc) else {}),
        }
    finally:
        if proposal_bucket is not None and proposal_key is not None:
            cleanup["proposal_pdf"] = _safe_legacy_cleanup(
                proposal_bucket, proposal_key, attempted=proposal_attempted
            )
        else:
            cleanup["proposal_pdf"] = {"delete": "not_needed", "absence": "not_applicable"}
        if production_bucket is not None and production_key is not None:
            cleanup["production_file"] = _safe_legacy_cleanup(
                production_bucket, production_key, attempted=production_attempted
            )
        else:
            cleanup["production_file"] = {"delete": "not_needed", "absence": "not_applicable"}

    cleanup_failed = any(
        result["delete"] == "failed" or result["absence"] not in ("confirmed", "not_applicable")
        for result in cleanup.values()
    )
    if primary_failure or cleanup_failed:
        if primary_failure is None:
            primary_failure = {"stage": "legacy_cleanup", "category": "cleanup_failed"}
        raise _SmokeFailure(primary_failure, cleanup)
    return {
        "operations": ["private_document_put_get_delete", "private_production_put_get_delete"],
        "sha256": hashlib.sha256(_PDF).hexdigest(),
        "cleanup": cleanup,
    }


def run_smokes() -> dict:
    run_id = str(uuid4())
    checks = {
        "r2_private_temp": lambda: _r2_smoke(StorageScope.PRODUCTION_TEMP, run_id),
        "r2_private_final": lambda: _r2_smoke(StorageScope.PRODUCTION_FINAL, run_id),
        "cloudinary": lambda: _cloudinary_smoke(run_id),
        "supabase_audio": lambda: _audio_smoke(run_id),
        "legacy_storage": lambda: _legacy_smoke(run_id),
    }
    results = {}
    for name, check in checks.items():
        try:
            result = check()
            sanitized = {"connectivity": "passed", "smoke": "passed", **result}
        except _SmokeFailure as exc:
            sanitized = {
                "connectivity": "failed",
                "smoke": "failed",
                "failure": exc.failure,
                **({"cleanup": exc.cleanup} if exc.cleanup else {}),
            }
        except Exception as exc:  # noqa: BLE001 - sanitize all provider failures before logging.
            sanitized = {
                "connectivity": "failed",
                "smoke": "failed",
                "failure": {
                    "stage": name,
                    "category": _error_category(exc),
                    **({"http_status": _http_status(exc)} if _http_status(exc) else {}),
                },
            }
        digest = hashlib.sha256(json.dumps(sanitized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        results[name] = {**sanitized, "evidence_sha256": digest}
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "components": results,
        "all_passed": all(result["smoke"] == "passed" for result in results.values()),
    }


def diagnostic_report(report: dict) -> dict:
    return {
        "schema_version": 1,
        "all_passed": report["all_passed"],
        "components": {
            name: {
                "status": result["smoke"],
                **({"failure": result["failure"]} if "failure" in result else {}),
                **({"cleanup": result["cleanup"]} if "cleanup" in result else {}),
            }
            for name, result in report["components"].items()
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic-output")
    args = parser.parse_args(argv)
    report = run_smokes()
    output = os.path.abspath(args.output)
    with open(output, "x", encoding="utf-8") as file:
        json.dump(report, file, sort_keys=True)
    if args.diagnostic_output:
        diagnostic_output = os.path.abspath(args.diagnostic_output)
        with open(diagnostic_output, "x", encoding="utf-8") as file:
            json.dump(diagnostic_report(report), file, sort_keys=True)
    print(json.dumps({"all_passed": report["all_passed"], "components": {name: value["smoke"] for name, value in report["components"].items()}}, sort_keys=True))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
