"""One-time schema bootstrap for a completely empty database."""

from pathlib import Path
import sys

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import configure_mappers


class BootstrapError(RuntimeError):
    pass


def migration_config():
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    return config


def require_empty_database(connection):
    if connection.dialect.name == "postgresql":
        # Cooperating bootstrap processes cannot race the emptiness check.
        locked = connection.execute(text(
            "SELECT pg_try_advisory_xact_lock(1296585521, 1112493908)"
        )).scalar_one()
        if not locked:
            raise BootstrapError("bootstrap_busy: outra execucao esta em andamento.")
        if connection.execute(text("SELECT current_schema()")).scalar_one() != "public":
            raise BootstrapError("unsupported_schema: o schema ativo deve ser public.")
        objects = connection.execute(text("""
            SELECT c.relname FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_toast%'
            UNION ALL
            SELECT t.typname FROM pg_catalog.pg_type t
            JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_toast%'
              AND t.typtype IN ('c', 'd', 'e', 'r', 'm')
        """)).first()
    elif connection.dialect.name == "sqlite":
        # Explicit BEGIN also makes SQLite DDL transactional in legacy drivers.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        databases = connection.exec_driver_sql("PRAGMA database_list").all()
        if any(row[1] not in {"main", "temp"} for row in databases):
            raise BootstrapError("attached_database: banco SQLite anexado nao permitido.")
        objects = connection.exec_driver_sql("""
            SELECT name FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'
            UNION ALL
            SELECT name FROM sqlite_temp_master WHERE name NOT GLOB 'sqlite_*'
        """).first()
    else:
        raise BootstrapError("unsupported_database: use PostgreSQL ou SQLite descartavel.")
    if objects:
        raise BootstrapError("database_not_empty: objetos existentes; bootstrap abortado.")


def bootstrap(engine):
    script = ScriptDirectory.from_config(migration_config())
    heads = script.get_heads()
    if len(heads) != 1:
        raise BootstrapError("invalid_heads: esperado exatamente uma Alembic head.")
    head = heads[0]
    with engine.begin() as connection:
        require_empty_database(connection)
        # The registry is imported only after the empty-database guard passes.
        import models  # noqa: F401
        from database import Base

        configure_mappers()
        if not Base.metadata.tables or "alembic_version" in Base.metadata.tables:
            raise BootstrapError("invalid_metadata: registro de models invalido.")
        Base.metadata.create_all(bind=connection, checkfirst=False)
        context = MigrationContext.configure(connection)
        context.stamp(script, head)
        if context.get_current_heads() != (head,):
            raise BootstrapError("version_mismatch: registro da revision nao confirmado.")
    return head


def main():
    try:
        from database import engine

        try:
            head = bootstrap(engine)
        finally:
            engine.dispose()
    except BootstrapError as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("bootstrap_interrupted: confira o estado do banco antes de repetir.", file=sys.stderr)
        return 130
    except Exception:
        # Driver/configuration exceptions can contain URLs, SQL and credentials.
        print("bootstrap_failed: falha de conexao, criacao ou registro; confira o banco e as permissoes.", file=sys.stderr)
        return 1
    print(f"bootstrap_complete: schema criado; Alembic revision {head}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
