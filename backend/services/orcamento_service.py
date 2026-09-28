import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crud import crud_orcamento
from schemas.orcamento import OrcamentoCreate
from services import cliente_service
from models.orcamento import OrcamentoModel


class OrcamentoReplayConflito(Exception):
    pass


def criar_sem_commit(db: Session, dados: OrcamentoCreate, *, erro_em_conflito=False):
    cliente = cliente_service.resolver_para_orcamento(
        db,
        nome=dados.nome_cliente,
        email=str(dados.email),
        telefone=dados.whatsapp,
        erro_em_conflito=erro_em_conflito,
    )
    payload = dados.model_dump()
    payload["email"] = str(dados.email)
    payload["cliente_id"] = cliente.id if cliente else None
    return crud_orcamento.criar_sem_commit(db, payload)


def criar(db: Session, dados: OrcamentoCreate):
    return criar_com_resultado(db, dados)[0]


def criar_com_resultado(db: Session, dados: OrcamentoCreate, idempotency_key=None):
    fingerprint = hashlib.sha256(json.dumps(
        dados.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()

    def existente():
        if not idempotency_key:
            return None
        found = db.query(OrcamentoModel).filter_by(idempotency_key=idempotency_key).first()
        if found and found.request_hash != fingerprint:
            raise OrcamentoReplayConflito("Chave de solicitacao reutilizada com dados diferentes.")
        return found

    try:
        found = existente()
        if found:
            return found, False
        orcamento = criar_sem_commit(db, dados)
        orcamento.idempotency_key = idempotency_key
        orcamento.request_hash = fingerprint if idempotency_key else None
        db.commit()
        db.refresh(orcamento)
        return orcamento, True
    except IntegrityError:
        # The unique key also serializes concurrent requests across workers.
        db.rollback()
        found = existente()
        if found:
            return found, False
        raise
    except Exception:
        db.rollback()
        raise
