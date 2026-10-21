import hashlib

from crud import crud_producao
from fastapi import HTTPException
from models.cliente import ClienteModel
from models.orcamento import OrcamentoModel
from models.servico import ServicoModel
from models.usuario import UsuarioModel
from services import audit_service
from sqlalchemy.exc import IntegrityError


def criar(db, dados, actor):
    key = str(dados.request_id)
    fingerprint = hashlib.sha256(dados.model_dump_json().encode()).hexdigest()

    def existente():
        budget = db.query(OrcamentoModel).filter_by(idempotency_key=key).first()
        if budget is None:
            return None
        if budget.request_hash != fingerprint:
            raise HTTPException(409, "Solicitacao ja utilizada com outros dados.")
        production = crud_producao.buscar_por_orcamento(db, budget.id)
        if production is None:
            raise HTTPException(409, "Solicitacao ainda nao concluida.")
        return crud_producao.buscar(db, production.id)

    previous = existente()
    if previous is not None:
        return previous
    client = db.get(ClienteModel, dados.cliente_id)
    if client is None or not client.ativo:
        raise HTTPException(422, "Cliente ativo nao encontrado.")
    service = db.get(ServicoModel, dados.servico_id)
    if service is None:
        raise HTTPException(422, "Servico nao encontrado.")
    if dados.produtor_id is not None:
        producer = db.get(UsuarioModel, dados.produtor_id)
        if producer is None or not producer.ativo or producer.role != "produtor":
            raise HTTPException(422, "Produtor ativo nao encontrado.")
    try:
        # Client ownership in all portals is resolved through the budget relation.
        budget = OrcamentoModel(
            nome_cliente=client.nome, email=client.email or "", whatsapp=client.telefone,
            cliente_id=client.id, servico=service.nome, is_test=client.is_test,
            idempotency_key=key, request_hash=fingerprint,
            detalhes="Producao criada diretamente pelo administrador.",
        )
        db.add(budget)
        db.flush()
        production = crud_producao.criar_sem_commit(db, {
            "titulo": dados.titulo, "cliente": client.nome, "servico": service.nome,
            "orcamento_id": budget.id, "produtor_id": dados.produtor_id,
            "prazo_entrega": dados.prazo_entrega, "observacoes": dados.observacoes,
        })
        audit_service.record(db, actor=actor, action="production.created_directly",
                             entity_type="production", entity_id=production.id,
                             metadata={"cliente_id": client.id, "orcamento_id": budget.id})
        db.commit()
        return crud_producao.buscar(db, production.id)
    except IntegrityError:
        db.rollback()
        previous = existente()
        if previous is not None:
            return previous
        raise HTTPException(409, "Nao foi possivel criar a producao. Atualize a listagem.") from None
    except Exception:
        db.rollback()
        raise
