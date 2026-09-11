from datetime import datetime
from sqlalchemy.orm import Session

from models.orcamento import OrcamentoModel
from crud import crud_producao
from core.enums import OrcamentoStatus


def buscar_por_id(
    db: Session,
    orcamento_id: int,
):
    return (
        db.query(OrcamentoModel)
        .filter(
            OrcamentoModel.id == orcamento_id
        )
        .first()
    )


def criar(db: Session, orcamento):

    novo = OrcamentoModel(
        **orcamento.model_dump()
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return novo


def listar(db: Session):

    return (
        db.query(OrcamentoModel)
        .order_by(
            OrcamentoModel.id.desc()
        )
        .all()
    )


def atualizar_status(
    db: Session,
    orcamento_id: int,
    status: OrcamentoStatus,
):

    orcamento = buscar_por_id(
        db,
        orcamento_id,
    )

    if not orcamento:
        return None


    orcamento.status = status.value


    if status == OrcamentoStatus.APROVADO:

        crud_producao.criar_por_orcamento(
            db,
            orcamento,
        )


    db.commit()
    db.refresh(orcamento)

    return orcamento


def marcar_proposta_enviada(
    db: Session,
    orcamento_id: int,
    codigo: str,
    arquivo: str,
):

    orcamento = buscar_por_id(
        db,
        orcamento_id,
    )


    if not orcamento:
        return None


    orcamento.status = (
        OrcamentoStatus.PROPOSTA_ENVIADA.value
    )

    orcamento.proposta_codigo = codigo

    orcamento.proposta_pdf = arquivo

    orcamento.proposta_enviada = True

    orcamento.proposta_enviada_em = (
        datetime.now()
    )


    db.commit()
    db.refresh(orcamento)

    return orcamento


def atualizar_produtor(
    db: Session,
    orcamento_id: int,
    produtor_id: int | None,
):

    orcamento = buscar_por_id(
        db,
        orcamento_id,
    )


    if not orcamento:
        return None


    orcamento.produtor_id = produtor_id


    db.commit()
    db.refresh(orcamento)

    return orcamento


def atualizar_observacoes(
    db: Session,
    orcamento_id: int,
    observacoes: str,
):

    orcamento = buscar_por_id(
        db,
        orcamento_id,
    )


    if not orcamento:
        return None


    orcamento.observacoes = observacoes


    db.commit()
    db.refresh(orcamento)

    return orcamento