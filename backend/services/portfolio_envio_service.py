from datetime import datetime, timezone

from crud import crud_producao
from fastapi import HTTPException
from models import PortfolioEnvioModel, ProjetoModel, UsuarioModel
from schemas.projeto import CreditoProjeto, ProjetoCreate
from services import audit_service
from services.portfolio_service import apply_project_data
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def enviar(db, actor, payload):
    data = payload.model_dump(mode="json")
    request_id = data.pop("request_id")
    producao_id = data.pop("producao_id")
    data.pop("autorizacao_artista")
    # Validate credit semantics now, not only when an administrator tries to approve it.
    CreditoProjeto(funcao=data["funcao"], funcao_outra=data.get("funcao_outra"), nome=actor.username)
    if producao_id is not None and not crud_producao.buscar_por_produtor(db, producao_id, actor.id):
        raise HTTPException(404, "Producao nao encontrada.")
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
    db.commit()
    db.refresh(item)
    return item


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
