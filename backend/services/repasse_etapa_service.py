"""Stage remuneration: immutable obligations and manual transfer receipts, not live payouts."""
import hashlib
import json
from decimal import Decimal, DecimalException

from models import (
    CobrancaModel,
    CreditoAlocacaoModel,
    CreditoEtapaModel,
    CreditoLoteModel,
    OrcamentoModel,
    ProducaoModel,
    PropostaModel,
    RepasseEtapaModel,
    RepasseEtapaPagamentoModel,
    RepasseProdutorModel,
    UsuarioModel,
)
from services import (
    audit_service,
    credito_alocacao_service,
    credito_producao_service,
    financial_service,
    producao_etapa_service,
    repasse_produtor_service,
)
from services.repasse_base_service import distribuir_pool, parcelas_produtor
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


class RepasseEtapaConflito(Exception):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _cents(value):
    try:
        exact = Decimal(str(value)) * 100
    except (DecimalException, ValueError, TypeError):
        raise RepasseEtapaConflito("Base monetaria da etapa requer conciliacao.") from None
    if not exact.is_finite() or exact < 0 or exact != exact.to_integral_value():
        raise RepasseEtapaConflito("Base monetaria da etapa requer conciliacao.")
    return int(exact)


def _admin(actor):
    if not actor or not actor.ativo or not actor.is_admin or actor.role != "admin":
        raise RepasseEtapaConflito("Somente um administrador ativo pode registrar repasses.")


def _contexto(db, production_id, *, bloquear=False):
    production = db.get(ProducaoModel, production_id)
    if production is None or production.orcamento_id is None:
        raise RepasseEtapaConflito("Producao sem origem comercial identificada.")
    budget_id = production.orcamento_id
    query = select(OrcamentoModel).where(OrcamentoModel.id == budget_id)
    budget = db.scalar((query.with_for_update() if bloquear else query).execution_options(populate_existing=True))
    allocations = list(db.scalars(select(CreditoAlocacaoModel).where(
        CreditoAlocacaoModel.producao_id == production_id).order_by(CreditoAlocacaoModel.id)))
    proposal = db.scalar(select(PropostaModel).where(PropostaModel.orcamento_id == budget_id))
    lots = [db.get(CreditoLoteModel, item.lote_id) for item in allocations]
    charge_ids = {item.cobranca_id for item in lots}
    if proposal:
        charge_ids.update(db.scalars(select(CobrancaModel.id).where(CobrancaModel.proposta_id == proposal.id)))
    if bloquear:
        for charge_id in sorted(charge_ids):
            financial_service.bloquear_cobranca(db, charge_id)
        if lots:
            list(db.scalars(select(CreditoLoteModel).where(CreditoLoteModel.id.in_([lot.id for lot in lots]))
                            .order_by(CreditoLoteModel.id).with_for_update().execution_options(populate_existing=True)))
        production = db.scalar(select(ProducaoModel).where(ProducaoModel.id == production_id)
                               .with_for_update().execution_options(populate_existing=True))
    if production.orcamento_id != budget_id or budget is None:
        raise RepasseEtapaConflito("Titularidade da producao mudou; recarregue antes de continuar.")
    if db.scalar(select(RepasseProdutorModel.id).where(RepasseProdutorModel.producao_id == production_id)):
        raise RepasseEtapaConflito("Repasse legado existente: nao duplique a obrigacao financeira.")
    stages = producao_etapa_service._etapas(db, production_id, bloquear=bloquear)
    if not stages:
        return production, [], "Nenhuma etapa contratual ativa para remunerar."
    if allocations:
        if proposal is not None:
            raise RepasseEtapaConflito("Producao possui duas origens financeiras.")
        bases = []
        reason = None
        for allocation in allocations:
            if credito_alocacao_service._estado(db, allocation) in ("devolvida", "estornada"):
                continue
            if allocation.produtor_centavos is None:
                raise RepasseEtapaConflito("Reserva historica sem base de repasse requer conciliacao.")
            if allocation.cliente_id != budget.cliente_id:
                raise RepasseEtapaConflito("Titularidade da reserva diverge da producao.")
            credito_producao_service._criar_etapas(db, production, allocation, permitir_criacao=False)
            links = list(db.scalars(select(CreditoEtapaModel).where(CreditoEtapaModel.alocacao_id == allocation.id)
                                   .order_by(CreditoEtapaModel.ordem_no_item)))
            by_id = {stage.id: stage for stage in stages}
            selected = [by_id[link.etapa_id] for link in links]
            gross = [_cents(stage.valor) for stage in selected]
            if sum(gross) != allocation.valor_centavos:
                raise RepasseEtapaConflito("Etapas divergem dos centavos reservados.")
            pools = distribuir_pool(allocation.produtor_centavos, gross)
            bases += [(stage, value, pool, _digest({"allocation": allocation.id,
                "contract": allocation.snapshot_servico, "producer_pool": allocation.produtor_centavos}))
                for stage, value, pool in zip(selected, gross, pools)]
            if credito_alocacao_service._estado(db, allocation) != "consumida":
                reason = "Creditos ainda nao consumidos."
            if (any(credito_producao_service.bloqueio_etapa(db, stage) for stage in selected)
                    or not credito_producao_service._financiamento_valido(db, allocation)):
                reason = "Origem dos creditos em conciliacao financeira."
        if {stage.id for stage, *_ in bases} != {stage.id for stage in stages}:
            raise RepasseEtapaConflito("Etapas sem origem economica de creditos.")
        return production, bases, reason
    if proposal is None or not proposal.snapshot_economico or proposal.finalidade != "producao":
        raise RepasseEtapaConflito("Proposta sem snapshot financeiro para remuneracao por etapa.")
    snapshot = proposal.snapshot_economico
    templates = [(line["indice"], position, stage.get("servico_id") or line.get("servico_id"), stage)
                 for line in snapshot["itens"] for position, stage in enumerate(line["etapas"], start=1)]
    if len(templates) != len(stages) or sum(_cents(item[3]["valor"]) for item in templates) != _cents(snapshot["total"]):
        raise RepasseEtapaConflito("Contrato sem etapas para toda a base; exige conciliacao, sem repasse presumido.")
    bases = []
    producer_pools = parcelas_produtor([_cents(item[3]["valor"]) for item in templates])
    for stage, (line, position, service_id, template), producer in zip(stages, templates, producer_pools):
        gross = _cents(template["valor"])
        if (stage.proposta_id != proposal.id or stage.item_indice != line or stage.ordem_no_item != position
                or stage.servico_id != service_id or stage.nome != template["nome"] or _cents(stage.valor) != gross
                or stage.peso_percentual != Decimal(str(template["peso_percentual"]))):
            raise RepasseEtapaConflito("Etapa diverge da origem financeira contratada.")
        bases.append((stage, gross, producer, _digest({"proposal": proposal.id, "snapshot": snapshot})))
    charges = [db.get(CobrancaModel, charge_id) for charge_id in charge_ids]
    paid = len(charges) == 1
    if paid:
        charge = charges[0]
        paid = (charge.moeda == "BRL" and charge.status != "cancelada" and proposal.status == "aceita"
                and charge.cliente_id == budget.cliente_id and _cents(charge.valor_total) == _cents(snapshot["total"])
                and not any(p.reconciliation_status for p in charge.pagamentos)
                and financial_service.valor_pago(charge) == financial_service.normalizar_valor(charge.valor_total))
    return production, bases, None if paid else "Quitacao integral ou conciliacao financeira pendente."


def _estado(production, stage, reason):
    if reason:
        return "bloqueado", reason
    if stage.status != "concluida":
        return "previsto", "Etapa ainda nao concluida."
    if production.status != "finalizado":
        return "bloqueado", "A producao precisa estar finalizada."
    if stage.executor_usuario_id is None:
        return "bloqueado", "Executor da etapa nao identificado."
    return "a_receber", None


def listar(db, production_id, *, produtor_id=None):
    production, bases, reason = _contexto(db, production_id)
    records = {row.etapa_id: row for row in db.scalars(select(RepasseEtapaModel).where(
        RepasseEtapaModel.producao_id == production_id))}
    payments = {row.repasse_id: row for row in db.scalars(select(RepasseEtapaPagamentoModel).where(
        RepasseEtapaPagamentoModel.repasse_id.in_([row.id for row in records.values()])))} if records else {}
    output = []
    for stage, gross, producer, digest in bases:
        owner = stage.executor_usuario_id if stage.status == "concluida" else stage.responsavel_usuario_id
        record = records.get(stage.id)
        if produtor_id is not None and (record.produtor_id if record else owner) != produtor_id:
            continue
        state, blocked = _estado(production, stage, reason)
        payment = payments.get(record.id) if record else None
        if record and (record.bruto_centavos != gross or record.produtor_centavos != producer
                       or record.origem_sha256 != digest or record.produtor_id != stage.executor_usuario_id):
            state, blocked = "bloqueado", "Obrigacao registrada diverge da etapa; requer conciliacao."
        if payment:
            state = "pago"  # A later hold never erases a recorded transfer.
        output.append({"id": record.id if record else None, "etapa_id": stage.id, "etapa_nome": stage.nome,
            "producao_id": production_id, "producao_titulo": production.titulo,
            "produtor_id": record.produtor_id if record else owner,
            "bruto_centavos": gross, "produtor_centavos": producer, "mirai_centavos": gross-producer,
            "estado": state, "bloqueio": blocked, "pago_em": payment.created_at if payment else None,
            "comprovante_arquivo_id": payment.comprovante_arquivo_id if payment else None})
    return output


def listar_produtor(db, producer_id):
    from models import ProducaoEtapaModel
    from models.credito_etapa import etapa_ativa

    production_ids = set(db.scalars(select(ProducaoEtapaModel.producao_id).where(
        ((ProducaoEtapaModel.executor_usuario_id == producer_id)
         | ((ProducaoEtapaModel.status != "concluida") & (ProducaoEtapaModel.responsavel_usuario_id == producer_id))),
        etapa_ativa(ProducaoEtapaModel.id))))
    production_ids.update(db.scalars(select(RepasseEtapaModel.producao_id).where(RepasseEtapaModel.produtor_id == producer_id)))
    output = []
    for production_id in sorted(production_ids, reverse=True):
        try:
            output += listar(db, production_id, produtor_id=producer_id)
        except (RepasseEtapaConflito, credito_alocacao_service.AlocacaoConflito):
            # A conflicting origin cannot erase a previously issued obligation or paid receipt.
            for record in db.scalars(select(RepasseEtapaModel).where(
                    RepasseEtapaModel.producao_id == production_id, RepasseEtapaModel.produtor_id == producer_id)):
                payment = db.scalar(select(RepasseEtapaPagamentoModel).where(RepasseEtapaPagamentoModel.repasse_id == record.id))
                output.append({"id": record.id, "etapa_id": record.etapa_id,
                    "etapa_nome": db.get(ProducaoEtapaModel, record.etapa_id).nome,
                    "producao_id": production_id, "producao_titulo": db.get(ProducaoModel, production_id).titulo,
                    "produtor_id": producer_id, "bruto_centavos": record.bruto_centavos,
                    "produtor_centavos": record.produtor_centavos, "mirai_centavos": record.mirai_centavos,
                    "estado": "pago" if payment else "bloqueado", "bloqueio": "Origem financeira requer conciliacao.",
                    "pago_em": payment.created_at if payment else None,
                    "comprovante_arquivo_id": payment.comprovante_arquivo_id if payment else None})
    return output


def emitir(db, production_id, *, actor, request_id=None):
    try:
        _admin(actor)
        production, bases, reason = _contexto(db, production_id, bloquear=True)
        if reason:
            raise RepasseEtapaConflito(reason)
        eligible = [(stage, gross, producer, digest) for stage, gross, producer, digest in bases if gross > 0
                    and _estado(production, stage, reason)[0] == "a_receber"]
        if not eligible:
            raise RepasseEtapaConflito("Nenhuma parcela financeiramente elegivel.")
        for stage, gross, producer, digest in eligible:
            executor = db.get(UsuarioModel, stage.executor_usuario_id)
            if executor is None or executor.role != "produtor":
                raise RepasseEtapaConflito("Executor da etapa nao e um produtor identificado.")
            previous = db.scalar(select(RepasseEtapaModel).where(RepasseEtapaModel.etapa_id == stage.id))
            if previous:
                if (previous.produtor_id, previous.bruto_centavos, previous.produtor_centavos, previous.origem_sha256) != (
                        executor.id, gross, producer, digest):
                    raise RepasseEtapaConflito("Repasse existente diverge do contrato; requer conciliacao.")
                continue
            record = RepasseEtapaModel(etapa_id=stage.id, producao_id=production.id, produtor_id=executor.id,
                bruto_centavos=gross, produtor_centavos=producer, mirai_centavos=gross-producer,
                origem_sha256=digest, autor_id=actor.id)
            db.add(record)
            db.flush()
            audit_service.record(db, actor=actor, action="stage_payout.issued", entity_type="stage_payout",
                entity_id=record.id, metadata={"stage_id": stage.id, "gross_cents": gross,
                    "producer_cents": producer, "mirai_cents": gross-producer}, request_id=request_id)
        result = listar(db, production_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def pagar(db, production_id, record_id, dados, *, actor, request_id=None):
    try:
        _admin(actor)
        _contexto(db, production_id, bloquear=True)
        rows = listar(db, production_id)
        row = next((item for item in rows if item["id"] == record_id), None)
        if row is None:
            raise RepasseEtapaConflito("Repasse nao encontrado nesta producao.")
        digest = _digest({"production": production_id, "record": record_id, "actor": actor.id,
                          "data": dados.model_dump(mode="json", exclude={"idempotency_key"})})
        previous = db.scalar(select(RepasseEtapaPagamentoModel).where(
            RepasseEtapaPagamentoModel.repasse_id == record_id))
        if previous:
            if previous.request_sha256 != digest:
                raise RepasseEtapaConflito("Repasse ja pago; nao reescreva a transferencia registrada.")
            db.commit()
            return rows
        if row["estado"] != "a_receber" or row["produtor_centavos"] <= 0:
            raise RepasseEtapaConflito("Parcela sem elegibilidade financeira para registrar pagamento.")
        reused = db.scalar(select(RepasseEtapaPagamentoModel.id).where(
            RepasseEtapaPagamentoModel.idempotency_key == str(dados.idempotency_key)))
        if reused:
            raise RepasseEtapaConflito("Referencia de repeticao ja utilizada em outro pagamento.")
        receipt = repasse_produtor_service._receipt(db, production_id, dados.comprovante_arquivo_id)
        if receipt:
            if db.scalar(select(RepasseEtapaPagamentoModel.id).where(
                    RepasseEtapaPagamentoModel.comprovante_arquivo_id == receipt.id)):
                raise RepasseEtapaConflito("Comprovante ja vinculado a outra transferencia.")
            receipt.visivel_produtor = True
        db.add(RepasseEtapaPagamentoModel(repasse_id=record_id, referencia=dados.referencia.strip(),
            comprovante_arquivo_id=receipt.id if receipt else None, autor_id=actor.id,
            idempotency_key=str(dados.idempotency_key), request_sha256=digest))
        audit_service.record(db, actor=actor, action="stage_payout.payment_recorded", entity_type="stage_payout",
            entity_id=record_id, metadata={"receipt_attached": receipt is not None}, request_id=request_id)
        db.flush()
        result = listar(db, production_id)
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise RepasseEtapaConflito("Referencia de repeticao ou comprovante ja utilizado; recarregue antes de continuar.") from None
    except Exception:
        db.rollback()
        raise
