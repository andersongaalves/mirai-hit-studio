"""AUD6-S02-004: password recovery and self-service password change for studio accounts.

Clients keep their own recovery through ClienteAcessoModel. Admin and producer accounts use
the e-mail registered by the studio and a one-time token stored as a SHA-256 hash.
"""
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from core.config import settings
from core.security import get_password_hash, verify_password
from database import SessionLocal
from models.usuario import UsuarioModel
from services import audit_service
from services.email_service import EmailService
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

RECOVERY_TTL = timedelta(minutes=60)
INTERNAL_ROLES = ("admin", "produtor")


class SenhaAtualIncorreta(Exception):
    pass


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def conta_por_email(db, email):
    if not email:
        return None
    return db.scalar(
        select(UsuarioModel)
        .where(func.lower(UsuarioModel.email) == email.strip().lower())
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def preparar_recuperacao(db, email, *, token_pair, request_id=None):
    """Returns a delivery dict when an active studio account owns the e-mail; never commits on its own."""
    user = conta_por_email(db, email)
    if user is None or not user.ativo or user.role not in INTERNAL_ROLES:
        return None
    raw_token, token_hash = token_pair
    user.reset_token_hash = token_hash
    user.reset_expires_at = _now() + RECOVERY_TTL
    audit_service.record(
        db, actor=None, action="user.recovery_requested", entity_type="user", entity_id=user.id,
        metadata={"result": "eligible"}, request_id=request_id,
    )
    return {"kind": "interna", "user_id": user.id, "raw_token": raw_token, "token_hash": token_hash,
            "request_id": request_id}


def entregar_recuperacao(delivery):
    with SessionLocal() as db:
        user = db.get(UsuarioModel, delivery["user_id"])
        if user is None or user.reset_token_hash != delivery["token_hash"] or not user.email:
            logger.warning("internal_recovery_delivery_cancelled request_id=%s", delivery["request_id"])
            return
        base_url = settings.PUBLIC_FRONTEND_URL.rstrip("/")
        url = f"{base_url}/redefinir-senha?token={delivery['raw_token']}"
        destinatario = SimpleNamespace(nome=user.nome_exibicao or user.username, email=user.email)
        try:
            EmailService.enviar_recuperacao_senha(
                destinatario, url, idempotency_key=f"internal-recovery/{user.id}/{delivery['token_hash'][:16]}")
        except Exception:  # noqa: BLE001 - provider SDK errors are not stable API types.
            logger.error("internal_recovery_delivery_failed request_id=%s", delivery["request_id"])


def redefinir_por_token(db, token_hash, nova_senha, *, request_id=None):
    """Returns the user when the token belongs to a studio account; None lets the caller decide."""
    user = db.scalar(
        select(UsuarioModel).where(UsuarioModel.reset_token_hash == token_hash)
        .with_for_update().execution_options(populate_existing=True)
    )
    if user is None:
        return None
    if (not user.ativo or user.role not in INTERNAL_ROLES or user.reset_expires_at is None
            or _aware(user.reset_expires_at) <= _now()):
        user.reset_token_hash = None
        user.reset_expires_at = None
        db.commit()
        return False
    user.password_hash = get_password_hash(nova_senha)
    user.auth_version += 1
    user.reset_token_hash = None
    user.reset_expires_at = None
    audit_service.record(db, actor=user, action="user.password_recovered", entity_type="user",
                         entity_id=user.id, request_id=request_id)
    db.commit()
    return user


def trocar_senha(db, user_id, senha_atual, nova_senha, *, request_id=None):
    """Changes the own password; every other session ends (auth_version)."""
    user = db.scalar(select(UsuarioModel).where(UsuarioModel.id == user_id)
                     .with_for_update().execution_options(populate_existing=True))
    if user is None or not user.ativo or not verify_password(senha_atual, user.password_hash):
        db.rollback()
        raise SenhaAtualIncorreta("Senha atual incorreta.")
    user.password_hash = get_password_hash(nova_senha)
    user.auth_version += 1
    user.reset_token_hash = None
    user.reset_expires_at = None
    audit_service.record(db, actor=user, action="user.password_changed", entity_type="user",
                         entity_id=user.id, request_id=request_id)
    db.commit()
    db.refresh(user)
    return user


def encerrar_sessoes(db, user_id, *, request_id=None):
    """AUD6-S02-006: "Sair de todos os aparelhos" ends every session, this one included."""
    user = db.scalar(select(UsuarioModel).where(UsuarioModel.id == user_id)
                     .with_for_update().execution_options(populate_existing=True))
    if user is None or not user.ativo:
        db.rollback()
        return None
    user.auth_version += 1
    audit_service.record(db, actor=user, action="user.sessions_revoked", entity_type="user",
                         entity_id=user.id, request_id=request_id)
    db.commit()
    return user
