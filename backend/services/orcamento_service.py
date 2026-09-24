from sqlalchemy.orm import Session

from crud import crud_orcamento
from schemas.orcamento import OrcamentoCreate
from services import cliente_service


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
    try:
        orcamento = criar_sem_commit(db, dados)
        db.commit()
        db.refresh(orcamento)
        return orcamento
    except Exception:
        db.rollback()
        raise
