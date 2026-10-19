"""Production rules derived exclusively from frozen credit allocations."""
import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
from fractions import Fraction

from models import (
    CobrancaModel,
    CreditoAlocacaoModel,
    CreditoEtapaModel,
    CreditoLoteModel,
    OrcamentoModel,
    ProducaoCotaArquivoModel,
    ProducaoEtapaAtribuicaoModel,
    ProducaoEtapaModel,
    ProducaoModel,
    ProducaoPoliticaModel,
)
from services import carteira_creditos_service as wallet
from services import (
    cota_arquivo_service,
    politica_service,
    producao_liberacao_service,
    proposta_snapshot_service,
)
from services import credito_alocacao_service as ledger
from sqlalchemy import delete, func, select


def tem_trabalho_previo(db, production):
    ordinary = ~select(CreditoEtapaModel.id).where(CreditoEtapaModel.etapa_id == ProducaoEtapaModel.id).exists()
    return (production.etapas not in (None, "", "[]") or db.scalar(select(ProducaoEtapaModel.id).where(
        ProducaoEtapaModel.producao_id == production.id,
        ordinary | ProducaoEtapaModel.iniciada_em.is_not(None))) is not None)


def _ativas(db, production_id):
    return [item for item in db.scalars(select(CreditoAlocacaoModel).where(
        CreditoAlocacaoModel.producao_id == production_id).order_by(CreditoAlocacaoModel.id))
        if ledger._estado(db, item) in ("reservada", "consumida")]


def _criar_etapas(db, production, allocation, *, permitir_criacao):
    snapshot = allocation.snapshot_servico
    templates = snapshot.get("etapas") or []
    if not templates:
        raise ledger.AlocacaoConflito("O contrato de creditos nao possui etapas; requer conciliacao.")
    try:
        pesos = [Decimal(str(item["peso_percentual"])) * 100 for item in templates]
        if any(not peso.is_finite() or peso != peso.to_integral_value() for peso in pesos):
            raise ValueError()
        values = proposta_snapshot_service.distribuir_centavos(allocation.valor_centavos, [int(peso) for peso in pesos])
    except (DecimalException, ValueError, TypeError, KeyError, OverflowError):
        raise ledger.AlocacaoConflito("Pesos contratuais dos creditos requerem conciliacao.") from None
    existing = db.scalars(select(CreditoEtapaModel).where(
        CreditoEtapaModel.alocacao_id == allocation.id).order_by(CreditoEtapaModel.ordem_no_item)).all()
    if existing:
        if [item.ordem_no_item for item in existing] != list(range(1, len(templates)+1)):
            raise ledger.AlocacaoConflito("Etapas contratuais incompletas; requer conciliacao.")
        for link, template, cents in zip(existing, templates, values):
            stage = db.get(ProducaoEtapaModel, link.etapa_id)
            if (stage.producao_id != production.id or stage.proposta_id != snapshot["proposta_id"]
                    or stage.servico_id != snapshot["servico_id"] or stage.ordem_no_item != link.ordem_no_item
                    or stage.valor != Decimal(cents)/100 or stage.nome != template["nome"]
                    or stage.peso_percentual != Decimal(str(template["peso_percentual"]))):
                raise ledger.AlocacaoConflito("Origem economica das etapas requer conciliacao.")
        return
    if not permitir_criacao:
        raise ledger.AlocacaoConflito("Confirme as etapas contratadas antes do consumo dos creditos.")
    ordem = db.scalar(select(func.max(ProducaoEtapaModel.ordem)).where(ProducaoEtapaModel.producao_id == production.id)) or 0
    prazo_dias, inicio = 0, datetime.now(timezone.utc)
    for posicao, (item, cents) in enumerate(zip(templates, values), start=1):
        if item.get("prazo_dias") is not None:
            prazo_dias += int(item["prazo_dias"])
        stage = ProducaoEtapaModel(producao_id=production.id, proposta_id=snapshot["proposta_id"],
            item_indice=allocation.id, item_descricao=f"Creditos #{allocation.id} - {snapshot['servico_nome']}"[:200],
            servico_id=snapshot["servico_id"], ordem=ordem+posicao, ordem_no_item=posicao,
            nome=item["nome"], peso_percentual=Decimal(str(item["peso_percentual"])), valor=Decimal(cents)/100,
            prazo_dias=item.get("prazo_dias"), unidade=item.get("unidade") or "",
            revisoes_incluidas=item.get("revisoes_incluidas"),
            depende_da_anterior=bool(item.get("depende_da_anterior")) and posicao > 1,
            administrativa=bool(item.get("administrativa")), status="pendente",
            prazo=inicio+timedelta(days=prazo_dias) if item.get("prazo_dias") is not None else None,
            responsavel_usuario_id=production.produtor_id)
        db.add(stage)
        db.flush()
        db.add(CreditoEtapaModel(etapa_id=stage.id, alocacao_id=allocation.id, ordem_no_item=posicao))
        db.add(ProducaoEtapaAtribuicaoModel(etapa_id=stage.id, producao_id=production.id,
            novo_usuario_id=production.produtor_id, motivo="Atribuicao inicial do contrato de creditos"))
    db.flush()


def _snapshot_agregado(allocations):
    groups = {}
    for item in allocations:
        snapshot = item.snapshot_servico
        try:
            units = Fraction(Decimal(snapshot["quantidade_creditos_lote"]))
            packages = Fraction(Decimal(snapshot["quantidade_planos_lote"]))
            if units <= 0 or packages <= 0:
                raise ValueError()
        except (DecimalException, KeyError, ValueError, TypeError, OverflowError):
            raise ledger.AlocacaoConflito("Unidades contratuais incompletas; requer conciliacao.") from None
        key = (snapshot["contrato_sha256"], snapshot["linha"], snapshot["componente"])
        group = groups.setdefault(key, {"template": snapshot, "quantidade": Fraction(0)})
        if json.dumps(group["template"], sort_keys=True) != json.dumps(snapshot, sort_keys=True):
            raise ledger.AlocacaoConflito("Regras da mesma origem contratual divergem.")
        group["quantidade"] += Fraction(item.quantidade) * packages / units
    # Preserve 5.09's per-production ceiling, grouping fractions before rounding.
    return {"itens": [{"servico_id": group["template"]["servico_id"],
                        "quantidade": str(math.ceil(group["quantidade"])),
                        "cotas_arquivos": group["template"]["cotas_arquivos"],
                        "politicas": group["template"]["politicas"]} for group in groups.values()]}


def sincronizar(db, production, allocation):
    """Caller holds production lock and owns commit; old stages and attribution records remain."""
    state = ledger._estado(db, allocation)
    if state in ("reservada", "consumida"):
        _criar_etapas(db, production, allocation, permitir_criacao=state == "reservada")
    if state == "consumida":
        return  # The active contract did not change; retain quota identities and exceptions.
    active = _ativas(db, production.id)
    if not active:
        return  # Keep previous limits; the credit-history guard blocks uploads and final delivery.
    snapshot = _snapshot_agregado(active)
    quotas = list(db.scalars(select(ProducaoCotaArquivoModel).where(ProducaoCotaArquivoModel.producao_id == production.id)))
    if not any(item.origem == "admin" for item in quotas):
        db.execute(delete(ProducaoCotaArquivoModel).where(ProducaoCotaArquivoModel.producao_id == production.id))
        db.add_all([ProducaoCotaArquivoModel(producao_id=production.id, origem="contrato", **item)
                    for item in cota_arquivo_service.agregar(snapshot)])
    row = db.get(ProducaoPoliticaModel, production.id)
    contract = politica_service.agregar(snapshot)
    if row is None:
        db.add(ProducaoPoliticaModel(producao_id=production.id, contrato=contract))
    else:
        row.contrato = contract  # Preserve every reasoned admin exception.
    db.flush()


def _financiamento_valido(db, allocation):
    lot = db.get(CreditoLoteModel, allocation.lote_id)
    charge = db.get(CobrancaModel, lot.cobranca_id)
    production = db.get(ProducaoModel, allocation.producao_id)
    budget = db.get(OrcamentoModel, production.orcamento_id) if production.orcamento_id else None
    return (budget is not None and budget.cliente_id == allocation.cliente_id
            and charge is not None and charge.cliente_id == allocation.cliente_id
            and wallet.financiamento_valido(charge) and lot.contrato_sha256 == wallet._fingerprint(charge.proposta))


def bloqueio_etapa(db, stage):
    link = db.scalar(select(CreditoEtapaModel).where(CreditoEtapaModel.etapa_id == stage.id))
    if link is None:
        return None
    allocation = db.get(CreditoAlocacaoModel, link.alocacao_id)
    if allocation.producao_id != stage.producao_id or ledger._estado(db, allocation) != "consumida":
        return "Creditos reservados: confirme o uso antes de executar as etapas."
    if not producao_liberacao_service.pipeline_v2_habilitada() or not _financiamento_valido(db, allocation):
        return "Creditos requerem conciliacao financeira antes da execucao."
    return None


def validar_upload(db, producao_id, tipo):
    if db.scalar(select(CreditoAlocacaoModel.id).where(CreditoAlocacaoModel.producao_id == producao_id)) is None:
        return
    active = _ativas(db, producao_id)
    if not active or not producao_liberacao_service.pipeline_v2_habilitada() or not all(
            _financiamento_valido(db, item) for item in active):
        raise ledger.AlocacaoConflito("Envio bloqueado: creditos sem reserva ativa ou em conciliacao.")
    if tipo in ("previa", "entrega") and any(ledger._estado(db, item) != "consumida" for item in active):
        raise ledger.AlocacaoConflito("Confirme o uso dos creditos antes de enviar previas ou entregas.")
