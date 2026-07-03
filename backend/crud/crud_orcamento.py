from sqlalchemy.orm import Session
from models.orcamento import OrcamentoModel
from crud import crud_producao

def criar(db, orcamento):

    novo = OrcamentoModel(
        **orcamento.model_dump()
    )

    db.add(novo)

    db.commit()

    db.refresh(novo)

    return novo


def listar(db):

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
    status: str
) -> OrcamentoModel | None:

    orcamento = db.query(
        OrcamentoModel
    ).filter(
        OrcamentoModel.id == orcamento_id
    ).first()

    if not orcamento:
        return None

    orcamento.status = status


    if status == "aprovado":

        crud_producao.criar_por_orcamento(

            db,

            orcamento

        )


    db.commit()

    db.refresh(
        orcamento
    )


    return orcamento

def atualizar_produtor(
    db,
    orcamento_id: int,
    produtor_id: int | None
):

    orcamento = (
        db.query(OrcamentoModel)
        .filter(
            OrcamentoModel.id == orcamento_id
        )
        .first()
    )


    if not orcamento:

        return None


    orcamento.produtor_id = produtor_id


    db.commit()

    db.refresh(
        orcamento
    )


    return orcamento

def atualizar_observacoes(
    db,
    orcamento_id: int,
    observacoes: str
):

    orcamento = (
        db.query(OrcamentoModel)
        .filter(
            OrcamentoModel.id == orcamento_id
        )
        .first()
    )


    if not orcamento:

        return None


    orcamento.observacoes = observacoes


    db.commit()

    db.refresh(
        orcamento
    )


    return orcamento