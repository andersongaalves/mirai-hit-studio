from core.config import settings
from crud import crud_producao
from models.orcamento import OrcamentoModel
from services import checkout_service, financial_service, politica_service
from sqlalchemy.orm import Session

PRODUCOES_FINALIZADAS = ("finalizado", "entregue")
TIPO_ENTREGA_FINAL = "entrega"
MENSAGEM_ENTREGA_BLOQUEADA = (
    "A entrega final está pronta e será liberada após a quitação do saldo. "
    "Conclua o pagamento no Portal do Cliente para baixar os arquivos."
)


class ProducaoClienteNaoEncontrada(Exception):
    pass


def listar_producoes(db: Session, cliente_id: int):
    return crud_producao.listar_por_cliente(db, cliente_id)


def listar_historico(db: Session, cliente_id: int):
    return crud_producao.listar_por_cliente(
        db,
        cliente_id,
        status=PRODUCOES_FINALIZADAS,
    )


def buscar_producao(db: Session, producao_id: int, cliente_id: int):
    producao = crud_producao.buscar_por_cliente(db, producao_id, cliente_id)
    if producao is None:
        raise ProducaoClienteNaoEncontrada("Producao nao encontrada.")
    return producao


def buscar_financeiro(db: Session, producao_id: int, cliente_id: int):
    producao = buscar_producao(db, producao_id, cliente_id)
    orcamento = db.get(OrcamentoModel, producao.orcamento_id)
    proposta = orcamento.proposta if orcamento else None
    cobranca = proposta.cobranca if proposta else None

    resposta = {
        "producao_id": producao.id,
        "proposta_numero": proposta.numero if proposta else None,
        "proposta_status": proposta.status if proposta else None,
        "cobranca": None,
        "checkout_url": None,
    }
    if cobranca is None:
        return resposta
    if cobranca.cliente_id is not None and cobranca.cliente_id != cliente_id:
        raise financial_service.FinanceiroConflito("Cobranca vinculada a outro cliente.")

    status = financial_service.status_calculado(cobranca)
    saldo = financial_service.saldo_pendente(cobranca)
    resposta["cobranca"] = {
        "status": status.value,
        "valor_total": cobranca.valor_total,
        "valor_pago": financial_service.valor_pago(cobranca),
        "saldo_pendente": saldo,
        "moeda": cobranca.moeda,
        "vencimento": cobranca.vencimento,
        "pagamentos": [
            {
                "tipo": pagamento.tipo,
                "valor": pagamento.valor,
                "status": pagamento.status,
                "metodo": pagamento.metodo,
                "aprovado_em": pagamento.aprovado_em,
                "created_at": pagamento.created_at,
            }
            for pagamento in cobranca.pagamentos
        ],
    }
    if politica_service.vigentes(db, producao.id)["financeiro_cliente"] == "resumido":
        # 5.10: summary view keeps status, balance, due date and the payment link only.
        resposta["cobranca"].update(valor_total=None, valor_pago=None, pagamentos=[])
        resposta["resumido"] = True
    if saldo > 0 and status.value not in {"paga", "cancelada"}:
        try:
            resposta["checkout_url"] = checkout_service.link_por_proposta(
                db,
                proposta.id,
                getattr(settings, "PUBLIC_FRONTEND_URL", "http://localhost:4173"),
            )
        except (checkout_service.CheckoutNaoEncontrado, checkout_service.CheckoutIndisponivel):
            resposta["checkout_url"] = None
    return resposta


def entrega_bloqueada(db: Session, producao) -> bool:
    """Re-evaluate settlement on every read; only a reasoned production exception bypasses it."""
    from services import credito_alocacao_service

    try:
        credit_block = credito_alocacao_service.entrega_bloqueada(db, producao)
    except (credito_alocacao_service.AlocacaoConflito, financial_service.FinanceiroConflito):
        return True
    if credit_block is not None:
        return credit_block
    politicas = politica_service.detalhar(db, producao.id)
    if (
        politicas["vigentes"]["entrega_final"] == "liberada"
        and politicas["origens"]["entrega_final"] == "excecao"
        and len((politicas["motivo"] or "").strip()) >= 5
    ):
        return False
    orcamento = db.get(OrcamentoModel, producao.orcamento_id)
    if orcamento is None:
        return True
    proposta = orcamento.proposta if orcamento else None
    cobranca = proposta.cobranca if proposta else None
    if cobranca is None:
        # Historical unbilled productions keep their existing access rules.
        return False
    if (
        proposta.orcamento_id != orcamento.id
        or cobranca.proposta_id != proposta.id
        or cobranca.cliente_id not in {None, orcamento.cliente_id}
        or cobranca.moeda != "BRL"
        or cobranca.status == "cancelada"
        or any(p.reconciliation_status for p in cobranca.pagamentos)
    ):
        return True
    try:
        status = financial_service.status_calculado(cobranca)
        saldo = financial_service.saldo_pendente(cobranca)
    except (financial_service.FinanceiroConflito, financial_service.FinanceiroInvalido):
        return True
    return saldo != 0 or status.value != "paga"
