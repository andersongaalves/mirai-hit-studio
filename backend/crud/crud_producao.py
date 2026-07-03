from sqlalchemy.orm import Session

from models.producao import ProducaoModel


def criar(
    db: Session,
    dados: dict
):

    producao = ProducaoModel(
        **dados
    )


    db.add(
        producao
    )

    db.commit()

    db.refresh(
        producao
    )


    return producao



def listar(
    db: Session
):

    return (

        db.query(ProducaoModel)

        .order_by(
            ProducaoModel.id.desc()
        )

        .all()

    )

def atualizar_status(
    db: Session,
    producao_id: int,
    status: str
):

    producao = (

        db.query(ProducaoModel)

        .filter(
            ProducaoModel.id == producao_id
        )

        .first()

    )


    if not producao:

        return None


    producao.status = status


    db.commit()

    db.refresh(
        producao
    )


    return producao

def criar_por_orcamento(
    db: Session,
    orcamento
):

    existente = (

        db.query(ProducaoModel)

        .filter(
            ProducaoModel.orcamento_id == orcamento.id
        )

        .first()

    )


    if existente:

        return existente


    producao = ProducaoModel(

        titulo=f"{orcamento.servico} - {orcamento.nome_cliente}",

        cliente=orcamento.nome_cliente,

        servico=orcamento.servico,

        produtor_id=orcamento.produtor_id,

        orcamento_id=orcamento.id,

        observacoes=orcamento.observacoes or ""

    )


    db.add(
        producao
    )


    db.commit()


    db.refresh(
        producao
    )


    return producao