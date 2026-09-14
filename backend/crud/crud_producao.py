from sqlalchemy.orm import Session

from models.producao import ProducaoModel
from models.orcamento import OrcamentoModel
from models.proposta import PropostaModel
from models.usuario import UsuarioModel


def _resposta(producao, produtor_nome=None, cliente_email=None, proposta=None):
    return {
        "id": producao.id,
        "titulo": producao.titulo,
        "cliente": producao.cliente,
        "servico": producao.servico,
        "status": producao.status,
        "produtor_id": producao.produtor_id,
        "produtor_nome": produtor_nome,
        "orcamento_id": producao.orcamento_id,
        "proposta_id": proposta.id if proposta else None,
        "proposta_numero": proposta.numero if proposta else None,
        "cliente_email": cliente_email,
        "observacoes": producao.observacoes or "",
        "etapas": producao.etapas or "[]",
        "prazo_entrega": producao.prazo_entrega,
        "created_at": producao.created_at,
        "updated_at": producao.updated_at,
    }


def _consulta_detalhes(db: Session):
    return (
        db.query(
            ProducaoModel,
            UsuarioModel.username,
            OrcamentoModel.email,
            PropostaModel,
        )
        .outerjoin(UsuarioModel, ProducaoModel.produtor_id == UsuarioModel.id)
        .outerjoin(OrcamentoModel, ProducaoModel.orcamento_id == OrcamentoModel.id)
        .outerjoin(
            PropostaModel,
            PropostaModel.orcamento_id == ProducaoModel.orcamento_id,
        )
    )


def buscar_por_orcamento(db, orcamento_id):
    return db.query(ProducaoModel).filter(ProducaoModel.orcamento_id == orcamento_id).first()


def criar_sem_commit(db, dados):
    producao = ProducaoModel(**dados)
    db.add(producao)
    db.flush()
    return producao


def criar(db: Session, dados: dict):

    producao = ProducaoModel(**dados)

    db.add(producao)

    db.commit()

    db.refresh(producao)

    return producao


def listar(db: Session):
    rows = _consulta_detalhes(db).order_by(ProducaoModel.id.desc()).all()
    return [
        _resposta(producao, produtor, email, proposta)
        for producao, produtor, email, proposta in rows
    ]


def buscar(db: Session, producao_id: int):
    row = _consulta_detalhes(db).filter(ProducaoModel.id == producao_id).first()
    if not row:
        return None
    producao, produtor, email, proposta = row
    return _resposta(producao, produtor, email, proposta)


def atualizar_status(db: Session, producao_id: int, status: str):

    producao = db.query(ProducaoModel).filter(ProducaoModel.id == producao_id).first()

    if not producao:

        return None

    producao.status = status

    db.commit()

    db.refresh(producao)

    return producao


def criar_por_orcamento(db: Session, orcamento):

    existente = (
        db.query(ProducaoModel)
        .filter(ProducaoModel.orcamento_id == orcamento.id)
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
        observacoes=orcamento.observacoes or "",
    )

    db.add(producao)

    db.commit()

    db.refresh(producao)

    return producao


def atualizar_etapas(db: Session, producao_id: int, etapas: str):

    producao = db.query(ProducaoModel).filter(ProducaoModel.id == producao_id).first()

    if not producao:

        return None

    producao.etapas = etapas

    db.commit()

    db.refresh(producao)

    return producao


def atualizar_prazo(db, producao_id, prazo):

    producao = db.query(ProducaoModel).filter(ProducaoModel.id == producao_id).first()

    if not producao:

        return None

    producao.prazo_entrega = prazo

    db.commit()

    db.refresh(producao)

    return producao


def atualizar_status_sem_commit(db: Session, producao_id: int, status: str):
    producao = db.get(ProducaoModel, producao_id)
    if not producao:
        return None
    producao.status = status
    db.flush()
    return producao


def atualizar_observacoes(db: Session, producao_id: int, observacoes: str):
    producao = db.get(ProducaoModel, producao_id)
    if not producao:
        return None
    producao.observacoes = observacoes
    db.commit()
    db.refresh(producao)
    return producao
