"""Restore an explicit PostgreSQL custom-format backup with destructive guards."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.database_tools import (
    DatabaseToolError,
    existing_dump,
    postgres_environment,
    require_tool,
)

PRODUCTION_ENVIRONMENTS = {"prod", "production"}
ALLOWED_ENVIRONMENTS = {"dev", "development", "test", "staging", *PRODUCTION_ENVIRONMENTS}


def restore_database(
    database_url: str,
    backup_path: str | Path,
    *,
    environment: str,
    confirmation: str,
    allow_production: bool = False,
    schema: str | None = None,
    runner=subprocess.run,
):
    if not database_url:
        raise DatabaseToolError("database_url_required")
    normalized_environment = (environment or "").strip().lower()
    if normalized_environment not in ALLOWED_ENVIRONMENTS:
        raise DatabaseToolError("explicit_environment_required")
    is_production = normalized_environment in PRODUCTION_ENVIRONMENTS
    expected_confirmation = "RESTORE_PRODUCTION" if is_production else "RESTORE"
    if confirmation != expected_confirmation:
        raise DatabaseToolError("restore_confirmation_required")
    if is_production and not allow_production:
        raise DatabaseToolError("production_restore_blocked")

    backup = existing_dump(backup_path)
    executable = require_tool("pg_restore")
    pg_environment, database_name = postgres_environment(database_url)
    if schema is not None and schema != "public":
        raise DatabaseToolError("restore_schema_not_allowed")
    command = [
        executable,
        "--exit-on-error",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--no-password",
    ]
    if schema:
        command.extend(["--schema", schema])
    command.extend(["--dbname", database_name, str(backup)])
    result = runner(
        command,
        env=pg_environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise DatabaseToolError("pg_restore_failed")


def main():
    parser = argparse.ArgumentParser(description="Restaura backup PostgreSQL de forma explicita.")
    parser.add_argument("--backup", required=True)
    parser.add_argument("--confirm-restore", required=True)
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--schema", choices=("public",))
    args = parser.parse_args()
    try:
        restore_database(
            os.getenv("DATABASE_URL", ""),
            args.backup,
            environment=os.getenv("APP_ENV", ""),
            confirmation=args.confirm_restore,
            allow_production=args.allow_production,
            schema=args.schema,
        )
    except (DatabaseToolError, OSError):
        print("restore_failed: operacao abortada; confira ambiente, confirmacao, arquivo e ferramentas.", file=sys.stderr)
        return 1
    print("restore_complete: valide dados e alembic_version antes de liberar o ambiente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
