"""Draft creation/editing only; no document, email or approval side effects."""
from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crud import crud_proposta as crud
from models.enums.proposta import PropostaStatus
from schemas.proposta import (
    PropostaItem, PropostaPagamento, PropostaResponse, PropostaSnapshot,
    PropostaTotais, PropostaUpdate,
)

CONDICOES_PADRAO = (
    "Esta proposta contempla os servi\u00e7os descritos neste documento.\n\n"
    "Altera\u00e7\u00f5es de escopo poder\u00e3o gerar revis\u00e3o de valores e prazos.\n\n"
    "O in\u00edcio da produ\u00e7\u00e3o ocorre ap\u00f3s confirma\u00e7\u00e3o do pagamento de entrada "
    "e envio dos materiais necess\u00e1rios."
)
COLUNAS_JSON = {"itens": "itens_json", "pagamentos": "pagamentos_json"}


class PropostaNaoEncontrada(Exception):
    pass


class PropostaInvalida(Exception):
    pass


class PropostaConflito(Exception):
    pass


def calcular_totais(itens: list[PropostaItem]) -> PropostaTotais:
    # Currency is rounded per line; the effective discount cannot make it negative.
    try:
        with localcontext() as context:
            context.prec = 64
            subtotal = desconto = Decimal("0.00")
            for item in itens:
                bruto = (item.quantidade * item.valor_unitario).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                abatimento = min(bruto, item.desconto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                subtotal += bruto
                desconto += abatimento
            return PropostaTotais(subtotal=subtotal, desconto=desconto, total=subtotal - desconto)
    except (DecimalException, ValidationError):
        raise PropostaInvalida("Valores fora da capacidade de calculo monetario.") from None


def _validar_produtor(db, produtor_id):
    if produtor_id is not None and crud.buscar_produtor(db, produtor_id) is None:
        raise PropostaInvalida("Produtor nao encontrado.")


def _resposta(proposta):
    try:
        return PropostaResponse.from_orm_model(proposta)
    except ValidationError:
        raise PropostaConflito("Dados armazenados da proposta precisam de revisao.") from None


def buscar(db: Session, proposta_id: int):
    proposta = crud.buscar_por_id(db, proposta_id)
    if proposta is None:
        raise PropostaNaoEncontrada("Proposta nao encontrada.")
    return _resposta(proposta)


def buscar_por_orcamento(db: Session, orcamento_id: int):
    proposta = crud.buscar_por_orcamento(db, orcamento_id)
    if proposta is None:
        raise PropostaNaoEncontrada("Proposta nao encontrada para este orcamento.")
    return _resposta(proposta)


def criar_por_orcamento(db: Session, orcamento_id: int):
    try:
        orcamento = crud.bloquear_orcamento(db, orcamento_id)
        if orcamento is None:
            raise PropostaNaoEncontrada("Orcamento nao encontrado.")
        existente = crud.buscar_por_orcamento(db, orcamento_id)
        if existente is not None:
            resposta = _resposta(existente)
            db.commit()
            return resposta
        _validar_produtor(db, orcamento.produtor_id)
        snapshot = PropostaSnapshot.model_validate({
            "cliente": {"nome": orcamento.nome_cliente, "email": orcamento.email, "whatsapp": orcamento.whatsapp},
            "orcamento": {"id": orcamento.id, "servico": orcamento.servico,
                          "detalhes": orcamento.detalhes, "valor_total": orcamento.valor_total,
                          "link_guia": orcamento.link_guia},
        })
        item = PropostaItem(descricao=orcamento.servico, quantidade=1,
                           valor_unitario=snapshot.orcamento.valor_total or Decimal("0"))
        pagamentos = [PropostaPagamento(tipo=tipo, titulo=titulo).model_dump(mode="json")
                      for tipo, titulo in [("integral", "Pagamento completo"),
                                           ("parcial_1", "Pagamento parcial 1"),
                                           ("parcial_2", "Pagamento parcial 2")]]
        proposta = crud.criar(db, {
            # The budget PK is allocated by the DB and the relationship is 1:1.
            "orcamento_id": orcamento.id, "numero": f"MHS-{orcamento.id:06d}",
            "versao": 1, "status": PropostaStatus.RASCUNHO.value,
            "produtor_id": orcamento.produtor_id, "cliente_snapshot": snapshot.model_dump(mode="json"),
            "objeto": orcamento.servico, "descricao": orcamento.detalhes or "",
            "itens_json": [item.model_dump(mode="json")], "pagamentos_json": pagamentos,
            "condicoes": CONDICOES_PADRAO, "totais_json": calcular_totais([item]).model_dump(mode="json"),
        })
        resposta = _resposta(proposta)
        db.commit()
        return resposta
    except IntegrityError:
        db.rollback()
        # UNIQUE remains the final guard for writers not using our row lock.
        existente = crud.buscar_por_orcamento(db, orcamento_id)
        if existente is not None:
            return _resposta(existente)
        raise PropostaConflito("Conflito ao criar proposta; nenhuma alteracao confirmada.") from None
    except ValidationError:
        db.rollback()
        raise PropostaInvalida("Dados do orcamento invalidos para criar a proposta.") from None
    except Exception:
        db.rollback()
        raise


def atualizar(db: Session, proposta_id: int, dados: PropostaUpdate):
    try:
        proposta = crud.buscar_por_id(db, proposta_id, bloquear=True)
        if proposta is None:
            raise PropostaNaoEncontrada("Proposta nao encontrada.")
        if proposta.status != PropostaStatus.RASCUNHO.value:
            raise PropostaConflito("Somente propostas em rascunho podem ser editadas.")
        if "produtor_id" in dados.model_fields_set:
            _validar_produtor(db, dados.produtor_id)
        payload = dados.model_dump(mode="json", exclude_unset=True)
        alteracoes = {COLUNAS_JSON.get(campo, campo): valor for campo, valor in payload.items()}
        itens = [PropostaItem.model_validate(item) for item in alteracoes.get("itens_json", proposta.itens_json)]
        alteracoes["totais_json"] = calcular_totais(itens).model_dump(mode="json")
        alteracoes = {campo: valor for campo, valor in alteracoes.items() if getattr(proposta, campo) != valor}
        if alteracoes:
            alteracoes.update(versao=proposta.versao + 1, pdf_path=None, gerada_em=None)
            crud.atualizar(db, proposta, alteracoes)
        resposta = _resposta(proposta)
        db.commit()
        return resposta
    except IntegrityError:
        db.rollback()
        raise PropostaConflito("Conflito ao salvar proposta; nenhuma alteracao confirmada.") from None
    except ValidationError:
        db.rollback()
        raise PropostaInvalida("Itens da proposta invalidos.") from None
    except Exception:
        db.rollback()
        raise
