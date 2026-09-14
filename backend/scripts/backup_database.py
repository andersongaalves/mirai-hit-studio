"""Create an explicit PostgreSQL custom-format backup."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

from scripts.database_tools import (
    DatabaseToolError,
    existing_directory,
    postgres_environment,
    require_tool,
)


def backup_database(database_url: str, output_dir: str | Path, *, now=None, runner=subprocess.run):
    if not database_url:
        raise DatabaseToolError("database_url_required")
    directory = existing_directory(output_dir)
    executable = require_tool("pg_dump")
    environment, _ = postgres_environment(database_url)
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d_%H%M%S")
    output = directory / f"mirai_{timestamp}.dump"
    if output.exists():
        raise DatabaseToolError("backup_already_exists")

    result = runner(
        [executable, "--format=custom", "--no-owner", "--no-privileges", "--no-password", "--file", str(output)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        output.unlink(missing_ok=True)
        raise DatabaseToolError("pg_dump_failed")
    if not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise DatabaseToolError("backup_not_created")
    return output


def main():
    parser = argparse.ArgumentParser(description="Cria backup PostgreSQL em formato custom.")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        output = backup_database(os.getenv("DATABASE_URL", ""), args.output_dir)
    except (DatabaseToolError, OSError):
        print("backup_failed: confira configuracao, diretorio e ferramentas PostgreSQL.", file=sys.stderr)
        return 1
    print(f"backup_complete: {output.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
