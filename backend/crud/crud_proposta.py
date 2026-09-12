"""Persistence helpers. The calling service owns commit/rollback."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import OrcamentoModel, PropostaModel, UsuarioModel


def buscar_por_id(db: Session, proposta_id: int, *, bloquear=False):
    query = select(PropostaModel).where(PropostaModel.id == proposta_id)
    if bloquear:
        query = query.with_for_update().execution_options(populate_existing=True)
    return db.scalar(query)


def buscar_por_orcamento(db: Session, orcamento_id: int):
    return db.scalar(select(PropostaModel).where(PropostaModel.orcamento_id == orcamento_id))


def bloquear_orcamento(db: Session, orcamento_id: int):
    return db.scalar(select(OrcamentoModel).where(OrcamentoModel.id == orcamento_id)
                     .with_for_update().execution_options(populate_existing=True))


def buscar_produtor(db: Session, produtor_id: int):
    return db.get(UsuarioModel, produtor_id)


def criar(db: Session, dados: dict):
    proposta = PropostaModel(**dados)
    db.add(proposta)
    db.flush()
    return proposta


def atualizar(db: Session, proposta: PropostaModel, dados: dict):
    for campo, valor in dados.items():
        setattr(proposta, campo, valor)
    db.flush()
    return proposta
