"""Inventory or copy legacy private Production files to configured R2 buckets."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter

from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.portal_produtor import ProducaoArquivoModel
from services import audit_service
from services.storage.contracts import ObjectReference, StorageScope
from services.storage.legacy import SupabaseProductionAdapter
from services.storage.migration import (
    MigrationCandidate,
    StorageMigrationError,
    migrate_candidate,
)
from services.storage.registry import storage_for

FINAL_TYPES = {"entrega", "comprovante"}


def _scope(file_type: str) -> StorageScope:
    return (
        StorageScope.PRODUCTION_FINAL
        if file_type in FINAL_TYPES
        else StorageScope.PRODUCTION_TEMP
    )


def _provider(value: str) -> str:
    return value.split("://", 1)[0] if "://" in value else "supabase_legacy"


def inventory(db: Session) -> dict:
    rows = db.scalars(select(ProducaoArquivoModel)).all()
    providers = Counter(_provider(row.object_key) for row in rows)
    types = Counter(row.tipo for row in rows)
    return {
        "mode": "inventory",
        "total": len(rows),
        "providers": dict(sorted(providers.items())),
        "types": dict(sorted(types.items())),
        "references_printed": 0,
        "deletions": 0,
    }


def _source_reference(adapter: SupabaseProductionAdapter, value: str) -> ObjectReference:
    if "://" in value:
        reference = ObjectReference.parse(value)
        if reference.provider != "supabase":
            raise ValueError("source_provider_not_legacy_supabase")
        return reference
    return ObjectReference("supabase", adapter.bucket, value)


def copy_batch(database_url: str, *, batch_size: int) -> dict:
    engine = create_engine(database_url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        raise RuntimeError("storage_migration_postgresql_required")

    sources = {
        scope: SupabaseProductionAdapter(scope)
        for scope in (StorageScope.PRODUCTION_TEMP, StorageScope.PRODUCTION_FINAL)
    }
    destinations = {
        scope: storage_for(scope)
        for scope in (StorageScope.PRODUCTION_TEMP, StorageScope.PRODUCTION_FINAL)
    }
    summary = Counter()
    try:
        with Session(engine) as db:
            ids = db.scalars(
                select(ProducaoArquivoModel.id)
                .where(~ProducaoArquivoModel.object_key.like("r2://%"))
                .order_by(ProducaoArquivoModel.id)
                .limit(batch_size)
            ).all()

        for record_id in ids:
            try:
                with Session(engine) as db:
                    row = db.scalar(
                        select(ProducaoArquivoModel)
                        .where(ProducaoArquivoModel.id == record_id)
                        .with_for_update()
                    )
                    if row is None or row.object_key.startswith("r2://"):
                        summary["skipped"] += 1
                        continue
                    scope = _scope(row.tipo)
                    source = sources[scope]
                    candidate = MigrationCandidate(
                        record_id=row.id,
                        scope=scope,
                        source=_source_reference(source, row.object_key),
                        content_type=row.mime_type,
                        size=row.tamanho_bytes,
                        sha256=row.sha256,
                    )
                    result = migrate_candidate(
                        candidate,
                        source=source,
                        destination=destinations[scope],
                    )
                    row.object_key = str(result.destination)
                    audit_service.record(
                        db,
                        actor=None,
                        action="storage.production_file_migrated",
                        entity_type="production_file",
                        entity_id=row.id,
                        metadata={"result": "copied_and_verified"},
                    )
                    db.commit()
                    summary["copied" if result.copied else "resumed"] += 1
            except (StorageMigrationError, SQLAlchemyError, ValueError):
                summary["failed"] += 1
        return {
            "mode": "copy",
            "processed": sum(summary.values()),
            "results": dict(sorted(summary.items())),
            "source_deletions": 0,
            "references_printed": 0,
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--mode", choices=("inventory", "copy"), default="inventory")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--confirm-copy", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 500:
        raise SystemExit("invalid_batch_size")
    if args.mode == "copy":
        if not args.confirm_copy or os.environ.get("STORAGE_MIGRATION_WRITE_ENABLED") != "true":
            raise SystemExit("storage_migration_write_not_authorized")
        report = copy_batch(args.database_url, batch_size=args.batch_size)
    else:
        engine = create_engine(args.database_url, pool_pre_ping=True)
        try:
            with Session(engine) as db:
                report = inventory(db)
        finally:
            engine.dispose()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
