import re

from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session, selectinload

from models.cliente import ClienteModel
from models.orcamento import OrcamentoModel


def buscar_por_id(db: Session, cliente_id: int, *, com_orcamentos: bool = False):
    query = db.query(ClienteModel).filter(ClienteModel.id == cliente_id)
    if com_orcamentos:
        query = query.options(
            selectinload(ClienteModel.orcamentos).selectinload(OrcamentoModel.proposta),
        )
    return query.first()


def buscar_por_email(db: Session, email: str | None):
    if not email:
        return None
    return db.query(ClienteModel).filter(ClienteModel.email == email).first()


def buscar_por_telefone(db: Session, telefone: str | None):
    if not telefone:
        return None
    return db.query(ClienteModel).filter(ClienteModel.telefone == telefone).first()


def listar(db: Session, busca: str = "", ativo: bool | None = None):
    ultima = func.max(func.coalesce(OrcamentoModel.updated_at, OrcamentoModel.data_solicitacao))
    query = (
        db.query(
            ClienteModel,
            func.count(OrcamentoModel.id).label("total_orcamentos"),
            ultima.label("ultima_interacao"),
        )
        .outerjoin(OrcamentoModel, OrcamentoModel.cliente_id == ClienteModel.id)
    )
    if busca:
        termo = f"%{busca.lower()}%"
        telefone = re.sub(r"\D", "", busca)
        query = query.filter(or_(
            func.lower(ClienteModel.nome).like(termo),
            func.lower(func.coalesce(ClienteModel.email, "")).like(termo),
            func.coalesce(ClienteModel.telefone, "").like(f"%{telefone}%")
            if telefone else false(),
        ))
    if ativo is not None:
        query = query.filter(ClienteModel.ativo.is_(ativo))
    return (
        query.group_by(
            ClienteModel.id,
            ClienteModel.nome,
            ClienteModel.email,
            ClienteModel.telefone,
            ClienteModel.observacoes,
            ClienteModel.ativo,
            ClienteModel.created_at,
            ClienteModel.updated_at,
        )
        .order_by(ultima.desc(), ClienteModel.id.desc())
        .all()
    )


def criar_sem_commit(db: Session, dados: dict):
    cliente = ClienteModel(**dados)
    db.add(cliente)
    db.flush()
    return cliente


def atualizar_sem_commit(db: Session, cliente: ClienteModel, dados: dict):
    for campo, valor in dados.items():
        setattr(cliente, campo, valor)
    db.flush()
    return cliente
