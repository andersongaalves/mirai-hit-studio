"""Sanitized, read-only Storage lifecycle inventory."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from models.portal_produtor import ProducaoArquivoModel
from models.projeto import ProjetoModel
from models.proposta import PropostaModel
from services.storage.lifecycle import RetentionPolicy, plan_production_files, summarize


def inventory(database_url: str, *, superseded_days: int | None) -> dict:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as db:
            files = db.scalars(select(ProducaoArquivoModel)).all()
            decisions = plan_production_files(
                files,
                now=datetime.now(timezone.utc),
                policy=RetentionPolicy(superseded_days=superseded_days),
            )
            return {
                "mode": "dry-run",
                "production_files": len(files),
                "production_decisions": summarize(decisions),
                "proposal_documents": db.scalar(
                    select(func.count()).select_from(PropostaModel).where(
                        PropostaModel.pdf_path.is_not(None)
                    )
                ),
                "portfolio_images": db.scalar(
                    select(func.count()).select_from(ProjetoModel).where(
                        ProjetoModel.link_capa != ""
                    )
                ),
                "portfolio_audio_references": db.scalar(
                    select(func.count()).select_from(ProjetoModel).where(
                        (ProjetoModel.audio_before_key.is_not(None))
                        | (ProjetoModel.audio_after_key.is_not(None))
                    )
                ),
                "remote_orphans": "not_evaluated_provider_listing_unavailable",
                "deletions": 0,
            }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--superseded-retention-days", type=int)
    args = parser.parse_args()
    print(json.dumps(inventory(
        args.database_url,
        superseded_days=args.superseded_retention_days,
    ), sort_keys=True))


if __name__ == "__main__":
    main()
