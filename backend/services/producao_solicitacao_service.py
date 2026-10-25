import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from models.cliente import ClienteModel
from models.orcamento import OrcamentoModel
from models.servico import ServicoModel
from services import audit_service
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

# AUD6-S07-006: a client account cannot flood the studio with requests.
DAILY_REQUESTS = 5


def solicitar(db, dados, actor):
    client = db.get(ClienteModel, actor.cliente_id)
    if client is None or not client.ativo:
        raise HTTPException(409, "Cadastro do cliente indisponivel.")
    if not client.email:
        raise HTTPException(409, "Complete o e-mail do seu cadastro com a Mirai antes de solicitar.")
    fingerprint = hashlib.sha256(
        f"portal-request:{client.id}:{dados.model_dump_json()}".encode()
    ).hexdigest()
    key = str(dados.request_id)

    def existente():
        found = db.query(OrcamentoModel).filter_by(idempotency_key=key).first()
        if found is not None and (found.cliente_id != client.id or found.request_hash != fingerprint):
            raise HTTPException(409, "Chave ja utilizada em outra solicitacao.")
        return found

    found = existente()
    if found is not None:
        return {"id": found.id, "status": found.status}
    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent = db.query(func.count(OrcamentoModel.id)).filter(
        OrcamentoModel.cliente_id == client.id,
        OrcamentoModel.detalhes.like("Solicitacao pelo Portal do Cliente%"),
        OrcamentoModel.data_solicitacao >= since,
    ).scalar() or 0
    if recent >= DAILY_REQUESTS:
        raise HTTPException(
            429,
            f"Você já enviou {DAILY_REQUESTS} solicitações nas últimas 24 horas. "
            "O estúdio vai analisar os pedidos; se precisar de algo urgente, fale conosco.",
        )
    service = db.get(ServicoModel, dados.servico_id)
    if service is None:
        raise HTTPException(422, "Servico nao encontrado.")
    try:
        budget = OrcamentoModel(
            cliente_id=client.id, nome_cliente=client.nome, email=client.email or "",
            whatsapp=client.telefone, servico=service.nome, valor_total=None,
            detalhes=f"Solicitacao pelo Portal do Cliente\nTitulo: {dados.titulo}\n\n{dados.descricao}",
            is_test=bool(client.is_test), idempotency_key=key, request_hash=fingerprint,
        )
        db.add(budget)
        db.flush()
        audit_service.record(db, actor=actor, action="production.requested",
                             entity_type="budget", entity_id=budget.id,
                             metadata={"cliente_id": client.id, "servico_id": service.id})
        from services import portal_notificacao_service

        portal_notificacao_service.solicitacao_producao(db, budget)
        db.commit()
        return {"id": budget.id, "status": budget.status}
    except IntegrityError:
        db.rollback()
        found = existente()
        if found is not None:
            return {"id": found.id, "status": found.status}
        raise HTTPException(409, "Nao foi possivel concluir. Tente novamente.") from None
    except Exception:
        db.rollback()
        raise
