"""Safe client-facing projection and actions for commercial proposals."""
from models.cliente import ClienteModel
from models.enums.proposta import PropostaStatus
from models.orcamento import OrcamentoModel
from models.proposta import PropostaModel
from services import producao_liberacao_service, proposta_service
from services import proposta_comercial_service as commercial
from services import proposta_documento_service as documents
from services.documento_storage import DocumentoIndisponivel
from sqlalchemy import select
from sqlalchemy.orm import Session

VISIBLE_STATUSES = {
    PropostaStatus.ENVIADA.value,
    PropostaStatus.ACEITA.value,
    PropostaStatus.RECUSADA.value,
}


class PropostaClienteError(Exception):
    pass


class PropostaClienteNotFound(PropostaClienteError):
    pass


class PropostaClienteConflict(PropostaClienteError):
    pass


class PropostaClienteUnavailable(PropostaClienteError):
    pass


def _ensure_enabled():
    if not producao_liberacao_service.pipeline_v2_habilitada():
        raise PropostaClienteNotFound("Proposta nao encontrada.")


def _owned_query(cliente_id: int):
    return (
        select(PropostaModel)
        .join(OrcamentoModel, OrcamentoModel.id == PropostaModel.orcamento_id)
        .join(ClienteModel, ClienteModel.id == OrcamentoModel.cliente_id)
        .where(
            OrcamentoModel.cliente_id == cliente_id,
            ClienteModel.ativo.is_(True),
            PropostaModel.status.in_(VISIBLE_STATUSES),
        )
    )


def _owned(db: Session, proposta_id: int, cliente_id: int):
    model = db.scalar(_owned_query(cliente_id).where(PropostaModel.id == proposta_id))
    if model is None:
        raise PropostaClienteNotFound("Proposta nao encontrada.")
    return model


def _commercial_state(model):
    if model.status == PropostaStatus.ENVIADA.value:
        return "aguardando_aceite"
    if model.status == PropostaStatus.RECUSADA.value:
        return "recusada"
    if model.cobranca is None:
        return "aguardando_cobranca"
    if model.cobranca.status == "paga":
        return "pagamento_confirmado"
    return "aguardando_pagamento"


def _project(model):
    try:
        proposal = proposta_service._resposta(model)
    except proposta_service.PropostaConflito:
        raise PropostaClienteConflict(
            "Os dados desta proposta precisam de conciliacao."
        ) from None
    if proposal.totais is None or proposal.enviada_em is None:
        raise PropostaClienteConflict(
            "Os dados desta proposta precisam de conciliacao."
        )
    return {
        "id": proposal.id,
        "numero": proposal.numero,
        "versao": proposal.versao,
        "status": proposal.status,
        "servico": model.orcamento.servico,
        "objeto": proposal.objeto,
        "descricao": proposal.descricao,
        "itens": proposal.itens,
        "totais": proposal.totais,
        "politica_pagamento": proposal.politica_pagamento,
        "condicoes": proposal.condicoes,
        "documento_disponivel": bool(
            model.pdf_path and model.pdf_sha256 and model.gerada_em
        ),
        "situacao_comercial": _commercial_state(model),
        "cobranca_status": model.cobranca.status if model.cobranca else None,
        "enviada_em": proposal.enviada_em,
        "aprovada_em": proposal.aprovada_em,
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
    }


def list_for_client(db: Session, cliente_id: int):
    _ensure_enabled()
    models = db.scalars(
        _owned_query(cliente_id).order_by(PropostaModel.enviada_em.desc())
    ).all()
    return [_project(model) for model in models]


def get_for_client(db: Session, proposta_id: int, cliente_id: int):
    _ensure_enabled()
    return _project(_owned(db, proposta_id, cliente_id))


def document_for_client(db: Session, proposta_id: int, cliente_id: int):
    _ensure_enabled()
    model = _owned(db, proposta_id, cliente_id)
    if not model.pdf_path or not model.pdf_sha256 or not model.gerada_em:
        raise PropostaClienteUnavailable("Documento indisponivel.")
    try:
        data = documents.ler_atual(model)
    except (DocumentoIndisponivel, proposta_service.PropostaConflito):
        raise PropostaClienteUnavailable("Documento indisponivel.") from None
    return data, f"proposta-{model.id}-v{model.versao}.pdf"


def accept(db: Session, proposta_id: int, cliente_id: int, versao: int, actor, request_id):
    _ensure_enabled()
    try:
        commercial.aceitar_cliente(
            db,
            proposta_id,
            cliente_id=cliente_id,
            versao=versao,
            actor=actor,
            request_id=request_id,
        )
    except proposta_service.PropostaNaoEncontrada:
        raise PropostaClienteNotFound("Proposta nao encontrada.") from None
    except (proposta_service.PropostaConflito, proposta_service.PropostaInvalida) as exc:
        raise PropostaClienteConflict(str(exc)) from None
    return get_for_client(db, proposta_id, cliente_id)


def refuse(db: Session, proposta_id: int, cliente_id: int, versao: int, actor, request_id):
    _ensure_enabled()
    try:
        commercial.recusar_cliente(
            db,
            proposta_id,
            cliente_id=cliente_id,
            versao=versao,
            actor=actor,
            request_id=request_id,
        )
    except proposta_service.PropostaNaoEncontrada:
        raise PropostaClienteNotFound("Proposta nao encontrada.") from None
    except (proposta_service.PropostaConflito, proposta_service.PropostaInvalida) as exc:
        raise PropostaClienteConflict(str(exc)) from None
    return get_for_client(db, proposta_id, cliente_id)
