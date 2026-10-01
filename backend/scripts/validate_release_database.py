"""Validate a bootstrap or restored release database without exposing row data."""

import argparse
import json
import os
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import Numeric, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.orm import configure_mappers

from database import Base
from scripts.bootstrap_database import migration_config

CRITICAL_TABLES = {
    "usuarios",
    "servicos",
    "clientes",
    "orcamentos",
    "propostas",
    "producoes",
    "cobrancas",
    "pagamentos",
    "provider_webhook_events",
    "audit_logs",
}
RESTORE_DATA_TABLES = {"usuarios", "clientes", "propostas", "cobrancas", "pagamentos"}
RLS_TABLES = {
    "ai_conversations",
    "ai_messages",
    "ai_email_threads",
    "ai_briefings",
    "ai_usage_events",
}
FINANCIAL_COLUMNS = {("cobrancas", "valor_total"), ("pagamentos", "valor")}


class ReleaseDatabaseError(RuntimeError):
    pass


def _expected_unique_columns(table):
    expected = set()
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            expected.add(tuple(sorted(column.name for column in constraint.columns)))
    for index in table.indexes:
        if index.unique:
            expected.add(tuple(sorted(column.name for column in index.columns)))
    return expected


def _actual_unique_columns(inspector, table_name):
    actual = {
        tuple(sorted(item["column_names"]))
        for item in inspector.get_unique_constraints(table_name, schema="public")
    }
    actual.update(
        tuple(sorted(item["column_names"]))
        for item in inspector.get_indexes(table_name, schema="public")
        if item.get("unique")
    )
    return actual


def _validate_schema(connection):
    import models  # noqa: F401

    configure_mappers()
    inspector = inspect(connection)
    tables = set(inspector.get_table_names(schema="public"))
    expected_tables = set(Base.metadata.tables)
    missing = expected_tables - tables
    if missing or not CRITICAL_TABLES.issubset(tables):
        raise ReleaseDatabaseError("release_schema_missing_tables")

    for table_name, table in Base.metadata.tables.items():
        columns = {item["name"]: item for item in inspector.get_columns(table_name, schema="public")}
        if {column.name for column in table.columns} - set(columns):
            raise ReleaseDatabaseError("release_schema_missing_columns")

        actual_foreign_keys = {
            (
                tuple(item["constrained_columns"]),
                item["referred_table"],
                tuple(item["referred_columns"]),
            )
            for item in inspector.get_foreign_keys(table_name, schema="public")
        }
        for foreign_key in table.foreign_key_constraints:
            expected = (
                tuple(element.parent.name for element in foreign_key.elements),
                foreign_key.referred_table.name,
                tuple(element.column.name for element in foreign_key.elements),
            )
            if expected not in actual_foreign_keys:
                raise ReleaseDatabaseError("release_schema_missing_foreign_key")

        if not _expected_unique_columns(table).issubset(
            _actual_unique_columns(inspector, table_name)
        ):
            raise ReleaseDatabaseError("release_schema_missing_unique_constraint")

        actual_indexes = {
            item["name"] for item in inspector.get_indexes(table_name, schema="public")
        }
        expected_indexes = {index.name for index in table.indexes if index.name}
        if not expected_indexes.issubset(actual_indexes):
            raise ReleaseDatabaseError("release_schema_missing_index")

    for table_name, column_name in FINANCIAL_COLUMNS:
        column = next(
            item
            for item in inspector.get_columns(table_name, schema="public")
            if item["name"] == column_name
        )
        if not isinstance(column["type"], Numeric):
            raise ReleaseDatabaseError("release_financial_type_invalid")
        if (column["type"].precision, column["type"].scale) != (12, 2):
            raise ReleaseDatabaseError("release_financial_precision_invalid")

    unvalidated_constraints = connection.execute(text("""
        SELECT count(*)
        FROM pg_catalog.pg_constraint
        WHERE connamespace = 'public'::regnamespace AND NOT convalidated
    """)).scalar_one()
    if unvalidated_constraints:
        raise ReleaseDatabaseError("release_constraints_not_validated")

    enabled_rls = set(connection.execute(text("""
        SELECT relname
        FROM pg_catalog.pg_class
        WHERE relnamespace = 'public'::regnamespace AND relrowsecurity
    """)).scalars())
    if not RLS_TABLES.issubset(enabled_rls):
        raise ReleaseDatabaseError("release_rls_missing")

    exposed_table_grants = connection.execute(text("""
        SELECT count(*)
        FROM information_schema.role_table_grants
        WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated')
    """)).scalar_one()
    if exposed_table_grants:
        raise ReleaseDatabaseError("release_data_api_table_grants_present")


def validate_database(database_url: str, *, expect_data: bool, snapshot_path: Path | None):
    if not database_url:
        raise ReleaseDatabaseError("release_database_url_required")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            if connection.dialect.name != "postgresql":
                raise ReleaseDatabaseError("release_postgresql_required")
            server_major = int(connection.execute(text("SHOW server_version_num")).scalar_one()) // 10000
            if server_major != 17:
                raise ReleaseDatabaseError("release_postgresql_17_required")

            expected_head = ScriptDirectory.from_config(migration_config()).get_current_head()
            current_head = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            if current_head != expected_head:
                raise ReleaseDatabaseError("release_alembic_head_mismatch")

            _validate_schema(connection)
            counts = {
                table_name: connection.execute(
                    text(f'SELECT count(*) FROM public."{table_name}"')
                ).scalar_one()
                for table_name in sorted(CRITICAL_TABLES)
            }
            if expect_data and any(counts[table_name] == 0 for table_name in RESTORE_DATA_TABLES):
                raise ReleaseDatabaseError("release_restore_expected_data_missing")

            approved_without_charge = connection.execute(text("""
                SELECT count(*)
                FROM pagamentos AS pagamento
                LEFT JOIN cobrancas AS cobranca ON cobranca.id = pagamento.cobranca_id
                WHERE pagamento.status = 'aprovado' AND cobranca.id IS NULL
            """)).scalar_one()
            paid_without_approved_payment = connection.execute(text("""
                SELECT count(*)
                FROM cobrancas AS cobranca
                WHERE cobranca.status = 'paga'
                  AND NOT EXISTS (
                      SELECT 1 FROM pagamentos AS pagamento
                      WHERE pagamento.cobranca_id = cobranca.id
                        AND pagamento.status = 'aprovado'
                  )
            """)).scalar_one()
            if approved_without_charge or paid_without_approved_payment:
                raise ReleaseDatabaseError("release_financial_consistency_failed")

            summary = {
                "alembic_head": current_head,
                "counts": counts,
                "financial_consistency": "passed",
                "postgresql_major": server_major,
                "schema_consistency": "passed",
            }
            if snapshot_path:
                snapshot_path.write_text(
                    json.dumps(summary, sort_keys=True), encoding="utf-8"
                )
            print(json.dumps(summary, sort_keys=True))
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Validate a Mirai release database.")
    parser.add_argument("--expect-data", action="store_true")
    parser.add_argument("--snapshot")
    args = parser.parse_args()
    try:
        validate_database(
            os.getenv("DATABASE_URL", ""),
            expect_data=args.expect_data,
            snapshot_path=Path(args.snapshot) if args.snapshot else None,
        )
    except Exception as error:  # noqa: BLE001 - never expose driver errors or database URLs
        if isinstance(error, ReleaseDatabaseError):
            print(str(error))
        else:
            print("release_database_validation_failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
