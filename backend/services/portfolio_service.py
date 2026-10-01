"""Transactional portfolio rules shared by project routes."""

from fastapi import HTTPException
from sqlalchemy import text

from models import ProjetoModel

PUBLIC_VERTICALS = ("artists", "creators", "media_games")
PUBLIC_CASE_TYPES = ("client_case", "demo", "concept_project", "study")
MAX_LANDING_COMPARISONS = 4
_MIX_COMPARISON_LOCK_KEY = 1296585521


def is_publishable(project: ProjetoModel) -> bool:
    return project.vertical in PUBLIC_VERTICALS and project.case_type in PUBLIC_CASE_TYPES


def lock_mix_comparisons(db) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _MIX_COMPARISON_LOCK_KEY},
        )


def _featured_projects(db, *, exclude_id=None):
    query = db.query(ProjetoModel).filter(
        ProjetoModel.show_mix_comparison_on_landing.is_(True)
    )
    if exclude_id is not None:
        query = query.filter(ProjetoModel.id != exclude_id)
    return query.order_by(ProjetoModel.landing_order, ProjetoModel.id).all()


def configure_landing_comparison(db, project: ProjetoModel, enabled: bool, order: int | None) -> None:
    lock_mix_comparisons(db)
    featured = _featured_projects(db, exclude_id=project.id)

    if enabled:
        if not project.audio_before_key or not project.audio_after_key:
            raise HTTPException(
                status_code=409,
                detail="Adicione os audios Antes e Depois para destacar este projeto.",
            )
        if not is_publishable(project):
            raise HTTPException(
                status_code=409,
                detail="Classifique o projeto para publicacao antes de destaca-lo.",
            )
        if len(featured) >= MAX_LANDING_COMPARISONS:
            raise HTTPException(
                status_code=409,
                detail="Limite de 4 comparacoes destacadas na landing atingido.",
            )
        insertion = min(max((order or len(featured) + 1) - 1, 0), len(featured))
        featured.insert(insertion, project)

    affected = _featured_projects(db)
    if project not in affected:
        affected.append(project)
    for item in affected:
        item.landing_order = None
        item.show_mix_comparison_on_landing = False
    db.flush()

    for position, item in enumerate(featured, start=1):
        item.show_mix_comparison_on_landing = True
        item.landing_order = position


def apply_project_data(db, project: ProjetoModel, data: dict) -> None:
    enabled = data.pop("show_mix_comparison_on_landing", False)
    order = data.pop("landing_order", None)
    for field, value in data.items():
        setattr(project, field, value)

    if enabled and not is_publishable(project):
        configure_landing_comparison(db, project, False, None)
        raise HTTPException(
            status_code=409,
            detail="Classifique o projeto para publicacao antes de destaca-lo.",
        )
    configure_landing_comparison(db, project, enabled, order)


def set_audio_key(db, project: ProjetoModel, slot: str, key: str | None) -> None:
    setattr(project, f"audio_{slot}_key", key)
    if key is None and project.show_mix_comparison_on_landing:
        configure_landing_comparison(db, project, False, None)


def delete_project_and_reorder(db, project: ProjetoModel) -> None:
    was_featured = project.show_mix_comparison_on_landing
    if was_featured:
        configure_landing_comparison(db, project, False, None)
    db.delete(project)
