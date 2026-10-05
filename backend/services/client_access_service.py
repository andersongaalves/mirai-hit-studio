import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from core.config import settings
from core.security import get_password_hash
from models.client_access import AuthRateLimitModel, ClienteAcessoModel
from models.cliente import ClienteModel
from models.enums.proposta import PropostaStatus
from models.orcamento import OrcamentoModel
from models.proposta import PropostaModel
from models.usuario import UsuarioModel
from pydantic import EmailStr, TypeAdapter, ValidationError
from schemas.client_access import ClientAccessStatus, ClientInviteActivation
from services import audit_service
from services.cliente_service import normalizar_email
from services.email_service import EmailService
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
INVITE_TTL = timedelta(hours=48)


class ClientAccessError(Exception):
    pass


class ClientAccessNotFound(ClientAccessError):
    pass


class ClientAccessInvalid(ClientAccessError):
    pass


class ClientAccessConflict(ClientAccessError):
    pass


class ClientAccessRateLimited(ClientAccessError):
    pass


class ClientAccessDeliveryUnavailable(ClientAccessError):
    pass


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _token():
    raw = secrets.token_urlsafe(48)
    return raw, _hash(raw)


def _rate_key(action: str, key: str) -> str:
    return _hash(f"client-access:{action}:{key}")


def enforce_rate_limit(
    db: Session,
    *,
    action: str,
    key: str,
    limit: int,
    window: timedelta,
):
    now = _now()
    expires_at = now + window
    key_hash = _rate_key(action, key)
    statement = text("""
        INSERT INTO auth_rate_limits (
            key_hash, action, window_started_at, request_count, expires_at,
            created_at, updated_at
        ) VALUES (
            :key_hash, :action, :now, 1, :expires_at, :now, :now
        )
        ON CONFLICT (key_hash) DO UPDATE SET
            action = :action,
            request_count = CASE
                WHEN auth_rate_limits.expires_at <= :now THEN 1
                ELSE auth_rate_limits.request_count + 1
            END,
            window_started_at = CASE
                WHEN auth_rate_limits.expires_at <= :now THEN :now
                ELSE auth_rate_limits.window_started_at
            END,
            expires_at = CASE
                WHEN auth_rate_limits.expires_at <= :now THEN :expires_at
                ELSE auth_rate_limits.expires_at
            END,
            updated_at = :now
        RETURNING request_count
    """)
    try:
        count = db.execute(statement, {
            "key_hash": key_hash,
            "action": action,
            "now": now,
            "expires_at": expires_at,
        }).scalar_one()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    if count > limit:
        raise ClientAccessRateLimited("Muitas tentativas. Aguarde antes de tentar novamente.")


def _commercial_context(db: Session, proposta_id: int, *, lock=False):
    proposal_query = select(PropostaModel).where(PropostaModel.id == proposta_id)
    if lock:
        proposal_query = proposal_query.with_for_update().execution_options(populate_existing=True)
    proposal = db.scalar(proposal_query)
    if proposal is None:
        raise ClientAccessNotFound("Proposta nao encontrada.")
    if proposal.status != PropostaStatus.ACEITA.value or proposal.aprovada_em is None:
        raise ClientAccessInvalid("Somente propostas aceitas podem conceder acesso ao portal.")
    budget_query = select(OrcamentoModel).where(OrcamentoModel.id == proposal.orcamento_id)
    if lock:
        budget_query = budget_query.with_for_update().execution_options(populate_existing=True)
    budget = db.scalar(budget_query)
    if budget is None or budget.cliente_id is None:
        raise ClientAccessConflict("A contratacao nao possui cliente comercial vinculado.")
    client = db.get(ClienteModel, budget.cliente_id)
    if client is None:
        raise ClientAccessConflict("O cliente comercial vinculado nao existe.")
    return proposal, budget, client


def _user_for_client(db: Session, cliente_id: int):
    return db.scalar(select(UsuarioModel).where(UsuarioModel.cliente_id == cliente_id))


def _access_for_client(db: Session, cliente_id: int, *, lock=False):
    query = select(ClienteAcessoModel).where(ClienteAcessoModel.cliente_id == cliente_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return db.scalar(query)


def _state(access, user, now):
    if user is not None:
        return "conta_ativa" if user.ativo else "conta_desativada"
    if access is None:
        return "sem_acesso"
    if access.usuario_id is not None:
        return "conflito"
    if access.token_consumed_at is not None:
        return "conflito"
    if access.token_revoked_at is not None:
        return "convite_revogado"
    if _aware(access.token_expires_at) <= now:
        return "convite_expirado"
    return "convite_pendente"


def _response(proposal, client, access, user):
    return ClientAccessStatus(
        proposta_id=proposal.id,
        cliente_id=client.id,
        cliente_nome=client.nome,
        email=client.email,
        proposta_status=proposal.status,
        estado=_state(access, user, _now()),
        usuario_id=user.id if user else None,
        last_sent_at=access.last_sent_at if access else None,
        expires_at=access.token_expires_at if access else None,
        send_count=access.send_count if access else 0,
    )


def status(db: Session, proposta_id: int):
    proposal, _, client = _commercial_context(db, proposta_id)
    access = _access_for_client(db, client.id)
    user = _user_for_client(db, client.id)
    if access and access.usuario_id and (user is None or access.usuario_id != user.id):
        return _response(proposal, client, access, None).model_copy(update={"estado": "conflito"})
    return _response(proposal, client, access, user)


def _prepare_invite(db, proposta_id, actor, request_id, *, resend):
    proposal, _, client = _commercial_context(db, proposta_id, lock=True)
    if not client.ativo:
        raise ClientAccessConflict("O cliente comercial esta inativo.")
    try:
        email = normalizar_email(str(TypeAdapter(EmailStr).validate_python(client.email)))
    except ValidationError:
        email = None
    if email is None:
        raise ClientAccessInvalid("Este cliente precisa de um e-mail valido antes de receber acesso ao portal.")
    user = _user_for_client(db, client.id)
    if user is not None:
        raise ClientAccessConflict("Cliente ja possui acesso ao portal.")
    access = _access_for_client(db, client.id, lock=True)
    if access and access.usuario_id is not None:
        raise ClientAccessConflict("Conflito de vinculo. Conciliacao necessaria.")
    if access and access.email_normalizado != email:
        raise ClientAccessConflict("O e-mail do acesso diverge do cliente. Conciliacao necessaria.")
    if access and access.token_consumed_at is not None:
        raise ClientAccessConflict("O convite ja foi utilizado. Conciliacao necessaria.")
    if access and not resend and access.token_revoked_at is None and _aware(access.token_expires_at) > _now():
        raise ClientAccessConflict("Ja existe um convite pendente para este cliente.")

    raw_token, token_hash = _token()
    now = _now()
    if access is None:
        access = ClienteAcessoModel(
            cliente_id=client.id,
            email_normalizado=email,
            origem="admin_invite",
            invited_by_user_id=actor.id,
        )
        db.add(access)
    access.token_finalidade = "convite"
    access.token_hash = token_hash
    access.token_expires_at = now + INVITE_TTL
    access.token_consumed_at = None
    access.token_revoked_at = None
    access.updated_at = now
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action="client_access.invite_resent" if resend else "client_access.invite_created",
        entity_type="client_access",
        entity_id=access.id,
        metadata={"client_id": client.id, "proposal_id": proposal.id},
        request_id=request_id,
    )
    db.commit()
    return proposal, client, access.id, raw_token, token_hash


def _deliver(db, proposal, client, access_id, raw_token, token_hash, actor, request_id):
    base_url = settings.PUBLIC_FRONTEND_URL.rstrip("/")
    activation_url = f"{base_url}/ativar?token={raw_token}"
    try:
        provider = EmailService.enviar_convite_cliente(
            client,
            activation_url,
            idempotency_key=f"client-invite/{access_id}/{token_hash[:16]}",
        )
        if not isinstance(provider, dict) or not isinstance(provider.get("id"), str) or not provider["id"].strip():
            raise ValueError("invalid_provider_response")
    except Exception:  # noqa: BLE001 - provider SDK errors are not stable API types.
        logger.error("client_invite_delivery_failed request_id=%s", request_id)
        try:
            audit_service.record(
                db,
                actor=actor,
                action="client_access.invite_delivery_failed",
                entity_type="client_access",
                entity_id=access_id,
                metadata={"client_id": client.id, "proposal_id": proposal.id},
                request_id=request_id,
            )
            db.commit()
        except Exception:  # noqa: BLE001 - audit failure must not expose provider data.
            db.rollback()
        raise ClientAccessDeliveryUnavailable(
            "Convite provisionado, mas o e-mail nao foi confirmado. Use Reenviar convite."
        ) from None

    try:
        access = db.get(ClienteAcessoModel, access_id)
        if access is None or access.token_hash != token_hash:
            raise ClientAccessConflict("O convite mudou durante o envio. Conciliacao necessaria.")
        access.last_sent_at = _now()
        access.send_count += 1
        access.updated_at = _now()
        db.commit()
        return _response(proposal, client, access, None)
    except Exception:  # noqa: BLE001 - commit failures make provider delivery uncertain.
        db.rollback()
        logger.error("client_invite_delivery_uncertain request_id=%s", request_id)
        raise ClientAccessDeliveryUnavailable(
            "E-mail aceito pelo provedor, mas o registro local nao foi confirmado. Concilie antes de repetir."
        ) from None


def invite(db, proposta_id, actor, request_id, source_key):
    enforce_rate_limit(
        db,
        action="confirmation",
        key=f"{actor.id}:{proposta_id}:{source_key}",
        limit=5,
        window=timedelta(hours=1),
    )
    try:
        prepared = _prepare_invite(db, proposta_id, actor, request_id, resend=False)
    except IntegrityError:
        db.rollback()
        raise ClientAccessConflict("O convite ja foi criado ou exige conciliacao.") from None
    except Exception:
        db.rollback()
        raise
    return _deliver(db, *prepared, actor, request_id)


def resend(db, proposta_id, actor, request_id, source_key):
    enforce_rate_limit(
        db,
        action="resend",
        key=f"{actor.id}:{proposta_id}:{source_key}",
        limit=5,
        window=timedelta(hours=1),
    )
    try:
        prepared = _prepare_invite(db, proposta_id, actor, request_id, resend=True)
    except IntegrityError:
        db.rollback()
        raise ClientAccessConflict("O convite mudou ou exige conciliacao.") from None
    except Exception:
        db.rollback()
        raise
    return _deliver(db, *prepared, actor, request_id)


def revoke(db, proposta_id, actor, request_id):
    try:
        proposal, _, client = _commercial_context(db, proposta_id, lock=True)
        user = _user_for_client(db, client.id)
        if user is not None:
            raise ClientAccessConflict("A conta ja esta ativa; gerencie o usuario em vez do convite.")
        access = _access_for_client(db, client.id, lock=True)
        if access is None or access.token_consumed_at is not None:
            raise ClientAccessConflict("Nao existe convite pendente revogavel.")
        access.token_revoked_at = _now()
        access.updated_at = _now()
        audit_service.record(
            db,
            actor=actor,
            action="client_access.invite_revoked",
            entity_type="client_access",
            entity_id=access.id,
            metadata={"client_id": client.id, "proposal_id": proposal.id},
            request_id=request_id,
        )
        db.commit()
        return _response(proposal, client, access, None)
    except Exception:
        db.rollback()
        raise


def _access_by_token(db: Session, raw_token: str, *, lock=False):
    token_hash = _hash(raw_token)
    query = select(ClienteAcessoModel).where(
        ClienteAcessoModel.token_hash == token_hash,
        ClienteAcessoModel.token_finalidade == "convite",
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return db.scalar(query)


def token_state(db: Session, raw_token: str, source_key: str):
    enforce_rate_limit(
        db,
        action="activation",
        key=source_key,
        limit=10,
        window=timedelta(minutes=15),
    )
    access = _access_by_token(db, raw_token)
    if access is None:
        raise ClientAccessInvalid("Convite invalido ou indisponivel.")
    if access.token_consumed_at is not None:
        return "utilizado"
    if access.token_revoked_at is not None:
        return "revogado"
    if _aware(access.token_expires_at) <= _now():
        return "expirado"
    return "valido"


def activate(db: Session, data: ClientInviteActivation, source_key: str, request_id: str | None):
    enforce_rate_limit(
        db,
        action="activation",
        key=source_key,
        limit=10,
        window=timedelta(minutes=15),
    )
    try:
        access = _access_by_token(db, data.token, lock=True)
        if access is None:
            raise ClientAccessInvalid("Convite invalido ou indisponivel.")
        access.activation_attempts += 1
        if access.token_consumed_at is not None:
            raise ClientAccessConflict("Este convite ja foi utilizado.")
        if access.token_revoked_at is not None:
            raise ClientAccessConflict("Este convite foi revogado.")
        if _aware(access.token_expires_at) <= _now():
            raise ClientAccessConflict("Este convite expirou.")
        client = db.get(ClienteModel, access.cliente_id)
        if client is None or not client.ativo:
            raise ClientAccessConflict("O acesso do cliente nao esta disponivel.")
        if normalizar_email(client.email) != access.email_normalizado:
            raise ClientAccessConflict("Os dados de identidade mudaram. Solicite um novo convite.")
        if _user_for_client(db, client.id) is not None:
            raise ClientAccessConflict("Cliente ja possui acesso ao portal.")
        if db.scalar(select(UsuarioModel).where(UsuarioModel.username == data.username)) is not None:
            raise ClientAccessConflict("Nome de usuario indisponivel.")
        user = UsuarioModel(
            username=data.username,
            password_hash=get_password_hash(data.password),
            role="cliente",
            is_admin=False,
            ativo=True,
            cliente_id=client.id,
        )
        db.add(user)
        db.flush()
        now = _now()
        access.usuario_id = user.id
        access.token_consumed_at = now
        access.email_verified_at = now
        access.updated_at = now
        audit_service.record(
            db,
            actor=user,
            action="client_access.activated",
            entity_type="client_access",
            entity_id=access.id,
            metadata={"client_id": client.id, "result": "activated"},
            request_id=request_id,
        )
        db.commit()
        return user
    except IntegrityError:
        db.rollback()
        raise ClientAccessConflict("Conta ou vinculo indisponivel. Tente outro usuario.") from None
    except Exception:
        db.rollback()
        raise


def cleanup_expired(db: Session, *, before: datetime | None = None):
    cutoff = before or (_now() - timedelta(days=30))
    deleted_limits = db.query(AuthRateLimitModel).filter(AuthRateLimitModel.expires_at < cutoff).delete()
    deleted_invites = db.query(ClienteAcessoModel).filter(
        ClienteAcessoModel.usuario_id.is_(None),
        ClienteAcessoModel.token_expires_at < cutoff,
    ).delete()
    db.commit()
    return deleted_invites, deleted_limits
