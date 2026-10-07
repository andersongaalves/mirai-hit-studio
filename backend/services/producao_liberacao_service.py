"""Authoritative, idempotent release of production after approved payment."""

from crud import crud_producao, crud_proposta
from models.enums.financeiro import CobrancaStatus
from models.enums.proposta import PoliticaPagamento, PropostaStatus
from models.financeiro import CobrancaModel
from services import audit_service, financial_service, proposta_service
from services.pdf_service import moeda
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload


def dados_producao(proposta):
    cliente = proposta.cliente_snapshot.cliente.nome
    servico = proposta.cliente_snapshot.orcamento.servico
    titulo = proposta.objeto or f"Proposta {proposta.numero}"
    if len(cliente) > 120 or len(servico) > 100:
        raise proposta_service.PropostaInvalida(
            "Nome/servico do snapshot excede o limite da producao."
        )
    totals = proposta_service.calcular_totais(proposta.itens)
    itens = "\n".join(
        f"- {item.descricao}: {item.quantidade} x {moeda(item.valor_unitario)}; "
        f"desconto {moeda(item.desconto)}"
        for item in proposta.itens
    )
    notes = (
        f"Proposta {proposta.numero} | versao {proposta.versao}\n"
        f"{proposta.objeto}\n{proposta.descricao}\n{itens}\n"
        f"Total: {moeda(totals.total)}\n{proposta.condicoes}"
    )
    return {
        "titulo": titulo[:150],
        "cliente": cliente,
        "servico": servico,
        "produtor_id": proposta.produtor_id,
        "orcamento_id": proposta.orcamento_id,
        "observacoes": notes,
        "status": "aguardando_inicio",
        "etapas": "[]",
    }


def condicao_inicio_satisfeita(proposta, cobranca: CobrancaModel) -> bool:
    if proposta.status != PropostaStatus.ACEITA.value:
        return False
    if cobranca.status == CobrancaStatus.CANCELADA.value:
        return False
    if cobranca.proposta_id != proposta.id:
        raise financial_service.FinanceiroConflito(
            "Cobranca nao pertence a proposta informada."
        )
    total = financial_service.normalizar_valor(cobranca.valor_total)
    pago = financial_service.valor_pago(cobranca)
    try:
        politica = PoliticaPagamento(proposta.politica_pagamento)
    except ValueError:
        raise financial_service.FinanceiroConflito(
            "Politica de pagamento invalida requer conciliacao."
        ) from None
    minimo = (
        total
        if politica == PoliticaPagamento.INTEGRAL
        else financial_service.dividir_50_50(total)[0]
    )
    return pago >= minimo


def avaliar_liberacao_producao(
    db: Session,
    cobranca_id: int,
    *,
    actor=None,
    request_id: str | None = None,
):
    db.flush()
    cobranca = db.scalar(
        select(CobrancaModel)
        .where(CobrancaModel.id == cobranca_id)
        .options(selectinload(CobrancaModel.pagamentos))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if cobranca is None or cobranca.proposta is None:
        raise financial_service.FinanceiroConflito(
            "Cobranca sem proposta requer conciliacao."
        )
    return avaliar_cobranca_bloqueada(
        db,
        cobranca,
        actor=actor,
        request_id=request_id,
    )


def avaliar_cobranca_bloqueada(
    db: Session,
    cobranca: CobrancaModel,
    *,
    actor=None,
    request_id: str | None = None,
):
    if cobranca.proposta is None:
        raise financial_service.FinanceiroConflito(
            "Cobranca sem proposta requer conciliacao."
        )
    proposta = cobranca.proposta
    existente = crud_producao.buscar_por_orcamento(db, proposta.orcamento_id)
    if existente is not None:
        return existente
    if not condicao_inicio_satisfeita(proposta, cobranca):
        return None

    budget = crud_proposta.bloquear_orcamento(db, proposta.orcamento_id)
    if budget is None:
        raise proposta_service.PropostaConflito(
            "Orcamento da proposta nao encontrado."
        )
    existente = crud_producao.buscar_por_orcamento(db, proposta.orcamento_id)
    if existente is not None:
        return existente
    producao = crud_producao.criar_sem_commit(
        db,
        dados_producao(proposta_service._resposta(proposta)),
    )
    audit_service.record(
        db,
        actor=actor,
        action="production.released_by_payment",
        entity_type="production",
        entity_id=producao.id,
        metadata={"proposal_id": proposta.id, "result": "created"},
        request_id=request_id,
    )
    return producao
