import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import httpx

from services.documento_storage import SupabaseDocumentoStorage
from services.producao_arquivo_storage import SupabaseProducaoArquivoStorage
from scripts.storage_provider_smoke import (
    _SmokeFailure,
    _PNG,
    _error_category,
    _legacy_smoke,
    diagnostic_report,
    main,
    run_smokes,
)


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code


class _ProposalStorage:
    bucket = "proposal-bucket"

    def __init__(self, run_id, requests):
        self.run_id = run_id
        self.requests = requests

    def _reference(self, key):
        return f"reference:{key}"

    def _bucket_privado(self):
        pass

    def salvar(self, data, proposal_id, version):
        return self._reference(
            f"propostas/{proposal_id}/v{version}/{self.run_id}.pdf"
        )

    def ler(self, reference):
        return b"%PDF-1.7\nMirai synthetic storage smoke\n%%EOF\n"

    def _request(self, method, path, **kwargs):
        self.requests.append(("proposal", method))
        if method == "DELETE":
            raise httpx.TimeoutException("private URL and object key")
        return _Response(404)


class _ProductionStorage:
    bucket = "production-bucket"

    def __init__(self, run_id, requests):
        self.run_id = run_id
        self.requests = requests

    def ensure_private_bucket(self):
        pass

    def save(self, data, mime_type):
        return f"arquivos/{self.run_id}/{self.run_id}"

    def read(self, key):
        request = httpx.Request("GET", "https://storage.invalid/object")
        response = httpx.Response(502, request=request)
        raise httpx.HTTPStatusError("private URL and object key", request=request, response=response)

    def _request(self, method, path, **kwargs):
        self.requests.append(("production", method))
        return _Response(204 if method == "DELETE" else 404)


class StorageProviderSmokeTests(unittest.TestCase):
    def test_synthetic_cloudinary_png_has_valid_chunks_and_pixel_data(self):
        self.assertEqual(_PNG[:8], b"\x89PNG\r\n\x1a\n")
        offset = 8
        chunks = []
        while offset < len(_PNG):
            length = struct.unpack(">I", _PNG[offset:offset + 4])[0]
            kind = _PNG[offset + 4:offset + 8]
            data = _PNG[offset + 8:offset + 8 + length]
            crc = struct.unpack(">I", _PNG[offset + 8 + length:offset + 12 + length])[0]
            self.assertEqual(zlib.crc32(kind + data), crc, kind)
            chunks.append((kind, data))
            offset += 12 + length
        self.assertEqual(offset, len(_PNG))
        self.assertEqual([kind for kind, _ in chunks], [b"IHDR", b"IDAT", b"IEND"])
        self.assertEqual(struct.unpack(">IIBBBBB", chunks[0][1]), (1, 1, 8, 6, 0, 0, 0))
        self.assertEqual(zlib.decompress(chunks[1][1]), bytes((0, 255, 0, 0, 255)))

    def test_rollout_workflow_publishes_bounded_diagnostics_on_failure(self):
        workflow = (
            Path(__file__).resolve().parents[2]
            / ".github/workflows/storage-provider-rollout.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("--diagnostic-output /tmp/storage-smoke-diagnostic.json", workflow)
        diagnostic_step = workflow.split("- name: Publish sanitized smoke diagnostics", 1)[1]
        diagnostic_step = diagnostic_step.split("- name:", 1)[0]
        self.assertIn("!cancelled()", diagnostic_step)
        for condition in (
            "steps.legacy-smoke.outcome == 'success'",
            "steps.legacy-smoke.outcome == 'failure'",
            "steps.all-smokes.outcome == 'failure'",
        ):
            self.assertIn(condition, diagnostic_step)
        self.assertIn("/tmp/storage-smoke-diagnostic.json", diagnostic_step)
        self.assertIn("retention-days: 1", diagnostic_step)
        self.assertIn("if-no-files-found: error", diagnostic_step)

    def test_legacy_workflow_step_is_isolated_from_other_provider_secrets(self):
        workflow = (
            Path(__file__).resolve().parents[2]
            / ".github/workflows/storage-provider-rollout.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("default: legacy_only", workflow)
        self.assertIn('case "$SMOKE_SCOPE" in legacy_only|all)', workflow)
        legacy = workflow.split(
            "- name: Run legacy-only diagnostic and independent cleanup", 1
        )[1].split("- name:", 1)[0]
        self.assertIn("if: inputs.smoke_scope == 'legacy_only'", legacy)
        self.assertIn("--scope legacy_only", legacy)
        self.assertIn("SUPABASE_SERVICE_ROLE_KEY", legacy)
        for excluded in ("R2_", "CLOUDINARY_", "PORTFOLIO_AUDIO_", "HMAC"):
            self.assertNotIn(excluded, legacy)
        for name in (
            "Run bounded real-provider smoke and cleanup",
            "Recheck pinned signer and verifier immediately before secret access",
            "Sign only a complete successful smoke report",
            "Verify the signed evidence and effective configuration",
            "Publish sanitized, short-lived evidence",
        ):
            step = workflow.split(f"- name: {name}", 1)[1].split("- name:", 1)[0]
            self.assertIn("inputs.smoke_scope == 'all'", step)

    def test_smoke_source_pin_matches_reviewed_script(self):
        import hashlib

        root = Path(__file__).resolve().parents[2]
        digest = hashlib.sha256(
            (root / "backend/scripts/storage_provider_smoke.py").read_bytes()
        ).hexdigest()
        workflow = (root / ".github/workflows/storage-provider-rollout.yml").read_text()
        self.assertIn(f"{digest}  scripts/storage_provider_smoke.py", workflow)

    def test_provider_failure_is_reported_sanitized_and_blocks_attestation(self):
        with (
            patch(
                "scripts.storage_provider_smoke._r2_smoke",
                side_effect=RuntimeError("secret endpoint and object key"),
            ),
            patch(
                "scripts.storage_provider_smoke._cloudinary_smoke",
                return_value={"operations": [], "sha256": "a" * 64},
            ),
            patch(
                "scripts.storage_provider_smoke._audio_smoke",
                return_value={"operations": [], "sha256": "b" * 64},
            ),
            patch(
                "scripts.storage_provider_smoke._legacy_smoke",
                return_value={"operations": [], "sha256": "c" * 64},
            ),
        ):
            report = run_smokes()

        self.assertFalse(report["all_passed"])
        for name in ("r2_private_temp", "r2_private_final"):
            self.assertEqual(report["components"][name]["smoke"], "failed")
            self.assertEqual(
                report["components"][name]["failure"]["category"],
                "operation_error",
            )
        self.assertNotIn("secret endpoint", str(report))
        self.assertNotIn("object key", str(report))

    def test_diagnostic_report_omits_run_and_object_identifiers(self):
        report = {
            "run_id": "private-run-id",
            "all_passed": False,
            "selected_passed": False,
            "components": {
                "legacy_storage": {
                    "smoke": "failed",
                    "failure": {
                        "stage": "production_download",
                        "category": "http_error",
                        "http_status": 502,
                    },
                    "cleanup": {
                        "proposal_pdf": {"delete": "failed", "absence": "confirmed"}
                    },
                    "reference": "supabase://private-bucket/private-object-key",
                }
            },
        }

        diagnostic = diagnostic_report(report)

        self.assertNotIn("private-run-id", str(diagnostic))
        self.assertNotIn("private-object-key", str(diagnostic))
        self.assertNotIn("supabase://", str(diagnostic))
        self.assertEqual(
            diagnostic["components"]["legacy_storage"]["failure"],
            {"stage": "production_download", "category": "http_error", "http_status": 502},
        )
        self.assertEqual(
            diagnostic["components"]["legacy_storage"]["cleanup"]["proposal_pdf"]["absence"],
            "confirmed",
        )

    def test_cli_writes_sanitized_diagnostic_before_returning_failure(self):
        report = {
            "run_id": "private-run-id",
            "all_passed": False,
            "selected_passed": False,
            "components": {
                "legacy_storage": {
                    "smoke": "failed",
                    "failure": {"stage": "proposal_upload", "category": "http_error", "http_status": 403},
                    "cleanup": {"proposal_pdf": {"delete": "deleted", "absence": "confirmed"}},
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            smoke_path = str(Path(directory) / "smoke.json")
            diagnostic_path = str(Path(directory) / "diagnostic.json")
            with patch("scripts.storage_provider_smoke.run_smokes", return_value=report):
                exit_code = main(
                    ["--output", smoke_path, "--diagnostic-output", diagnostic_path]
                )

            diagnostic = json.loads(Path(diagnostic_path).read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(diagnostic["components"]["legacy_storage"]["status"], "failed")
            self.assertNotIn("private-run-id", Path(diagnostic_path).read_text(encoding="utf-8"))

    def test_legacy_failure_preserves_original_and_attempts_both_cleanups(self):
        run_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        run_hex = run_id.replace("-", "")
        requests = []
        proposal = _ProposalStorage(run_hex, requests)
        production = _ProductionStorage(run_hex, requests)

        with (
            patch("scripts.storage_provider_smoke.SupabaseDocumentoStorage", return_value=proposal),
            patch("scripts.storage_provider_smoke.SupabaseProducaoArquivoStorage", return_value=production),
            patch("scripts.storage_provider_smoke._assert_bucket"),
        ):
            with self.assertRaises(_SmokeFailure) as raised:
                _legacy_smoke(run_id)

        self.assertEqual(
            raised.exception.failure,
            {"stage": "production_download", "category": "http_error", "http_status": 502},
        )
        cleanup = raised.exception.cleanup
        self.assertEqual(cleanup["proposal_pdf"]["delete"], "failed")
        self.assertEqual(cleanup["proposal_pdf"]["delete_category"], "network_timeout")
        self.assertEqual(cleanup["proposal_pdf"]["absence"], "confirmed")
        self.assertEqual(cleanup["production_file"]["delete"], "deleted")
        self.assertEqual(cleanup["production_file"]["absence"], "confirmed")
        self.assertIn(("proposal", "DELETE"), requests)
        self.assertIn(("production", "DELETE"), requests)
        self.assertNotIn("private URL", str(raised.exception.failure))
        self.assertNotIn("object key", str(cleanup))

    def test_real_legacy_adapters_preserve_sanitized_http_status(self):
        deleted_buckets = set()

        def handler(request):
            path = request.url.path
            if "/bucket/" in path:
                return httpx.Response(200, json={"public": False})
            bucket = (
                "proposal-bucket"
                if "proposal-bucket" in path
                else "production-bucket"
            )
            if request.method == "POST":
                return httpx.Response(200)
            if request.method == "DELETE":
                deleted_buckets.add(bucket)
                return httpx.Response(200)
            if bucket in deleted_buckets:
                return httpx.Response(404)
            if bucket == "proposal-bucket":
                return httpx.Response(
                    200,
                    content=b"%PDF-1.7\nMirai synthetic storage smoke\n%%EOF\n",
                )
            return httpx.Response(502)

        transport = httpx.MockTransport(handler)
        proposal = SupabaseDocumentoStorage(
            base_url="https://storage.invalid",
            service_key="test-only",
            bucket="proposal-bucket",
            transport=transport,
        )
        production = SupabaseProducaoArquivoStorage(
            base_url="https://storage.invalid",
            service_key="test-only",
            bucket="production-bucket",
            transport=transport,
        )

        with (
            patch(
                "scripts.storage_provider_smoke.SupabaseDocumentoStorage",
                return_value=proposal,
            ),
            patch(
                "scripts.storage_provider_smoke.SupabaseProducaoArquivoStorage",
                return_value=production,
            ),
        ):
            with self.assertRaises(_SmokeFailure) as raised:
                _legacy_smoke("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

        self.assertEqual(
            raised.exception.failure,
            {
                "stage": "production_download",
                "category": "http_error",
                "http_status": 502,
            },
        )
        self.assertEqual(
            raised.exception.cleanup["proposal_pdf"]["absence"], "confirmed"
        )
        self.assertEqual(
            raised.exception.cleanup["production_file"]["absence"], "confirmed"
        )

    def test_legacy_only_never_invokes_other_providers_or_attests_full_rollout(self):
        with (
            patch("scripts.storage_provider_smoke._r2_smoke") as r2,
            patch("scripts.storage_provider_smoke._cloudinary_smoke") as cloudinary,
            patch("scripts.storage_provider_smoke._audio_smoke") as audio,
            patch(
                "scripts.storage_provider_smoke._legacy_smoke",
                return_value={"sha256": "a" * 64, "cleanup": {}},
            ) as legacy,
        ):
            report = run_smokes(scope="legacy_only")
        r2.assert_not_called()
        cloudinary.assert_not_called()
        audio.assert_not_called()
        legacy.assert_called_once()
        self.assertEqual(set(report["components"]), {"legacy_storage"})
        self.assertTrue(report["selected_passed"])
        self.assertFalse(report["all_passed"])

    def test_invalid_scope_is_rejected_before_any_provider_call(self):
        with patch("scripts.storage_provider_smoke.uuid4") as generate_id:
            with self.assertRaisesRegex(ValueError, "invalid_smoke_scope"):
                run_smokes(scope="legacy")
        generate_id.assert_not_called()

    def test_cli_legacy_success_returns_zero_without_full_rollout_claim(self):
        report = {
            "all_passed": False,
            "selected_passed": True,
            "components": {"legacy_storage": {"smoke": "passed", "cleanup": {}}},
        }
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "smoke.json")
            diagnostic = str(Path(directory) / "diagnostic.json")
            with patch(
                "scripts.storage_provider_smoke.run_smokes", return_value=report
            ) as run:
                self.assertEqual(main([
                    "--scope", "legacy_only", "--output", output,
                    "--diagnostic-output", diagnostic,
                ]), 0)
            run.assert_called_once_with(scope="legacy_only")
            sanitized = json.loads(Path(diagnostic).read_text())
        self.assertTrue(sanitized["selected_passed"])
        self.assertFalse(sanitized["all_passed"])

    def test_real_adapters_preserve_transport_failures_and_cleanup_is_independent(self):
        for error, expected in (
            (httpx.ReadTimeout, "network_timeout"),
            (httpx.ConnectError, "network_error"),
        ):
            with self.subTest(error=error.__name__):
                requests = []
                deleted = set()

                def handler(request):
                    path = request.url.path
                    requests.append((request.method, path))
                    if "/bucket/" in path:
                        self.assertEqual(request.method, "GET")
                        return httpx.Response(200, json={"public": False})
                    bucket = "proposal" if "proposal-bucket" in path else "production"
                    if request.method == "POST":
                        return httpx.Response(200)
                    if request.method == "DELETE":
                        if bucket == "proposal":
                            raise error("secret URL and key", request=request)
                        deleted.add(bucket)
                        return httpx.Response(200)
                    if bucket in deleted:
                        return httpx.Response(404)
                    if bucket == "production":
                        raise error("secret URL and key", request=request)
                    # The failed proposal DELETE may leave a synthetic object.
                    return httpx.Response(
                        200, content=b"%PDF-1.7\nMirai synthetic storage smoke\n%%EOF\n"
                    )

                transport = httpx.MockTransport(handler)
                proposal = SupabaseDocumentoStorage(
                    base_url="https://storage.invalid", service_key="test-only",
                    bucket="proposal-bucket", transport=transport,
                )
                production = SupabaseProducaoArquivoStorage(
                    base_url="https://storage.invalid", service_key="test-only",
                    bucket="production-bucket", transport=transport,
                )
                with (
                    patch("scripts.storage_provider_smoke.SupabaseDocumentoStorage", return_value=proposal),
                    patch("scripts.storage_provider_smoke.SupabaseProducaoArquivoStorage", return_value=production),
                ):
                    with self.assertRaises(_SmokeFailure) as raised:
                        _legacy_smoke("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
                self.assertEqual(raised.exception.failure, {
                    "stage": "production_download", "category": expected,
                })
                cleanup = raised.exception.cleanup
                self.assertEqual(cleanup["proposal_pdf"]["delete_category"], expected)
                self.assertEqual(cleanup["proposal_pdf"]["absence"], "not_confirmed")
                self.assertEqual(cleanup["production_file"]["absence"], "confirmed")
                self.assertIn(("DELETE", "/storage/v1/object/production-bucket"), requests)
                self.assertNotIn("secret URL", str(raised.exception.failure) + str(cleanup))

    def test_invalid_or_public_bucket_blocks_writes_without_changing_buckets(self):
        for response, expected, status in (
            (httpx.Response(200, json={"public": True}), "bucket_visibility_mismatch", 200),
            (httpx.Response(200, content=b"invalid"), "bucket_metadata_invalid", 200),
            (httpx.Response(403), "http_error", 403),
            (httpx.Response(404), "http_error", 404),
        ):
            with self.subTest(expected=expected, status=status):
                requests = []

                def handler(request):
                    requests.append((request.method, request.url.path))
                    return response

                proposal = SupabaseDocumentoStorage(
                    base_url="https://storage.invalid", service_key="test-only",
                    bucket="proposal-bucket", transport=httpx.MockTransport(handler),
                )
                with (
                    patch("scripts.storage_provider_smoke.SupabaseDocumentoStorage", return_value=proposal),
                    patch("scripts.storage_provider_smoke.SupabaseProducaoArquivoStorage") as production,
                ):
                    with self.assertRaises(_SmokeFailure) as raised:
                        _legacy_smoke("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
                production.assert_not_called()
                self.assertEqual(requests, [("GET", "/storage/v1/bucket/proposal-bucket")])
                self.assertEqual(raised.exception.failure, {
                    "stage": "proposal_bucket_check", "category": expected, "http_status": status,
                })
                for cleanup in raised.exception.cleanup.values():
                    self.assertEqual(cleanup["delete"], "not_needed")

    def test_exception_context_cycles_are_bounded(self):
        error = RuntimeError("secret URL")
        error.__context__ = error
        self.assertEqual(_error_category(error), "operation_error")


if __name__ == "__main__":
    unittest.main()
