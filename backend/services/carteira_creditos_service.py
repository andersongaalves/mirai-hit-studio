"""Service-credit acquisition from settled contracts; no money is created or transferred."""

import hashlib
import json
from decimal import Decimal

from models import (
    CreditoContratoItemModel,
    CreditoLancamentoModel,
    CreditoLoteModel,
    OrcamentoModel,
    ServicoModel,
)
from models.enums.proposta import PropostaStatus
from pydantic import ValidationError
from schemas.credito_servico import ContratoCreditos, CreditoContratado, CreditoServico
from services import audit_service, financial_service, proposta_service
from sqlalchemy import select


def finalidade_creditos(proposta):
    return getattr(proposta, "finalidade", "producao") == "creditos"


def construir_contrato(db, proposta, economico):
    if not finalidade_creditos(proposta):
        return None
    if proposta.politica_pagamento != "integral":
        raise proposta_service.PropostaInvalida("Creditos exigem pagamento integral antes da concessao.")
    budget = db.get(OrcamentoModel, proposta.orcamento_id)
    if budget is None or budget.cliente_id is None:
        raise proposta_service.PropostaInvalida("Vincule o orcamento a um cliente antes de vender creditos.")
    itens = []
    try:
        for linha in economico["itens"]:
            partes = linha.get("componentes") or [{
                "indice": 0, "servico_id": linha.get("servico_id"),
                "servico_nome": linha.get("servico_nome"), "valor_alocado": linha["valor_contratado"],
            }]
            if not linha["catalogo_disponivel"]:
                raise ValueError()
            for parte in partes:
                servico = db.get(ServicoModel, parte["servico_id"]) if parte["servico_id"] else None
                if servico is None or not servico.credito_servico:
                    raise ValueError()
                config = CreditoServico.model_validate(servico.credito_servico)
                quantidade = config.quantidade * Decimal(linha["quantidade"])
                valor = Decimal(parte["valor_alocado"]) * 100
                if valor != valor.to_integral_value():
                    raise ValueError()
                itens.append(CreditoContratado(
                    linha=linha["indice"], componente=parte["indice"], servico_id=servico.id,
                    servico_nome=parte["servico_nome"], unidade=config.unidade,
                    quantidade=quantidade, valor_centavos=int(valor),
                ))
        contrato = ContratoCreditos(itens=itens)
        total = sum(item.valor_centavos for item in contrato.itens)
        if total <= 0 or total != Decimal(economico["total"]) * 100:
            raise ValueError()
        return contrato.model_dump(mode="json")
    except (ValidationError, ValueError, TypeError, KeyError):
        raise proposta_service.PropostaInvalida(
            "Defina unidades de credito validas para todos os servicos e um total contratado positivo."
        ) from None


def _contrato(proposta):
    try:
        contrato = ContratoCreditos.model_validate(proposta.contrato_creditos)
        economico = proposta.snapshot_economico
        total = sum(i.valor_centavos for i in contrato.itens)
        if economico is None or total <= 0 or total != Decimal(economico["total"]) * 100:
            raise ValueError()
        pares = [(i.linha, i.componente) for i in contrato.itens]
        if len(set(pares)) != len(pares):
            raise ValueError()
        origens = {}
        for linha in economico["itens"]:
            partes = linha.get("componentes") or [{"indice": 0, "servico_id": linha.get("servico_id"),
                "servico_nome": linha.get("servico_nome"), "valor_alocado": linha["valor_contratado"]}]
            for parte in partes:
                valor = Decimal(parte["valor_alocado"]) * 100
                if valor != valor.to_integral_value():
                    raise ValueError()
                origens[(linha["indice"], parte["indice"])] = (parte["servico_id"], parte["servico_nome"], int(valor))
        if origens != {(i.linha, i.componente): (i.servico_id, i.servico_nome, i.valor_centavos) for i in contrato.itens}:
            raise ValueError()
        if proposta.politica_pagamento != "integral":
            raise ValueError()
        return contrato
    except (ValidationError, ValueError, TypeError, KeyError):
        raise financial_service.FinanceiroConflito("Contrato de creditos requer conciliacao.") from None


def _fingerprint(proposta):
    payload = {"proposta_id": proposta.id, "orcamento_id": proposta.orcamento_id,
               "finalidade": proposta.finalidade, "politica_pagamento": proposta.politica_pagamento,
               "direitos": proposta.contrato_creditos, "economico": proposta.snapshot_economico}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def financiamento_valido(cobranca):
    try:
        return (
            cobranca.moeda == "BRL" and cobranca.status != "cancelada"
            and cobranca.proposta.status == PropostaStatus.ACEITA.value
            and cobranca.proposta.politica_pagamento == "integral"
            and not any(p.reconciliation_status for p in cobranca.pagamentos)
            and financial_service.valor_pago(cobranca) == financial_service.normalizar_valor(cobranca.valor_total)
        )
    except (financial_service.FinanceiroInvalido, financial_service.FinanceiroConflito):
        return False


def _direitos_registrados(db, proposta, contrato, cliente_id):
    direitos = db.scalars(select(CreditoContratoItemModel).where(
        CreditoContratoItemModel.proposta_id == proposta.id,
        CreditoContratoItemModel.proposta_versao == proposta.versao,
    )).all()
    expected = {(i.linha, i.componente): i for i in contrato.itens}
    if {(i.linha, i.componente) for i in direitos} != set(expected):
        raise financial_service.FinanceiroConflito("Direitos contratuais incompletos; requer conciliacao.")
    digest = _fingerprint(proposta)
    for direito in direitos:
        item = expected[(direito.linha, direito.componente)]
        if (direito.cliente_id != cliente_id or direito.contrato_sha256 != digest
                or any(getattr(direito, key) != value for key, value in item.model_dump().items())):
            raise financial_service.FinanceiroConflito("Identidade dos direitos contratados requer conciliacao.")
    return {(i.linha, i.componente): i for i in direitos}


def registrar_contrato(db, proposta):
    contrato = _contrato(proposta)
    budget = db.get(OrcamentoModel, proposta.orcamento_id)
    if budget is None or budget.cliente_id is None:
        raise proposta_service.PropostaInvalida("Contrato de creditos sem cliente.")
    digest = _fingerprint(proposta)
    for item in contrato.itens:
        db.add(CreditoContratoItemModel(proposta_id=proposta.id, proposta_versao=proposta.versao,
            cliente_id=budget.cliente_id, contrato_sha256=digest, **item.model_dump()))
    db.flush()
    audit_service.record(db, actor=None, action="credits.contract_frozen", entity_type="proposal", entity_id=proposta.id,
                         metadata={"version": proposta.versao, "items": len(contrato.itens)})


def creditar_cobranca_bloqueada(db, cobranca, *, actor=None, request_id=None):
    """Caller holds the charge lock used by payment confirmation, refunds and reconciliation."""
    proposta = cobranca.proposta
    from models import ProducaoModel

    if db.scalar(select(ProducaoModel.id).where(ProducaoModel.orcamento_id == proposta.orcamento_id)) is not None:
        raise financial_service.FinanceiroConflito("Compra de creditos vinculada a producao requer conciliacao.")
    contrato = _contrato(proposta)
    budget = db.get(OrcamentoModel, proposta.orcamento_id)
    if budget is None or not cobranca.cliente_id or budget.cliente_id != cobranca.cliente_id:
        raise financial_service.FinanceiroConflito("Titularidade dos creditos requer conciliacao.")
    direitos = _direitos_registrados(db, proposta, contrato, cobranca.cliente_id)
    if sum(i.valor_centavos for i in contrato.itens) != financial_service.normalizar_valor(cobranca.valor_total) * 100:
        raise financial_service.FinanceiroConflito("Origem economica dos creditos diverge da cobranca.")
    if not financiamento_valido(cobranca):
        return
    digest = _fingerprint(proposta)
    existentes = db.scalars(select(CreditoLoteModel).where(CreditoLoteModel.cobranca_id == cobranca.id)).all()
    if existentes:
        esperado = {(i.linha, i.componente, i.servico_id, i.unidade, i.quantidade, i.valor_centavos) for i in contrato.itens}
        atual = {(i.linha, i.componente, i.servico_id, i.unidade, i.quantidade, i.valor_centavos) for i in existentes}
        if atual != esperado or any(i.cliente_id != cobranca.cliente_id or i.contrato_sha256 != digest
            or i.contrato_item_id != direitos[(i.linha, i.componente)].id for i in existentes):
            raise financial_service.FinanceiroConflito("Lotes de creditos requerem conciliacao.")
        registros = db.scalars(select(CreditoLancamentoModel).where(
            CreditoLancamentoModel.lote_id.in_([i.id for i in existentes]))).all()
        if {i.lote_id: i.quantidade for i in registros} != {i.id: i.quantidade for i in existentes}:
            raise financial_service.FinanceiroConflito("Historico de creditos requer conciliacao.")
        return
    for item in contrato.itens:
        lote = CreditoLoteModel(cliente_id=cobranca.cliente_id, cobranca_id=cobranca.id,
                               contrato_item_id=direitos[(item.linha, item.componente)].id,
                               contrato_sha256=digest, **item.model_dump())
        db.add(lote)
        db.flush()
        db.add(CreditoLancamentoModel(lote_id=lote.id, quantidade=lote.quantidade))
        audit_service.record(db, actor=actor, action="credits.acquired", entity_type="credit_lot", entity_id=lote.id,
                             metadata={"charge_id": cobranca.id, "line": item.linha, "component": item.componente},
                             request_id=request_id)
    db.flush()


def carteira(db, cliente_id):
    from models import CobrancaModel

    rows = db.execute(select(CreditoLoteModel, CreditoLancamentoModel).join(
        CreditoLancamentoModel, CreditoLancamentoModel.lote_id == CreditoLoteModel.id
    ).where(CreditoLoteModel.cliente_id == cliente_id).order_by(CreditoLoteModel.id)).all()
    saldos = {}
    lotes = []
    for lote, lancamento in rows:
        cobranca = db.get(CobrancaModel, lote.cobranca_id)
        valida = (cobranca is not None and cobranca.cliente_id == cliente_id and finalidade_creditos(cobranca.proposta)
                  and financiamento_valido(cobranca) and lote.contrato_sha256 == _fingerprint(cobranca.proposta)
                  and lancamento.quantidade == lote.quantidade)
        key = (lote.servico_id, lote.unidade)
        saldo = saldos.setdefault(key, {"servico_id": lote.servico_id, "servico_nome": lote.servico_nome,
                                      "unidade": lote.unidade, "disponivel": Decimal(0), "bloqueado": Decimal(0)})
        saldo["disponivel" if valida else "bloqueado"] += lote.quantidade
        lotes.append({"id": lote.id, "proposta_id": cobranca.proposta_id if cobranca else None,
                      "servico_nome": lote.servico_nome, "unidade": lote.unidade, "quantidade": str(lote.quantidade),
                      "estado": "disponivel" if valida else "bloqueado", "created_at": lote.created_at})
    return {"saldos": [{**s, "disponivel": str(s["disponivel"]), "bloqueado": str(s["bloqueado"])} for s in saldos.values()],
            "lotes": lotes}
