"""Transactional portfolio rules shared by project routes."""

from fastapi import HTTPException
from sqlalchemy import select, text

from models import ProjetoCreditoModel, ProjetoModel, UsuarioModel
from services.portfolio_segments_service import validate_project_segments

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


def replace_credits(db, project: ProjetoModel, creditos: list[dict]) -> None:
    """Roadmap 5.19: the ordered list replaces the previous one; linked accounts must be active producers."""
    ids = {credito["usuario_id"] for credito in creditos if credito.get("usuario_id") is not None}
    contas = {}
    if ids:
        contas = {conta.id: conta for conta in db.scalars(select(UsuarioModel).where(
            UsuarioModel.id.in_(ids), UsuarioModel.ativo.is_(True), UsuarioModel.role == "produtor",
            UsuarioModel.is_admin.is_(False),
        ))}
        if ids - set(contas):
            raise HTTPException(status_code=422, detail="Credito vinculado a um produtor inexistente ou inativo.")
    project.creditos.clear()
    db.flush()  # Old rows go first so the (projeto_id, ordem) uniqueness never collides.
    for ordem, credito in enumerate(creditos, start=1):
        project.creditos.append(ProjetoCreditoModel(
            ordem=ordem,
            funcao=credito["funcao"],
            funcao_outra=credito.get("funcao_outra"),
            # A linked account is credited by its display name (kept as fallback if it is removed).
            nome=getattr(contas.get(credito.get("usuario_id")), "nome_exibicao", None) or credito["nome"],
            usuario_id=credito.get("usuario_id"),
        ))


def apply_project_data(db, project: ProjetoModel, data: dict) -> None:
    creditos = data.pop("creditos", None)
    if "segmentos_json" in data:
        validate_project_segments(
            db,
            current=project.segmentos_json or [],
            proposed=data["segmentos_json"],
        )
    comparison_changed = bool(
        {"show_mix_comparison_on_landing", "landing_order"}.intersection(data)
    )
    classification_changed = bool({"vertical", "case_type"}.intersection(data))
    enabled = data.pop(
        "show_mix_comparison_on_landing",
        project.show_mix_comparison_on_landing or False,
    )
    order = data.pop("landing_order", project.landing_order)
    for field, value in data.items():
        setattr(project, field, value)
    if creditos is not None:
        replace_credits(db, project, creditos)

    if not comparison_changed and not (
        classification_changed and project.show_mix_comparison_on_landing
    ):
        return

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
