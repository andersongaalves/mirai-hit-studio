"""Registry failover must keep the exact same immutable official PostgreSQL image."""

import re
import unittest
from pathlib import Path


class CIPostgresWorkflowTests(unittest.TestCase):
    def test_all_disposable_postgres_services_use_immutable_official_registry_failover(self):
        root = Path(__file__).resolve().parents[2]
        suffix = "postgres:17.11-bookworm@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826"
        primary = "docker.io/library/" + suffix
        alternate = "public.ecr.aws/docker/library/" + suffix
        expected = "${{ github.run_attempt > 1 && '" + alternate + "' || '" + primary + "' }}"
        services = {}
        for path in (root / ".github/workflows").glob("*.yml"):
            images = re.findall(r"(?m)^\s+image:\s+([^\r\n]+)", path.read_text(encoding="utf-8"))
            for image in images:
                if "postgres" in image:
                    services[path.name] = image
                    with self.subTest(workflow=path.name):
                        self.assertEqual(image, expected)
        self.assertEqual(set(services), {
            "storage-integration-gate.yml", "portals-e2e.yml",
            "client-access-migration.yml", "commerce-domain.yml",
            "portfolio-segments-migration.yml", "release-restore-drill.yml",
        })


if __name__ == "__main__":
    unittest.main()
