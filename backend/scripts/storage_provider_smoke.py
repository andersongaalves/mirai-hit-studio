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

    proposal_bucket = SupabaseDocumentoStorage()
    _assert_bucket(proposal_bucket, public=False)
    proposal_id = 9000000000000000000
    proposal_key = f"propostas/{proposal_id}/v1/{run_id.replace('-', '')}.pdf"
    proposal_ref = proposal_bucket._reference(proposal_key)
    proposal_written = True

    production_bucket = SupabaseProducaoArquivoStorage()
    _assert_bucket(production_bucket, public=False)
    production_folder = run_id.replace("-", "")
    production_key = f"arquivos/{production_folder}/{production_folder}"
    production_written = True
    try:
        with patch.object(proposal_bucket, "_bucket_privado", return_value=None), patch(
            "services.documento_storage.uuid4", return_value=_uuid(run_id.replace("-", ""))
        ):
            saved_reference = proposal_bucket.salvar(_PDF, proposal_id, 1)
        if saved_reference != proposal_ref:
            raise RuntimeError("unexpected_generated_reference")
        if proposal_bucket.ler(saved_reference) != _PDF:
            raise RuntimeError("legacy_document_read_failed")

        uuid_values = iter((_uuid(production_folder), _uuid(production_folder)))
        with patch.object(production_bucket, "ensure_private_bucket", return_value=None), patch(
            "services.producao_arquivo_storage.uuid4", side_effect=lambda: next(uuid_values)
        ):
            saved_key = production_bucket.save(_PDF, "application/pdf")
        if saved_key != production_key:
            raise RuntimeError("unexpected_generated_reference")
        if production_bucket.read(saved_key) != _PDF:
            raise RuntimeError("legacy_production_read_failed")
    finally:
        if production_written:
            production_bucket.delete(production_key)
        if proposal_written:
            path = "object/" + quote(proposal_bucket.bucket, safe="")
            response = proposal_bucket._request("DELETE", path, json={"prefixes": [proposal_key]})
            if response.status_code not in (200, 204):
                raise RuntimeError("cleanup_failed")
            check = proposal_bucket._request(
                "GET",
                "object/authenticated/" + quote(proposal_bucket.bucket, safe="") + "/" + quote(proposal_key, safe="/"),
            )
            if not _object_missing(check):
                raise RuntimeError("cleanup_verification_failed")
    return {
        "operations": ["private_document_put_get_delete", "private_production_put_get_delete"],
        "sha256": hashlib.sha256(_PDF).hexdigest(),
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
        except Exception as exc:  # noqa: BLE001 - sanitize all provider failures before logging.
            sanitized = {"connectivity": "failed", "smoke": "failed", "failure_class": type(exc).__name__}
        digest = hashlib.sha256(json.dumps(sanitized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        results[name] = {**sanitized, "evidence_sha256": digest}
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "components": results,
        "all_passed": all(result["smoke"] == "passed" for result in results.values()),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = run_smokes()
    output = os.path.abspath(args.output)
    with open(output, "x", encoding="utf-8") as file:
        json.dump(report, file, sort_keys=True)
    print(json.dumps({"all_passed": report["all_passed"], "components": {name: value["smoke"] for name, value in report["components"].items()}}, sort_keys=True))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
