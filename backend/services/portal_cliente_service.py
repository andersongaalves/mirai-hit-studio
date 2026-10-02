from sqlalchemy.orm import Session

from crud import crud_producao
from models.orcamento import OrcamentoModel
from services import financial_service

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
    }
    if cobranca is None:
        return resposta

    resposta["cobranca"] = {
        "status": financial_service.status_calculado(cobranca).value,
        "valor_total": cobranca.valor_total,
        "valor_pago": financial_service.valor_pago(cobranca),
        "saldo_pendente": financial_service.saldo_pendente(cobranca),
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
    return resposta
