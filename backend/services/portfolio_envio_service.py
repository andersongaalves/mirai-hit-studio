import hashlib
import logging
from datetime import datetime, timezone

from crud import crud_producao
from fastapi import HTTPException
from models import PortfolioEnvioModel, ProjetoModel, UsuarioModel
from schemas.portfolio_envio import PortfolioEnvioCreate
from schemas.projeto import CreditoProjeto, ProjetoCreate
from services import audit_service
from services.portfolio_service import apply_project_data
from services.storage.contracts import (
    StorageError,
    StorageScope,
    StorageValidationError,
)
from services.storage.policies import DEFAULT_POLICIES
from services.storage.registry import storage_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger(__name__)


def _dados(db, actor, payload):
    data = payload.model_dump(mode="json")
    request_id = data.pop("request_id")
    producao_id = data.pop("producao_id")
    data.pop("autorizacao_artista")
    # Validate credit semantics now, not only when an administrator tries to approve it.
    CreditoProjeto(funcao=data["funcao"], funcao_outra=data.get("funcao_outra"), nome=actor.username)
    if producao_id is not None and not crud_producao.buscar_por_produtor(db, producao_id, actor.id):
        raise HTTPException(404, "Producao nao encontrada.")
    return request_id, producao_id, data


def _existente(db, actor, request_id):
    return db.scalar(select(PortfolioEnvioModel).where(
        PortfolioEnvioModel.produtor_id == actor.id, PortfolioEnvioModel.request_id == request_id,
    ))


def enviar(db, actor, payload, *, capa_sha256=None):
    request_id, producao_id, data = _dados(db, actor, payload)
    if capa_sha256 is not None:
        data["_capa_sha256"] = capa_sha256
    existing = db.scalar(select(PortfolioEnvioModel).where(
        PortfolioEnvioModel.produtor_id == actor.id, PortfolioEnvioModel.request_id == request_id,
    ))
    if existing is not None:
        return _replay(existing, data, producao_id)
    item = PortfolioEnvioModel(
        produtor_id=actor.id, producao_id=producao_id, request_id=request_id, dados=data,
        autorizado_em=datetime.now(timezone.utc),
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(PortfolioEnvioModel).where(
            PortfolioEnvioModel.produtor_id == actor.id, PortfolioEnvioModel.request_id == request_id,
        ))
        if existing is None:
            raise
        return _replay(existing, data, producao_id)
    audit_service.record(db, actor=actor, action="portfolio.submitted", entity_type="portfolio_submission",
                         entity_id=item.id, metadata={"producao_id": producao_id, "artist_consent": True})
    from services import portal_notificacao_service

    portal_notificacao_service.portfolio_proposto(db, item)
    db.commit()
    db.refresh(item)
    return item


def enviar_com_capa(db, actor, payload, contents, content_type):
    try:
        DEFAULT_POLICIES[StorageScope.PUBLIC_IMAGE].validate(contents, content_type)
    except StorageValidationError as error:
        raise HTTPException(422, str(error)) from None
    request_id, producao_id, data = _dados(db, actor, payload)
    data["_capa_sha256"] = hashlib.sha256(contents).hexdigest()
    # NO KEY UPDATE serializes uploads without blocking FK references from the URL flow.
    current = db.scalar(select(UsuarioModel).where(UsuarioModel.id == actor.id)
                        .with_for_update(key_share=True).execution_options(populate_existing=True))
    if current is None or not current.ativo or current.role != "produtor" or current.is_admin:
        raise HTTPException(403, "Acesso restrito ao produtor ativo.")
    existing = _existente(db, actor, request_id)
    if existing is not None:
        return _replay(existing, {**data, "link_capa": existing.dados.get("link_capa")}, producao_id)
    stored, url = None, None
    try:
        storage = storage_for(StorageScope.PUBLIC_IMAGE)
        stored = storage.save(contents, content_type)
        url = stored.public_url or storage.get_public_url(stored.reference)
        validated = PortfolioEnvioCreate(**payload.model_dump(), link_capa=url)
        return enviar(db, actor, validated, capa_sha256=data["_capa_sha256"])
    except Exception as error:
        db.rollback()
        if stored is not None:
            # A failed commit acknowledgement must not delete an already-linked cover.
            try:
                persisted = _existente(db, actor, request_id)
            except SQLAlchemyError:
                logger.error("portfolio_cover_outcome_unknown request_id=%s", request_id)
                raise HTTPException(503, "Nao foi possivel confirmar o envio. Tente novamente com os mesmos dados.") from None
            if url is not None and persisted is not None and persisted.dados.get("link_capa") == url:
                return _replay(persisted, {**data, "link_capa": url}, producao_id)
            try:
                storage.delete(stored.reference)
            except StorageError:
                logger.warning("portfolio_cover_compensation_failed request_id=%s", request_id)
        if isinstance(error, HTTPException):
            raise
        if isinstance(error, StorageValidationError):
            raise HTTPException(422, str(error)) from None
        if isinstance(error, StorageError):
            raise HTTPException(503, "O envio da capa esta temporariamente indisponivel.") from None
        logger.error("portfolio_cover_submission_failed request_id=%s", request_id)
        raise HTTPException(503, "Nao foi possivel confirmar o envio. Tente novamente com os mesmos dados.") from None


def _replay(item, data, producao_id):
    if item.dados != data or item.producao_id != producao_id:
        raise HTTPException(409, "Este envio ja foi registrado com outros dados.")
    return item


def revisar(db, actor, envio_id, payload):
    item = db.scalar(select(PortfolioEnvioModel).where(PortfolioEnvioModel.id == envio_id).with_for_update())
    if item is None:
        raise HTTPException(404, "Envio nao encontrado.")
    target = "aprovado" if payload.decisao == "aprovar" else "recusado"
    # A repeated decision is idempotent; a different decision cannot overwrite history.
    if item.status == target:
        return item
    if item.status != "pendente" or item.versao != payload.versao:
        raise HTTPException(409, "Este envio ja foi revisado. Atualize a lista.")
    if target == "recusado" and not (payload.motivo or "").strip():
        raise HTTPException(422, "Informe o motivo da recusa.")
    if target == "aprovado":
        produtor = db.get(UsuarioModel, item.produtor_id)
        if produtor is None or not produtor.ativo or produtor.role != "produtor" or produtor.is_admin:
            raise HTTPException(409, "O produtor nao esta ativo para publicacao.")
        data = dict(item.dados)
        data.pop("_capa_sha256", None)
        funcao, outra = data.pop("funcao"), data.pop("funcao_outra", None)
        data["creditos"] = [{"funcao": funcao, "funcao_outra": outra,
                             "nome": produtor.nome_exibicao or produtor.username, "usuario_id": produtor.id}]
        validated = ProjetoCreate(**data)
        project = ProjetoModel()
        db.add(project)
        apply_project_data(db, project, validated.model_dump())
        db.flush()
        item.projeto_id = project.id
    item.status = target
    item.versao += 1
    item.revisado_por = actor.id
    item.revisado_em = datetime.now(timezone.utc)
    item.motivo = payload.motivo.strip() if payload.motivo else None
    audit_service.record(db, actor=actor, action="portfolio.reviewed", entity_type="portfolio_submission",
                         entity_id=item.id, metadata={"status": target, "projeto_id": item.projeto_id})
    db.commit()
    db.refresh(item)
    return item
