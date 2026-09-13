from sqlalchemy.orm import Session

from crud import crud_orcamento
from schemas.orcamento import OrcamentoCreate
from services import cliente_service


def criar(db: Session, dados: OrcamentoCreate):
    try:
        cliente = cliente_service.resolver_para_orcamento(
            db,
            nome=dados.nome_cliente,
            email=str(dados.email),
            telefone=dados.whatsapp,
        )
        payload = dados.model_dump()
        payload["email"] = str(dados.email)
        payload["cliente_id"] = cliente.id if cliente else None
        orcamento = crud_orcamento.criar_sem_commit(db, payload)
        db.commit()
        db.refresh(orcamento)
        return orcamento
    except Exception:
        db.rollback()
        raise
