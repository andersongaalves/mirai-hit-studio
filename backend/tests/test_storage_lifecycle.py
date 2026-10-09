"""Safe lifecycle planning without provider deletion."""

import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import test_bootstrap_database as isolated

from services.storage.lifecycle import (
    LifecycleAction,
    RetentionPolicy,
    plan_production_files,
    summarize,
)

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


@dataclass
class FileRow:
    id: int
    tipo: str
    created_at: datetime
    substitui_arquivo_id: int | None = None


class StorageLifecycleTests(unittest.TestCase):
    def rows(self):
        return [
            FileRow(1, "material", NOW - timedelta(days=100)),
            FileRow(2, "material", NOW - timedelta(days=10), 1),
            FileRow(3, "previa", NOW - timedelta(days=100)),
            FileRow(4, "previa", NOW - timedelta(days=5), 3),
            FileRow(5, "entrega", NOW - timedelta(days=100)),
            FileRow(6, "entrega", NOW - timedelta(days=1), 5),
        ]

    def test_without_approved_deadline_only_superseded_work_requires_review(self):
        decisions = plan_production_files(
            self.rows(), now=NOW, policy=RetentionPolicy()
        )
        by_id = {decision.record_id: decision for decision in decisions}
        self.assertEqual(by_id[1].action, LifecycleAction.REVIEW)
        self.assertEqual(by_id[3].action, LifecycleAction.REVIEW)
        self.assertEqual(by_id[5].action, LifecycleAction.PRESERVE)
        self.assertTrue(all(by_id[item].action == LifecycleAction.PRESERVE for item in (2, 4, 6)))

    def test_approved_deadline_marks_only_elapsed_non_final_versions_eligible(self):
        decisions = plan_production_files(
            self.rows(), now=NOW, policy=RetentionPolicy(superseded_days=30)
        )
        by_id = {decision.record_id: decision for decision in decisions}
        self.assertEqual(by_id[1].action, LifecycleAction.ELIGIBLE)
        self.assertEqual(by_id[3].action, LifecycleAction.ELIGIBLE)
        self.assertEqual(by_id[5].action, LifecycleAction.PRESERVE)
        summary = summarize(decisions)
        self.assertEqual(summary["production_material:eligible"], 1)
        self.assertNotIn("object_key", summary)

    def test_invalid_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            RetentionPolicy(superseded_days=0)

    def test_inventory_is_sanitized_and_never_deletes(self):
        isolated.BootstrapTests().run_case("""
            bootstrap(engine)
            from scripts.storage_lifecycle import inventory
            report = inventory(str(engine.url), superseded_days=None)
            assert report['mode'] == 'dry-run'
            assert report['production_files'] == 0
            assert report['deletions'] == 0
            assert report['remote_orphans'] == 'not_evaluated_provider_listing_unavailable'
            assert not any('key' in name or 'email' in name for name in report)
        """)


if __name__ == "__main__":
    unittest.main()
