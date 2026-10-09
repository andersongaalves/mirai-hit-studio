import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from services.documento_storage import SupabaseDocumentoStorage
from services.producao_arquivo_storage import SupabaseProducaoArquivoStorage
from scripts.storage_provider_smoke import (
    _SmokeFailure,
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
    def test_rollout_workflow_publishes_bounded_diagnostics_on_failure(self):
        workflow = (
            Path(__file__).resolve().parents[2]
            / ".github/workflows/storage-provider-rollout.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("--diagnostic-output /tmp/storage-smoke-diagnostic.json", workflow)
        diagnostic_step = workflow.split("- name: Publish sanitized smoke diagnostics", 1)[1]
        diagnostic_step = diagnostic_step.split("- name:", 1)[0]
        self.assertIn("if: failure()", diagnostic_step)
        self.assertIn("/tmp/storage-smoke-diagnostic.json", diagnostic_step)
        self.assertIn("retention-days: 1", diagnostic_step)
        self.assertIn("if-no-files-found: warn", diagnostic_step)

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


if __name__ == "__main__":
    unittest.main()
