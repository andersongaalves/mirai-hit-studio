"""Mirai Hit Labs admin panel: overview, orders, customers, licenses, releases, coupons
and store content. Plugin editing, installers and covers stay in ``plugin_service``.

Money: BRL comes from studio-checkout licenses (``origem='compra'``, value net of any
coupon); USD comes from paid Stripe orders. Test clients (``clientes.is_test``) never count
in the overview totals.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import (
    AuditLogModel,
    ClienteModel,
    CobrancaModel,
    LabsConteudoModel,
    LabsCupomModel,
    LabsCupomUsoModel,
    PluginLicencaModel,
    PluginModel,
    PluginPedidoStripeModel,
    PluginVersaoModel,
    UsuarioModel,
)
from services import audit_service

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
PENDING_USE_WINDOW = timedelta(hours=2)
LIST_LIMIT = 300


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _iso(value):
    value = _aware(value)
    return value.isoformat() if value else None


def _money(value):
    return f"{Decimal(str(value or 0)).quantize(CENT)}"


def _like(term):
    term = (term or "").strip()[:120]
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# ---------------------------------------------------------------- overview


def resumo(db: Session, dias: int = 30):
    dias = max(1, min(int(dias or 30), 365))
    since = _now() - timedelta(days=dias)
    real = ClienteModel.is_test.is_(False)

    def total_brl(after=None):
        query = (select(func.coalesce(func.sum(PluginLicencaModel.valor), 0))
                 .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
                 .where(PluginLicencaModel.origem == "compra", PluginLicencaModel.status == "ativa", real))
        if after is not None:
            query = query.where(PluginLicencaModel.ativada_em >= after)
        return Decimal(str(db.scalar(query) or 0))

    def total_usd(after=None):
        query = (select(func.coalesce(func.sum(PluginPedidoStripeModel.valor), 0))
                 .join(ClienteModel, ClienteModel.id == PluginPedidoStripeModel.cliente_id)
                 .where(PluginPedidoStripeModel.status == "pago", real))
        if after is not None:
            query = query.where(PluginPedidoStripeModel.pago_em >= after)
        return Decimal(str(db.scalar(query) or 0))

    # Licenses activated in the period, per day (computed here: portable and small).
    recent = db.execute(
        select(PluginLicencaModel.ativada_em, PluginLicencaModel.origem, PluginLicencaModel.valor,
               PluginLicencaModel.plugin_id)
        .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
        .where(PluginLicencaModel.status == "ativa", PluginLicencaModel.ativada_em >= since, real)
    ).all()
    days = [(since + timedelta(days=offset + 1)).date() for offset in range(dias)]
    per_day = {day: {"vendas": 0, "gratis": 0} for day in days}
    for activated, origem, _valor, _plugin in recent:
        day = _aware(activated).date()
        if day in per_day:
            per_day[day]["vendas" if origem in ("compra", "stripe") else "gratis"] += 1

    downloads = db.execute(
        select(AuditLogModel.metadata_json)
        .where(AuditLogModel.action == "plugin.installer_downloaded", AuditLogModel.created_at >= since)
    ).scalars().all()
    downloads_por_plugin = defaultdict(int)
    for meta in downloads:
        plugin_id = (meta or {}).get("plugin_id")
        if isinstance(plugin_id, int):
            downloads_por_plugin[plugin_id] += 1

    status_counts = dict(db.execute(
        select(PluginLicencaModel.status, func.count())
        .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
        .where(real).group_by(PluginLicencaModel.status)
    ).all())
    aguardando = db.scalar(
        select(func.count()).select_from(PluginLicencaModel)
        .where(PluginLicencaModel.status == "reservada", PluginLicencaModel.motivo.is_(None))
    ) or 0

    contas = db.scalar(select(func.count()).select_from(UsuarioModel).where(
        UsuarioModel.somente_labs.is_(True), UsuarioModel.is_test.is_(False))) or 0
    contas_novas = db.scalar(select(func.count()).select_from(UsuarioModel).where(
        UsuarioModel.somente_labs.is_(True), UsuarioModel.is_test.is_(False),
        UsuarioModel.created_at >= since)) or 0

    # Per plugin: active licenses, revenue and downloads in the period.
    plugins = db.scalars(select(PluginModel).order_by(PluginModel.ordem, PluginModel.nome)).all()
    ativas = dict(db.execute(
        select(PluginLicencaModel.plugin_id, func.count())
        .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
        .where(PluginLicencaModel.status == "ativa", real).group_by(PluginLicencaModel.plugin_id)
    ).all())
    brl = dict(db.execute(
        select(PluginLicencaModel.plugin_id, func.sum(PluginLicencaModel.valor))
        .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
        .where(PluginLicencaModel.origem == "compra", PluginLicencaModel.status == "ativa", real)
        .group_by(PluginLicencaModel.plugin_id)
    ).all())
    usd = dict(db.execute(
        select(PluginPedidoStripeModel.plugin_id, func.sum(PluginPedidoStripeModel.valor))
        .join(ClienteModel, ClienteModel.id == PluginPedidoStripeModel.cliente_id)
        .where(PluginPedidoStripeModel.status == "pago", real).group_by(PluginPedidoStripeModel.plugin_id)
    ).all())

    ultimas = db.execute(
        select(PluginLicencaModel, PluginModel.nome, ClienteModel.nome)
        .join(PluginModel, PluginModel.id == PluginLicencaModel.plugin_id)
        .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
        .where(PluginLicencaModel.status == "ativa", PluginLicencaModel.ativada_em.is_not(None))
        .order_by(PluginLicencaModel.ativada_em.desc()).limit(8)
    ).all()

    return {
        "dias": dias,
        "receita": {
            "periodo": {"brl": _money(total_brl(since)), "usd": _money(total_usd(since))},
            "total": {"brl": _money(total_brl()), "usd": _money(total_usd())},
        },
        "vendas_periodo": sum(item["vendas"] for item in per_day.values()),
        "gratis_periodo": sum(item["gratis"] for item in per_day.values()),
        "downloads_periodo": len(downloads),
        "licencas": {"ativas": status_counts.get("ativa", 0), "aguardando_pagamento": aguardando,
                     "revogadas": status_counts.get("revogada", 0)},
        "contas_labs": {"total": contas, "novas_periodo": contas_novas},
        "serie": [{"dia": day.isoformat(), **per_day[day]} for day in days],
        "plugins": [
            {"id": plugin.id, "nome": plugin.nome, "slug": plugin.slug, "status": plugin.status,
             "versao": plugin.versao, "capa_url": plugin.capa_url,
             "licencas_ativas": ativas.get(plugin.id, 0),
             "receita_brl": _money(brl.get(plugin.id)), "receita_usd": _money(usd.get(plugin.id)),
             "downloads_periodo": downloads_por_plugin.get(plugin.id, 0)}
            for plugin in plugins
        ],
        "ultimas_licencas": [
            {"id": license.id, "plugin": plugin_name, "cliente": client_name, "origem": license.origem,
             "valor": _money(license.valor), "moeda": "usd" if license.origem == "stripe" else "brl",
             "ativada_em": _iso(license.ativada_em)}
            for license, plugin_name, client_name in ultimas
        ],
    }


# ---------------------------------------------------------------- orders


MP_STATUS = {"ativa": "pago", "cancelada": "cancelado", "revogada": "revogado"}
STRIPE_STATUS = {"aberto": "aguardando", "pago": "pago", "expirado": "expirado",
                 "reembolsado": "reembolsado", "contestado": "contestado"}


def _cupons_por(db, column, ids):
    if not ids:
        return {}
    rows = db.execute(
        select(column, LabsCupomModel.codigo, LabsCupomUsoModel.desconto)
        .join(LabsCupomModel, LabsCupomModel.id == LabsCupomUsoModel.cupom_id)
        .where(column.in_(ids))
    ).all()
    return {key: {"codigo": code, "desconto": _money(discount)} for key, code, discount in rows}


def pedidos(db: Session, q: str | None = None, moeda: str | None = None, status: str | None = None):
    rows = []
    term = (q or "").strip()
    if moeda in (None, "", "brl"):
        query = (
            select(PluginLicencaModel, PluginModel.nome, ClienteModel)
            .join(PluginModel, PluginModel.id == PluginLicencaModel.plugin_id)
            .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
            .where(PluginLicencaModel.origem == "compra")
            .order_by(PluginLicencaModel.id.desc()).limit(LIST_LIMIT)
        )
        if term:
            query = query.where(or_(ClienteModel.nome.ilike(_like(term), escape="\\"),
                                    ClienteModel.email.ilike(_like(term), escape="\\"),
                                    PluginModel.nome.ilike(_like(term), escape="\\")))
        licenses = db.execute(query).all()
        proposal_ids = [license.proposta_id for license, _, _ in licenses if license.proposta_id]
        charges = {}
        if proposal_ids:
            for charge in db.scalars(select(CobrancaModel).where(CobrancaModel.proposta_id.in_(proposal_ids))
                                     .order_by(CobrancaModel.id)):
                charges[charge.proposta_id] = charge
        coupons = _cupons_por(db, LabsCupomUsoModel.licenca_id, [license.id for license, _, _ in licenses])
        for license, plugin_name, client in licenses:
            charge = charges.get(license.proposta_id)
            if license.status == "reservada":
                state = "revertido" if license.motivo == "pagamento_revertido" else "aguardando"
                if state == "aguardando" and charge is not None and charge.status == "cancelada":
                    state = "cancelado"
            else:
                state = MP_STATUS.get(license.status, license.status)
            rows.append({
                "id": f"brl-{license.id}", "tipo": "checkout", "moeda": "brl", "status": state,
                "plugin": plugin_name, "plugin_id": license.plugin_id,
                "cliente": {"id": client.id, "nome": client.nome, "email": client.email, "teste": bool(client.is_test)},
                "valor": _money(charge.valor_total if charge is not None else license.valor),
                "licenca_id": license.id, "proposta_id": license.proposta_id,
                "cobranca_id": charge.id if charge is not None else None,
                "cupom": coupons.get(license.id),
                "criado_em": _iso(license.created_at), "pago_em": _iso(license.ativada_em) if license.status == "ativa" else None,
                "pode_reembolsar": False,
            })
    if moeda in (None, "", "usd"):
        query = (
            select(PluginPedidoStripeModel, PluginModel.nome, ClienteModel)
            .join(PluginModel, PluginModel.id == PluginPedidoStripeModel.plugin_id)
            .join(ClienteModel, ClienteModel.id == PluginPedidoStripeModel.cliente_id)
            .order_by(PluginPedidoStripeModel.id.desc()).limit(LIST_LIMIT)
        )
        if term:
            query = query.where(or_(ClienteModel.nome.ilike(_like(term), escape="\\"),
                                    ClienteModel.email.ilike(_like(term), escape="\\"),
                                    PluginModel.nome.ilike(_like(term), escape="\\"),
                                    PluginPedidoStripeModel.stripe_session_id == term,
                                    PluginPedidoStripeModel.stripe_payment_intent == term))
        orders = db.execute(query).all()
        coupons = _cupons_por(db, LabsCupomUsoModel.pedido_stripe_id, [order.id for order, _, _ in orders])
        for order, plugin_name, client in orders:
            rows.append({
                "id": f"usd-{order.id}", "tipo": "stripe", "moeda": "usd",
                "status": STRIPE_STATUS.get(order.status, order.status),
                "plugin": plugin_name, "plugin_id": order.plugin_id,
                "cliente": {"id": client.id, "nome": client.nome, "email": client.email, "teste": bool(client.is_test)},
                "valor": _money(order.valor), "licenca_id": order.licenca_id, "pedido_id": order.id,
                "stripe_payment_intent": order.stripe_payment_intent,
                "cupom": coupons.get(order.id),
                "criado_em": _iso(order.created_at), "pago_em": _iso(order.pago_em),
                "pode_reembolsar": order.status == "pago" and bool(order.stripe_payment_intent),
            })
    if status:
        rows = [row for row in rows if row["status"] == status]
    rows.sort(key=lambda row: row["criado_em"] or "", reverse=True)
    return rows[:LIST_LIMIT]


def reembolsar_stripe(db: Session, pedido_id: int, motivo: str, actor, request_id=None):
    from services import stripe_service

    order = db.scalar(select(PluginPedidoStripeModel).where(PluginPedidoStripeModel.id == pedido_id).with_for_update())
    if order is None:
        raise HTTPException(404, "Pedido não encontrado.")
    if order.status != "pago" or not order.stripe_payment_intent:
        raise HTTPException(409, "Só um pedido pago pode ser reembolsado.")
    if not stripe_service.configurado():
        raise HTTPException(503, "Stripe não está configurado.")
    stripe_service._api("POST", "/refunds", data={
        "payment_intent": order.stripe_payment_intent,
        "metadata[order_id]": str(order.id),
        "metadata[motivo]": motivo,
    }, idempotency_key=f"mirai-labs-refund-{order.id}")
    # Stripe also sends charge.refunded; applying it now keeps the panel in step.
    stripe_service._reverter(db, order, "reembolsado", request_id)
    audit_service.record(db, actor=actor, action="plugin.stripe_refunded", entity_type="plugin_pedido_stripe",
                         entity_id=order.id, metadata={"plugin_id": order.plugin_id, "motivo": motivo},
                         request_id=request_id)
    db.commit()
    return {"id": order.id, "status": order.status}


# ---------------------------------------------------------------- customers


def _contas_por_cliente(db, client_ids):
    if not client_ids:
        return {}
    users = db.scalars(select(UsuarioModel).where(UsuarioModel.cliente_id.in_(client_ids))).all()
    return {user.cliente_id: user for user in users}


def _conta(user):
    if user is None:
        return {"tipo": "sem_conta"}
    return {"tipo": "labs" if user.somente_labs else "estudio", "usuario": user.username,
            "ativo": bool(user.ativo), "criada_em": _iso(user.created_at)}


def clientes(db: Session, q: str | None = None):
    licensed = select(PluginLicencaModel.cliente_id).distinct()
    labs_users = select(UsuarioModel.cliente_id).where(UsuarioModel.somente_labs.is_(True),
                                                        UsuarioModel.cliente_id.is_not(None))
    query = (select(ClienteModel)
             .where(or_(ClienteModel.id.in_(licensed), ClienteModel.id.in_(labs_users)))
             .order_by(ClienteModel.id.desc()).limit(LIST_LIMIT))
    term = (q or "").strip()
    if term:
        query = query.where(or_(ClienteModel.nome.ilike(_like(term), escape="\\"),
                                ClienteModel.email.ilike(_like(term), escape="\\")))
    clients = db.scalars(query).all()
    ids = [client.id for client in clients]
    accounts = _contas_por_cliente(db, ids)
    active, brl, usd = {}, {}, {}
    if ids:
        active = dict(db.execute(
            select(PluginLicencaModel.cliente_id, func.count())
            .where(PluginLicencaModel.cliente_id.in_(ids), PluginLicencaModel.status == "ativa")
            .group_by(PluginLicencaModel.cliente_id)).all())
        brl = dict(db.execute(
            select(PluginLicencaModel.cliente_id, func.sum(PluginLicencaModel.valor))
            .where(PluginLicencaModel.cliente_id.in_(ids), PluginLicencaModel.status == "ativa",
                   PluginLicencaModel.origem == "compra")
            .group_by(PluginLicencaModel.cliente_id)).all())
        usd = dict(db.execute(
            select(PluginPedidoStripeModel.cliente_id, func.sum(PluginPedidoStripeModel.valor))
            .where(PluginPedidoStripeModel.cliente_id.in_(ids), PluginPedidoStripeModel.status == "pago")
            .group_by(PluginPedidoStripeModel.cliente_id)).all())
    return [
        {"id": client.id, "nome": client.nome, "email": client.email, "teste": bool(client.is_test),
         "conta": _conta(accounts.get(client.id)), "licencas_ativas": active.get(client.id, 0),
         "total_brl": _money(brl.get(client.id)), "total_usd": _money(usd.get(client.id)),
         "criado_em": _iso(client.created_at)}
        for client in clients
    ]


def cliente_detalhe(db: Session, cliente_id: int):
    client = db.get(ClienteModel, cliente_id)
    if client is None:
        raise HTTPException(404, "Cliente não encontrado.")
    user = _contas_por_cliente(db, [client.id]).get(client.id)
    return {
        "id": client.id, "nome": client.nome, "email": client.email, "telefone": client.telefone,
        "teste": bool(client.is_test), "ativo": bool(client.ativo), "criado_em": _iso(client.created_at),
        "conta": _conta(user),
        "licencas": licencas(db, cliente_id=client.id),
        "pedidos": [row for row in pedidos(db, q=client.email) if row["cliente"]["id"] == client.id]
        if client.email else [],
    }


# ---------------------------------------------------------------- licenses


def _licenca_row(license, plugin, client):
    return {
        "id": license.id, "plugin_id": plugin.id, "plugin": plugin.nome, "slug": plugin.slug,
        "cliente_id": client.id, "cliente": client.nome, "email": client.email, "teste": bool(client.is_test),
        "origem": license.origem, "status": license.status, "motivo": license.motivo, "chave": license.chave,
        "valor": _money(license.valor), "moeda": "usd" if license.origem == "stripe" else "brl",
        "proposta_id": license.proposta_id,
        "criada_em": _iso(license.created_at), "ativada_em": _iso(license.ativada_em),
        "encerrada_em": _iso(license.encerrada_em),
    }


def licencas(db: Session, q: str | None = None, status: str | None = None, plugin_id: int | None = None,
             origem: str | None = None, cliente_id: int | None = None):
    query = (select(PluginLicencaModel, PluginModel, ClienteModel)
             .join(PluginModel, PluginModel.id == PluginLicencaModel.plugin_id)
             .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
             .order_by(PluginLicencaModel.id.desc()).limit(LIST_LIMIT))
    term = (q or "").strip()
    if term:
        query = query.where(or_(PluginLicencaModel.chave == term.upper(),
                                ClienteModel.nome.ilike(_like(term), escape="\\"),
                                ClienteModel.email.ilike(_like(term), escape="\\")))
    if status:
        query = query.where(PluginLicencaModel.status == status)
    if plugin_id:
        query = query.where(PluginLicencaModel.plugin_id == plugin_id)
    if origem:
        query = query.where(PluginLicencaModel.origem == origem)
    if cliente_id:
        query = query.where(PluginLicencaModel.cliente_id == cliente_id)
    return [_licenca_row(*row) for row in db.execute(query).all()]


def reativar(db: Session, licenca_id: int, actor):
    from services import plugin_service

    license = db.scalar(select(PluginLicencaModel).where(PluginLicencaModel.id == licenca_id).with_for_update())
    if license is None:
        raise HTTPException(404, "Licença não encontrada.")
    if license.status != "revogada":
        raise HTTPException(409, "Só uma licença revogada pode ser reativada.")
    if plugin_service._licenca_ativa(db, license.plugin_id, license.cliente_id) is not None:
        raise HTTPException(409, "Este cliente já tem outra licença ativa deste plugin.")
    license.status = "ativa"
    license.ativada_em = _now()
    license.encerrada_em = None
    license.motivo = None
    audit_service.record(db, actor=actor, action="plugin.license_reactivated", entity_type="plugin_licenca",
                         entity_id=license.id, metadata={"plugin_id": license.plugin_id})
    db.commit()
    return {"id": license.id, "status": license.status}


def cortesia_por_email(db: Session, plugin_id: int, email: str, actor):
    from services import plugin_service

    client = db.scalar(select(ClienteModel).where(func.lower(ClienteModel.email) == email)
                       .order_by(ClienteModel.id).limit(1))
    if client is None:
        user = db.scalar(select(UsuarioModel).where(func.lower(UsuarioModel.email) == email,
                                                    UsuarioModel.cliente_id.is_not(None)).limit(1))
        client = db.get(ClienteModel, user.cliente_id) if user is not None else None
    if client is None:
        raise HTTPException(404, "Ninguém com este e-mail. Peça para a pessoa criar a conta na loja.")
    return plugin_service.conceder_cortesia(db, plugin_id, client.id, actor)


# ---------------------------------------------------------------- releases


def _versao_row(release):
    return {"id": release.id, "plugin_id": release.plugin_id, "versao": release.versao, "canal": release.canal,
            "notas": release.notas, "notas_en": release.notas_en, "obrigatoria": bool(release.obrigatoria),
            "publicada": release.publicada_em is not None, "publicada_em": _iso(release.publicada_em),
            "criada_em": _iso(release.created_at)}


def _plugin(db, plugin_id, lock=False):
    query = select(PluginModel).where(PluginModel.id == plugin_id)
    if lock:
        query = query.with_for_update()
    plugin = db.scalar(query)
    if plugin is None:
        raise HTTPException(404, "Plugin não encontrado.")
    return plugin


def _ordenadas(db, plugin_id):
    rows = db.scalars(select(PluginVersaoModel).where(PluginVersaoModel.plugin_id == plugin_id)).all()
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(rows, key=lambda row: (_aware(row.publicada_em) or _aware(row.created_at) or epoch, row.id),
                  reverse=True)


def versoes(db: Session, plugin_id: int):
    _plugin(db, plugin_id)
    return [_versao_row(row) for row in _ordenadas(db, plugin_id)]


def _sincronizar_versao_atual(db, plugin):
    stable = [row for row in _ordenadas(db, plugin.id) if row.canal == "estavel" and row.publicada_em]
    if stable:
        plugin.versao = stable[0].versao


def _aplicar_versao(release, payload):
    release.versao = payload.versao
    release.canal = payload.canal
    release.notas = payload.notas
    release.notas_en = payload.notas_en
    release.obrigatoria = payload.obrigatoria
    if payload.publicar and release.publicada_em is None:
        release.publicada_em = _now()
    elif not payload.publicar:
        release.publicada_em = None


def _salvar_versao(db, plugin, release, actor, action):
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Esta versão já existe neste plugin.") from None
    _sincronizar_versao_atual(db, plugin)
    audit_service.record(db, actor=actor, action=action, entity_type="plugin_versao", entity_id=release.id,
                         metadata={"plugin_id": plugin.id, "versao": release.versao, "canal": release.canal})
    db.commit()
    db.refresh(release)
    return _versao_row(release)


def criar_versao(db: Session, plugin_id: int, payload, actor):
    plugin = _plugin(db, plugin_id, lock=True)
    release = PluginVersaoModel(plugin_id=plugin.id)
    _aplicar_versao(release, payload)
    db.add(release)
    return _salvar_versao(db, plugin, release, actor, "plugin.release_created")


def _versao(db, versao_id):
    release = db.scalar(select(PluginVersaoModel).where(PluginVersaoModel.id == versao_id).with_for_update())
    if release is None:
        raise HTTPException(404, "Versão não encontrada.")
    return release


def editar_versao(db: Session, versao_id: int, payload, actor):
    release = _versao(db, versao_id)
    plugin = _plugin(db, release.plugin_id, lock=True)
    _aplicar_versao(release, payload)
    return _salvar_versao(db, plugin, release, actor, "plugin.release_updated")


def remover_versao(db: Session, versao_id: int, actor):
    release = _versao(db, versao_id)
    plugin = _plugin(db, release.plugin_id, lock=True)
    db.delete(release)
    db.flush()
    _sincronizar_versao_atual(db, plugin)
    audit_service.record(db, actor=actor, action="plugin.release_removed", entity_type="plugin_versao",
                         entity_id=versao_id, metadata={"plugin_id": plugin.id, "versao": release.versao})
    db.commit()
    return {"ok": True, "versao_atual": plugin.versao}


def _atualizacao(db, plugin, canal="estavel"):
    from core import config

    allowed = ("estavel", "beta") if canal == "beta" else ("estavel",)
    releases = [row for row in _ordenadas(db, plugin.id) if row.publicada_em and row.canal in allowed]
    latest = releases[0] if releases else None
    base = getattr(config.settings, "LABS_PUBLIC_URL", "https://labs.miraihitstudio.com.br").rstrip("/")
    return {
        "plugin": plugin.slug,
        "nome": plugin.nome,
        "versao": latest.versao if latest else plugin.versao,
        "canal": latest.canal if latest else "estavel",
        "publicada_em": _iso(latest.publicada_em) if latest else None,
        "obrigatoria": bool(latest.obrigatoria) if latest else False,
        "notas": latest.notas if latest else None,
        "notas_en": latest.notas_en if latest else None,
        "pagina": f"{base}/plugins/{plugin.slug}",
        "download": f"{base}/my-plugins",
    }


def publico_atualizacao(db: Session, slug: str, canal: str = "estavel"):
    plugin = db.scalar(select(PluginModel).where(PluginModel.slug == slug.strip().lower(),
                                                 PluginModel.status == "publicado"))
    if plugin is None:
        raise HTTPException(404, "Plugin não encontrado.")
    return _atualizacao(db, plugin, canal)


def publico_atualizacoes(db: Session):
    plugins = db.scalars(select(PluginModel).where(PluginModel.status == "publicado").order_by(PluginModel.slug)).all()
    return {"gerado_em": _iso(_now()), "plugins": {plugin.slug: _atualizacao(db, plugin) for plugin in plugins}}


# ---------------------------------------------------------------- coupons


def _usos_validos(db, cupom_id, cliente_id=None):
    """Uses that count: the license is active or waiting for payment (not reverted), or the
    purchase just started and has no license yet."""
    query = (select(func.count()).select_from(LabsCupomUsoModel)
             .outerjoin(PluginLicencaModel, PluginLicencaModel.id == LabsCupomUsoModel.licenca_id)
             .where(LabsCupomUsoModel.cupom_id == cupom_id,
                    or_(PluginLicencaModel.status == "ativa",
                        (PluginLicencaModel.status == "reservada") & PluginLicencaModel.motivo.is_(None),
                        LabsCupomUsoModel.licenca_id.is_(None)
                        & (LabsCupomUsoModel.created_at >= _now() - PENDING_USE_WINDOW))))
    if cliente_id is not None:
        query = query.where(LabsCupomUsoModel.cliente_id == cliente_id)
    return db.scalar(query) or 0


def _cupom_row(db, coupon, plugin_names):
    uses = _usos_validos(db, coupon.id)
    total = db.scalar(select(func.count()).select_from(LabsCupomUsoModel)
                      .where(LabsCupomUsoModel.cupom_id == coupon.id)) or 0
    now = _now()
    if not coupon.ativo:
        state = "inativo"
    elif coupon.valido_ate and _aware(coupon.valido_ate) <= now:
        state = "expirado"
    elif coupon.valido_de and _aware(coupon.valido_de) > now:
        state = "agendado"
    elif coupon.max_usos is not None and uses >= coupon.max_usos:
        state = "esgotado"
    else:
        state = "ativo"
    return {"id": coupon.id, "codigo": coupon.codigo, "descricao": coupon.descricao, "tipo": coupon.tipo,
            "valor": _money(coupon.valor), "plugin_id": coupon.plugin_id,
            "plugin": plugin_names.get(coupon.plugin_id) if coupon.plugin_id else None,
            "valido_de": _iso(coupon.valido_de), "valido_ate": _iso(coupon.valido_ate),
            "max_usos": coupon.max_usos, "ativo": bool(coupon.ativo), "usos": uses, "usos_registrados": total,
            "situacao": state, "criado_em": _iso(coupon.created_at)}


def _nomes(db):
    return dict(db.execute(select(PluginModel.id, PluginModel.nome)).all())


def cupons(db: Session):
    names = _nomes(db)
    return [_cupom_row(db, row, names) for row in db.scalars(select(LabsCupomModel).order_by(LabsCupomModel.id.desc()))]


def _aplicar_cupom_payload(db, coupon, payload):
    if payload.plugin_id is not None:
        _plugin(db, payload.plugin_id)
    coupon.codigo = payload.codigo
    coupon.descricao = payload.descricao
    coupon.tipo = payload.tipo
    coupon.valor = payload.valor
    coupon.plugin_id = payload.plugin_id
    coupon.valido_de = payload.valido_de
    coupon.valido_ate = payload.valido_ate
    coupon.max_usos = payload.max_usos
    coupon.ativo = payload.ativo


def _salvar_cupom(db, coupon, actor, action):
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe um cupom com este código.") from None
    audit_service.record(db, actor=actor, action=action, entity_type="labs_cupom", entity_id=coupon.id,
                         metadata={"codigo": coupon.codigo, "ativo": coupon.ativo})
    db.commit()
    db.refresh(coupon)
    return _cupom_row(db, coupon, _nomes(db))


def criar_cupom(db: Session, payload, actor):
    coupon = LabsCupomModel()
    _aplicar_cupom_payload(db, coupon, payload)
    db.add(coupon)
    return _salvar_cupom(db, coupon, actor, "labs.coupon_created")


def editar_cupom(db: Session, cupom_id: int, payload, actor):
    coupon = db.scalar(select(LabsCupomModel).where(LabsCupomModel.id == cupom_id).with_for_update())
    if coupon is None:
        raise HTTPException(404, "Cupom não encontrado.")
    used = db.scalar(select(func.count()).select_from(LabsCupomUsoModel)
                     .where(LabsCupomUsoModel.cupom_id == coupon.id)) or 0
    if used and coupon.codigo != payload.codigo:
        raise HTTPException(409, "Este cupom já foi usado; o código não pode mudar.")
    _aplicar_cupom_payload(db, coupon, payload)
    return _salvar_cupom(db, coupon, actor, "labs.coupon_updated")


def remover_cupom(db: Session, cupom_id: int, actor):
    coupon = db.scalar(select(LabsCupomModel).where(LabsCupomModel.id == cupom_id).with_for_update())
    if coupon is None:
        raise HTTPException(404, "Cupom não encontrado.")
    if db.scalar(select(func.count()).select_from(LabsCupomUsoModel).where(LabsCupomUsoModel.cupom_id == coupon.id)):
        raise HTTPException(409, "Este cupom já foi usado; desative em vez de apagar.")
    db.delete(coupon)
    audit_service.record(db, actor=actor, action="labs.coupon_removed", entity_type="labs_cupom",
                         entity_id=cupom_id, metadata={"codigo": coupon.codigo})
    db.commit()
    return {"ok": True}


def _desconto(coupon, price: Decimal) -> Decimal:
    if coupon.tipo == "percentual":
        value = (price * Decimal(str(coupon.valor)) / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
    else:
        value = Decimal(str(coupon.valor)).quantize(CENT)
    return min(price, max(Decimal(0), value))


def _checar(db, coupon, plugin, cliente_id=None):
    """Raises with the reason a coupon cannot be used on this plugin (messages start with 'Cupom')."""
    now = _now()
    if coupon is None or not coupon.ativo:
        raise HTTPException(409, "Cupom inválido.")
    if coupon.valido_de and _aware(coupon.valido_de) > now:
        raise HTTPException(409, "Cupom inválido.")
    if coupon.valido_ate and _aware(coupon.valido_ate) <= now:
        raise HTTPException(409, "Cupom expirado.")
    if coupon.plugin_id is not None and coupon.plugin_id != plugin.id:
        raise HTTPException(409, "Cupom não vale para este plugin.")
    if coupon.max_usos is not None and _usos_validos(db, coupon.id) >= coupon.max_usos:
        raise HTTPException(409, "Cupom esgotado.")
    if cliente_id is not None and _usos_validos(db, coupon.id, cliente_id):
        raise HTTPException(409, "Cupom já usado nesta conta.")


def aplicar_cupom(db: Session, codigo: str, plugin, cliente_id: int, price: Decimal):
    """For a purchase: locks the coupon and returns (coupon, discount)."""
    coupon = db.scalar(select(LabsCupomModel).where(LabsCupomModel.codigo == codigo.strip().upper())
                       .with_for_update())
    _checar(db, coupon, plugin, cliente_id)
    return coupon, _desconto(coupon, price)


def registrar_uso(db: Session, coupon, *, cliente_id, plugin_id, desconto, moeda, licenca_id=None,
                  orcamento_id=None, pedido_stripe_id=None):
    use = LabsCupomUsoModel(cupom_id=coupon.id, cliente_id=cliente_id, plugin_id=plugin_id, licenca_id=licenca_id,
                            orcamento_id=orcamento_id, pedido_stripe_id=pedido_stripe_id, moeda=moeda,
                            desconto=desconto)
    db.add(use)
    db.flush()
    return use


def uso_do_orcamento(db: Session, orcamento_id: int):
    return db.scalar(select(LabsCupomUsoModel).where(LabsCupomUsoModel.orcamento_id == orcamento_id))


def desconto_do_orcamento(db: Session, orcamento_id: int) -> Decimal:
    use = uso_do_orcamento(db, orcamento_id)
    return Decimal(str(use.desconto)) if use is not None else Decimal(0)


def validar_cupom_publico(db: Session, codigo: str, slug: str):
    from services import plugin_service

    plugin = plugin_service._publicado(db, slug.strip().lower())
    price = plugin_service.preco_vigente(plugin)
    coupon = db.scalar(select(LabsCupomModel).where(LabsCupomModel.codigo == codigo.strip().upper()))
    try:
        if price <= 0:
            raise HTTPException(409, "Cupom não vale para este plugin.")
        _checar(db, coupon, plugin)
    except HTTPException as error:
        return {"valido": False, "motivo": error.detail}
    discount = _desconto(coupon, price)
    return {"valido": True, "codigo": coupon.codigo, "tipo": coupon.tipo, "valor": _money(coupon.valor),
            "preco": _money(price), "desconto": _money(discount), "preco_final": _money(price - discount)}


# ---------------------------------------------------------------- store content


BANNER_DEFAULT = {"ativo": False, "texto": None, "texto_en": None, "link": None}


def _bloco(db, chave, default):
    row = db.get(LabsConteudoModel, chave)
    return {**default, **(row.dados_json or {})} if row is not None else dict(default)


def conteudo(db: Session):
    return {"banner": _bloco(db, "banner", BANNER_DEFAULT)}


def salvar_banner(db: Session, payload, actor):
    row = db.get(LabsConteudoModel, "banner")
    data = payload.model_dump()
    if row is None:
        db.add(LabsConteudoModel(chave="banner", dados_json=data))
    else:
        row.dados_json = data
    audit_service.record(db, actor=actor, action="labs.banner_updated", entity_type="labs_conteudo",
                         entity_id="banner", metadata={"ativo": data["ativo"]})
    db.commit()
    return conteudo(db)


def conteudo_publico(db: Session):
    banner = _bloco(db, "banner", BANNER_DEFAULT)
    return {"banner": {key: banner[key] for key in ("texto", "texto_en", "link")} if banner.get("ativo") else None}


def ordenar(db: Session, payload, actor):
    plugins = {plugin.id: plugin for plugin in db.scalars(select(PluginModel).with_for_update())}
    if set(payload.ids) - set(plugins):
        raise HTTPException(404, "Plugin não encontrado.")
    for index, plugin_id in enumerate(dict.fromkeys(payload.ids)):
        plugins[plugin_id].ordem = min(index * 10, 9999)
    featured = set(payload.destaques)
    for plugin in plugins.values():
        plugin.destaque = plugin.id in featured
    audit_service.record(db, actor=actor, action="labs.store_order_updated", entity_type="plugin",
                         entity_id=None, metadata={"ids": payload.ids[:50], "destaques": sorted(featured)[:50]})
    db.commit()
    from services import plugin_service

    return plugin_service.admin_lista(db)
