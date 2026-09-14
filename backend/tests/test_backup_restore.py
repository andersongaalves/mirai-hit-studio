"""Safe PostgreSQL backup/restore wrapper tests without a real database."""

from datetime import datetime, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.backup_database import backup_database
from scripts.database_tools import DatabaseToolError, postgres_environment
from scripts.restore_database import restore_database


DATABASE_URL = "postgresql://mirai_user:secret-password@localhost:5432/mirai_test?sslmode=require"


class BackupRestoreTests(unittest.TestCase):
    def test_connection_environment_redacts_url(self):
        environment, database = postgres_environment(DATABASE_URL)
        self.assertEqual(database, "mirai_test")
        self.assertEqual(environment["PGPASSWORD"], "secret-password")
        self.assertEqual(environment["PGSSLMODE"], "require")
        self.assertNotIn("DATABASE_URL", environment)

    def test_backup_guards_success_and_failure(self):
        with tempfile.TemporaryDirectory(prefix="mirai-backup-test-") as directory:
            output_dir = Path(directory)

            def success(command, **options):
                output = Path(command[command.index("--file") + 1])
                output.write_bytes(b"synthetic custom dump")
                self.assertNotIn("secret-password", " ".join(command))
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("scripts.database_tools.shutil.which", return_value="pg_dump"):
                output = backup_database(
                    DATABASE_URL,
                    output_dir,
                    now=datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc),
                    runner=success,
                )
                self.assertEqual(output.name, "mirai_2026-09-14_150000.dump")
                with self.assertRaisesRegex(DatabaseToolError, "backup_already_exists"):
                    backup_database(
                        DATABASE_URL,
                        output_dir,
                        now=datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc),
                        runner=success,
                    )

            with patch("scripts.database_tools.shutil.which", return_value="pg_dump"):
                with self.assertRaisesRegex(DatabaseToolError, "pg_dump_failed"):
                    backup_database(
                        DATABASE_URL,
                        output_dir,
                        now=datetime(2026, 9, 14, 15, 1, tzinfo=timezone.utc),
                        runner=lambda command, **options: subprocess.CompletedProcess(command, 1, "", "secret-password"),
                    )
                self.assertFalse((output_dir / "mirai_2026-09-14_150100.dump").exists())

        for url in ("", "sqlite:///test.db"):
            with self.assertRaises(DatabaseToolError):
                backup_database(url, ".")
        with self.assertRaises((DatabaseToolError, OSError)):
            backup_database(DATABASE_URL, "missing-backup-directory")
        with tempfile.TemporaryDirectory() as directory, patch("scripts.database_tools.shutil.which", return_value=None):
            with self.assertRaisesRegex(DatabaseToolError, "pg_dump_not_found"):
                backup_database(DATABASE_URL, directory)

    def test_restore_guards_success_and_failure(self):
        with tempfile.TemporaryDirectory(prefix="mirai-restore-test-") as directory:
            backup = Path(directory) / "safe.dump"
            backup.write_bytes(b"synthetic custom dump")
            calls = []

            def success(command, **options):
                calls.append((command, options))
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("scripts.database_tools.shutil.which", return_value="pg_restore"):
                with self.assertRaisesRegex(DatabaseToolError, "explicit_environment_required"):
                    restore_database(DATABASE_URL, backup, environment="", confirmation="RESTORE")
                with self.assertRaisesRegex(DatabaseToolError, "restore_confirmation_required"):
                    restore_database(DATABASE_URL, backup, environment="test", confirmation="")
                with self.assertRaisesRegex(DatabaseToolError, "production_restore_blocked"):
                    restore_database(DATABASE_URL, backup, environment="production", confirmation="RESTORE_PRODUCTION")
                restore_database(DATABASE_URL, backup, environment="test", confirmation="RESTORE", runner=success)
                restore_database(
                    DATABASE_URL,
                    backup,
                    environment="production",
                    confirmation="RESTORE_PRODUCTION",
                    allow_production=True,
                    runner=success,
                )
                self.assertEqual(len(calls), 2)
                self.assertTrue(all("secret-password" not in " ".join(command) for command, _ in calls))
                with self.assertRaisesRegex(DatabaseToolError, "pg_restore_failed"):
                    restore_database(
                        DATABASE_URL,
                        backup,
                        environment="test",
                        confirmation="RESTORE",
                        runner=lambda command, **options: subprocess.CompletedProcess(command, 1, "", "secret-password"),
                    )

            invalid = Path(directory) / "safe.sql"
            invalid.write_text("not a custom dump", encoding="utf-8")
            with self.assertRaisesRegex(DatabaseToolError, "invalid_backup_file"):
                restore_database(DATABASE_URL, invalid, environment="test", confirmation="RESTORE")
            with self.assertRaises(FileNotFoundError):
                restore_database(DATABASE_URL, Path(directory) / "missing.dump", environment="test", confirmation="RESTORE")


if __name__ == "__main__":
    unittest.main()
