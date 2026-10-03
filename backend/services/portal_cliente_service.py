from sqlalchemy.orm import Session

from core.config import settings
from crud import crud_producao
from models.orcamento import OrcamentoModel
from services import checkout_service, financial_service

PRODUCOES_FINALIZADAS = ("finalizado", "entregue")


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
