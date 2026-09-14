import os
import shutil
from pathlib import Path

from sqlalchemy.engine import make_url


class DatabaseToolError(RuntimeError):
    pass


def postgres_environment(database_url: str):
    try:
        url = make_url(database_url)
    except Exception:
        raise DatabaseToolError("invalid_database_url") from None
    if url.get_backend_name() != "postgresql" or not url.host or not url.database:
        raise DatabaseToolError("postgresql_database_required")

    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)
    environment.update({
        "PGHOST": url.host,
        "PGPORT": str(url.port or 5432),
        "PGDATABASE": url.database,
        "PGUSER": url.username or "",
        "PGPASSWORD": url.password or "",
    })
    if url.query.get("sslmode"):
        environment["PGSSLMODE"] = url.query["sslmode"]
    return environment, url.database


def require_tool(name: str):
    executable = shutil.which(name)
    if not executable:
        raise DatabaseToolError(f"{name}_not_found")
    return executable


def existing_directory(path: str | Path):
    directory = Path(path).expanduser().resolve(strict=True)
    if not directory.is_dir():
        raise DatabaseToolError("invalid_output_directory")
    return directory


def existing_dump(path: str | Path):
    dump = Path(path).expanduser().resolve(strict=True)
    if not dump.is_file() or dump.suffix.lower() != ".dump" or dump.stat().st_size == 0:
        raise DatabaseToolError("invalid_backup_file")
    return dump
