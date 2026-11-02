"""Pop-ups sent by the Admin to the client and producer portals."""
from datetime import datetime, timezone

from fastapi import HTTPException
from models import PortalPopupModel, PortalPopupVistoModel
from services import audit_service
from sqlalchemy import func, or_, select


def _agora():
    return datetime.now(timezone.utc)


def listar_admin(db):
    counts = dict(db.execute(
        select(PortalPopupVistoModel.popup_id, func.count(PortalPopupVistoModel.id)).group_by(PortalPopupVistoModel.popup_id)
    ).all())
    rows = db.scalars(select(PortalPopupModel).order_by(PortalPopupModel.created_at.desc(), PortalPopupModel.id.desc())).all()
    for row in rows:
        row.fechamentos = counts.get(row.id, 0)
    return rows


def _get(db, popup_id):
    model = db.get(PortalPopupModel, popup_id)
    if model is None:
        raise HTTPException(404, "Pop-up nao encontrado.")
    return model


def criar(db, actor, dados):
    model = PortalPopupModel(**dados.model_dump(), autor_usuario_id=actor.id)
    db.add(model)
    db.flush()
    audit_service.record(db, actor=actor, action="portal_popup.created", entity_type="portal_popup", entity_id=model.id,
                         metadata={"publico": model.publico, "ativo": model.ativo})
    db.commit()
    db.refresh(model)
    model.fechamentos = 0
    return model


def atualizar(db, actor, popup_id, dados):
    model = _get(db, popup_id)
    for key, value in dados.model_dump().items():
        setattr(model, key, value)
    audit_service.record(db, actor=actor, action="portal_popup.updated", entity_type="portal_popup", entity_id=model.id,
                         metadata={"publico": model.publico, "ativo": model.ativo})
    db.commit()
    db.refresh(model)
    model.fechamentos = db.scalar(select(func.count(PortalPopupVistoModel.id)).where(PortalPopupVistoModel.popup_id == model.id)) or 0
    return model


def excluir(db, actor, popup_id):
    model = _get(db, popup_id)
    audit_service.record(db, actor=actor, action="portal_popup.deleted", entity_type="portal_popup", entity_id=model.id,
                         metadata={"titulo": model.titulo})
    db.delete(model)
    db.commit()


def _ativos(db, papel):
    now = _agora()
    return select(PortalPopupModel).where(
        PortalPopupModel.ativo.is_(True),
        PortalPopupModel.publico.in_((papel, "todos")),
        or_(PortalPopupModel.inicio.is_(None), PortalPopupModel.inicio <= now),
        or_(PortalPopupModel.fim.is_(None), PortalPopupModel.fim > now),
    )


def para_usuario(db, usuario, papel):
    """Active pop-ups for this portal; "show once" ones the user already closed stay closed."""
    vistos = select(PortalPopupVistoModel.popup_id).where(PortalPopupVistoModel.usuario_id == usuario.id)
    query = _ativos(db, papel).where(
        or_(PortalPopupModel.frequencia != "uma_vez", PortalPopupModel.id.notin_(vistos))
    ).order_by(PortalPopupModel.created_at.asc(), PortalPopupModel.id.asc())
    return db.scalars(query).all()


def fechar(db, usuario, papel, popup_id):
    model = db.scalar(_ativos(db, papel).where(PortalPopupModel.id == popup_id))
    if model is None:
        raise HTTPException(404, "Pop-up nao encontrado.")
    exists = db.scalar(select(PortalPopupVistoModel.id).where(
        PortalPopupVistoModel.popup_id == popup_id, PortalPopupVistoModel.usuario_id == usuario.id))
    if exists is None:
        db.add(PortalPopupVistoModel(popup_id=popup_id, usuario_id=usuario.id))
        db.commit()
