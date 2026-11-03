"""Admin preview: see a client or producer portal as that account, read-only.

The admin picks a real account; the API issues a 30-minute preview token (its own type,
never a normal session) and every request with it may only read (core.dependencies).
Each session opened is recorded in the audit log with the admin and the account.
"""
from core.security import PREVIEW_TOKEN_MINUTES, create_preview_token
from fastapi import HTTPException
from models import ClienteModel, UsuarioModel
from services import audit_service
from sqlalchemy import func, or_, select

PORTAIS = {"cliente": "/cliente", "produtor": "/produtor"}


def _nome(usuario):
    cliente = getattr(usuario, "cliente", None)
    return (usuario.nome_exibicao or (cliente.nome if cliente else None) or usuario.username).strip()


def _conta(usuario):
    return {
        "id": usuario.id,
        "nome": _nome(usuario),
        "login": usuario.username,
        "portal": usuario.role,
        "teste": bool(usuario.is_test),
    }


def contas(db, portal=None, busca="", limite=20):
    """Active client and producer accounts that can be previewed, by name or login."""
    roles = [portal] if portal in PORTAIS else list(PORTAIS)
    query = (
        select(UsuarioModel)
        .outerjoin(ClienteModel, ClienteModel.id == UsuarioModel.cliente_id)
        .where(UsuarioModel.ativo.is_(True), UsuarioModel.is_admin.is_(False), UsuarioModel.role.in_(roles))
    )
    termo = (busca or "").strip().lower()[:80]
    if termo:
        like = f"%{termo}%"
        query = query.where(or_(
            func.lower(UsuarioModel.username).like(like),
            func.lower(func.coalesce(UsuarioModel.nome_exibicao, "")).like(like),
            func.lower(func.coalesce(ClienteModel.nome, "")).like(like),
        ))
    query = query.order_by(UsuarioModel.is_test.asc(), func.lower(func.coalesce(UsuarioModel.nome_exibicao, ClienteModel.nome, UsuarioModel.username))).limit(limite)
    return [_conta(item) for item in db.scalars(query).all()]


def abrir(db, admin, usuario_id, request_id=None):
    usuario = db.get(UsuarioModel, usuario_id)
    if usuario is None or not usuario.ativo or usuario.is_admin or usuario.role not in PORTAIS:
        raise HTTPException(404, "Conta de cliente ou produtor não encontrada.")
    if usuario.role == "cliente" and usuario.cliente_id is None:
        raise HTTPException(404, "Conta de cliente ou produtor não encontrada.")
    token, expira = create_preview_token(usuario, admin)
    audit_service.record(
        db, actor=admin, action="admin.preview_started", entity_type="user", entity_id=usuario.id,
        metadata={"portal": usuario.role}, request_id=request_id,
    )
    db.commit()
    return {
        "token": token,
        "expira_em": expira,
        "minutos": PREVIEW_TOKEN_MINUTES,
        "portal": usuario.role,
        "inicio": PORTAIS[usuario.role],
        "conta": _conta(usuario),
    }
