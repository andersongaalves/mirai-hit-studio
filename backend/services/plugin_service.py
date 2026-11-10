"""Mirai Hit Labs: plugin catalog, purchases, licenses and installer downloads.

A paid plugin is bought like a catalog beat: one budget with ``plugin_id``, a proposal
paid in full (``finalidade='plugins'``) and the studio's checkout. The payment turns the
reserved license into an active one; no production is created. A free plugin is granted
straight away. Installers are .zip files in private storage (signed links) or links.
"""
import hashlib
import json
import logging
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from models import ClienteModel, OrcamentoModel, PluginArquivoModel, PluginLicencaModel, PluginModel
from models.enums.financeiro import CobrancaStatus
from services import audit_service
from services.producao_arquivo_storage import (
    ProducaoArquivoIntegridadeError,
    ProducaoArquivoStorageError,
    new_production_file_storage,
)
from services.storage.contracts import StorageError, StorageScope
from services.storage.registry import storage_for
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

logger = logging.getLogger(__name__)

SISTEMAS = {"windows": "Windows", "macos": "macOS"}
INSTALLER_MAX_BYTES = 150 * 1024 * 1024
COVER_MAX_BYTES = 8 * 1024 * 1024
KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now():
    return datetime.now(timezone.utc)


def _money(value):
    return f"{Decimal(str(value or 0)).quantize(Decimal('0.01'))}"


def preco_vigente(plugin) -> Decimal:
    if plugin.preco_promocional is not None:
        return Decimal(str(plugin.preco_promocional))
    return Decimal(str(plugin.preco or 0))


def nova_chave() -> str:
    raw = "".join(secrets.choice(KEY_ALPHABET) for _ in range(16))
    return "MHL-" + "-".join(raw[index:index + 4] for index in range(0, 16, 4))


def _sistemas(plugin):
    return [
        {"sistema": item.sistema, "nome": SISTEMAS[item.sistema], "versao": item.versao or plugin.versao,
         "tamanho_bytes": item.tamanho_bytes, "tipo": "link" if item.link_externo else "arquivo"}
        for item in sorted(plugin.arquivos, key=lambda row: list(SISTEMAS).index(row.sistema))
    ]


def _publico(plugin):
    preco = Decimal(str(plugin.preco or 0))
    vigente = preco_vigente(plugin)
    return {
        "slug": plugin.slug,
        "nome": plugin.nome,
        "tagline": plugin.tagline,
        "descricao": plugin.descricao,
        "categoria": plugin.categoria,
        "versao": plugin.versao,
        "formatos": list(plugin.formatos_json or []),
        "recursos": list(plugin.recursos_json or []),
        "requisitos": plugin.requisitos,
        "preco": _money(preco),
        "preco_vigente": _money(vigente),
        "em_promocao": plugin.preco_promocional is not None,
        "gratuito": vigente == 0,
        "capa_url": plugin.capa_url,
        "video_url": plugin.video_url,
        "destaque": bool(plugin.destaque),
        "sistemas": _sistemas(plugin),
        "publicado_em": plugin.publicado_em.isoformat() if plugin.publicado_em else None,
    }


def _admin(db, plugin):
    counts = dict(db.execute(
        select(PluginLicencaModel.status, func.count())
        .where(PluginLicencaModel.plugin_id == plugin.id)
        .group_by(PluginLicencaModel.status)
    ).all())
    return {
        **_publico(plugin),
        "id": plugin.id,
        "status": plugin.status,
        "ordem": plugin.ordem,
        "preco_promocional": _money(plugin.preco_promocional) if plugin.preco_promocional is not None else None,
        "instaladores": [
            {**info, "nome_arquivo": row.nome_arquivo, "link": row.link_externo,
             "atualizado_em": row.updated_at.isoformat() if row.updated_at else None}
            for info, row in zip(_sistemas(plugin), sorted(plugin.arquivos, key=lambda row: list(SISTEMAS).index(row.sistema)))
        ],
        "licencas": {"ativas": counts.get("ativa", 0), "reservadas": counts.get("reservada", 0),
                     "revogadas": counts.get("revogada", 0) + counts.get("cancelada", 0)},
    }


def _query():
    return select(PluginModel).options(selectinload(PluginModel.arquivos))


# ---------------------------------------------------------------- public catalog


def publico_lista(db: Session):
    plugins = db.scalars(
        _query().where(PluginModel.status == "publicado")
        .order_by(PluginModel.destaque.desc(), PluginModel.ordem, PluginModel.nome)
    ).all()
    return [_publico(plugin) for plugin in plugins]


def _publicado(db, slug):
    plugin = db.scalar(_query().where(PluginModel.slug == slug, PluginModel.status == "publicado"))
    if plugin is None:
        raise HTTPException(404, "Plugin não encontrado.")
    return plugin


def publico_detalhe(db: Session, slug: str):
    return _publico(_publicado(db, slug))


# ---------------------------------------------------------------- admin


def admin_lista(db: Session):
    plugins = db.scalars(_query().order_by(PluginModel.ordem, PluginModel.nome)).all()
    return [_admin(db, plugin) for plugin in plugins]


def _obter(db, plugin_id, lock=False):
    query = _query().where(PluginModel.id == plugin_id)
    if lock:
        query = query.with_for_update()
    plugin = db.scalar(query)
    if plugin is None:
        raise HTTPException(404, "Plugin não encontrado.")
    return plugin


def admin_obter(db: Session, plugin_id: int):
    return _admin(db, _obter(db, plugin_id))


def _aplicar(plugin, payload):
    data = payload.model_dump()
    plugin.nome = data["nome"]
    plugin.slug = data["slug"]
    plugin.tagline = data["tagline"]
    plugin.descricao = data["descricao"]
    plugin.categoria = data["categoria"]
    plugin.versao = data["versao"]
    plugin.formatos_json = data["formatos"]
    plugin.recursos_json = data["recursos"]
    plugin.requisitos = data["requisitos"]
    plugin.preco = data["preco"]
    plugin.preco_promocional = data["preco_promocional"]
    plugin.video_url = data["video_url"]
    plugin.destaque = data["destaque"]
    plugin.ordem = data["ordem"]
    if data["status"] == "publicado" and plugin.status != "publicado":
        plugin.publicado_em = plugin.publicado_em or _now()
    plugin.status = data["status"]


def _salvar(db, plugin, actor, action):
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe um plugin com este endereço.") from None
    audit_service.record(db, actor=actor, action=action, entity_type="plugin", entity_id=plugin.id,
                         metadata={"status": plugin.status, "slug": plugin.slug})
    db.commit()
    db.refresh(plugin)
    return _admin(db, plugin)


def criar(db: Session, payload, actor):
    plugin = PluginModel()
    _aplicar(plugin, payload)
    if plugin.status == "publicado":
        raise HTTPException(409, "Salve o plugin e envie a capa e um instalador antes de publicar.")
    db.add(plugin)
    return _salvar(db, plugin, actor, "plugin.created")


def editar(db: Session, plugin_id: int, payload, actor):
    plugin = _obter(db, plugin_id, lock=True)
    _aplicar(plugin, payload)
    if plugin.status == "publicado" and (not plugin.capa_url or not plugin.arquivos):
        raise HTTPException(409, "Para publicar, o plugin precisa de capa e de pelo menos um instalador.")
    return _salvar(db, plugin, actor, "plugin.updated")


def enviar_capa(db: Session, plugin_id: int, data: bytes, mime: str, actor):
    plugin = _obter(db, plugin_id, lock=True)
    storage = storage_for(StorageScope.PUBLIC_IMAGE)
    try:
        saved = storage.save(data, mime)
    except StorageError as error:
        raise HTTPException(422, str(error)) from None
    old = plugin.capa_ref
    plugin.capa_ref = str(saved.reference)
    plugin.capa_url = saved.public_url or storage.get_public_url(saved.reference)
    result = _salvar(db, plugin, actor, "plugin.cover_updated")
    if old:
        try:
            storage.delete(old)
        except StorageError:
            logger.warning("plugin_cover_cleanup_failed")
    return result


def _download_name(plugin, sistema, version):
    plain = unicodedata.normalize("NFKD", plugin.nome or "").encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", plain).strip("-") or plugin.slug
    suffix = f"-{version}" if version else ""
    return f"{slug}{suffix}-{SISTEMAS[sistema].replace(' ', '')}.zip"[:160]


def _instalador(db, plugin, sistema):
    if sistema not in SISTEMAS:
        raise HTTPException(422, "Sistema inválido.")
    row = next((item for item in plugin.arquivos if item.sistema == sistema), None)
    if row is None:
        row = PluginArquivoModel(plugin_id=plugin.id, sistema=sistema)
        plugin.arquivos.append(row)
    return row


def _apagar_arquivo(reference):
    if not reference:
        return
    try:
        new_production_file_storage("previa").delete(reference)
    except ProducaoArquivoStorageError:
        logger.warning("plugin_installer_cleanup_failed")


def enviar_instalador(db: Session, plugin_id: int, sistema: str, data: bytes, versao, actor):
    plugin = _obter(db, plugin_id, lock=True)
    if len(data) > INSTALLER_MAX_BYTES:
        raise HTTPException(413, "O instalador passa de 150 MB; use um link.")
    storage = new_production_file_storage("previa")
    try:
        reference = storage.save(data, "application/zip")
    except ProducaoArquivoStorageError as error:
        raise HTTPException(422, f"Não foi possível guardar o instalador: {error}") from None
    row = _instalador(db, plugin, sistema)
    old = row.arquivo_ref
    row.arquivo_ref = reference
    row.sha256 = hashlib.sha256(data).hexdigest()
    row.mime = "application/zip"
    row.tamanho_bytes = len(data)
    row.link_externo = None
    row.versao = (versao or "").strip()[:20] or plugin.versao
    row.nome_arquivo = _download_name(plugin, sistema, row.versao)
    try:
        result = _salvar(db, plugin, actor, "plugin.installer_updated")
    except Exception:
        _apagar_arquivo(reference)
        raise
    _apagar_arquivo(old)
    return result


def definir_link(db: Session, plugin_id: int, sistema: str, payload, actor):
    plugin = _obter(db, plugin_id, lock=True)
    row = _instalador(db, plugin, sistema)
    old = row.arquivo_ref
    row.arquivo_ref = None
    row.sha256 = None
    row.mime = None
    row.tamanho_bytes = None
    row.nome_arquivo = None
    row.link_externo = payload.link
    row.versao = payload.versao or plugin.versao
    result = _salvar(db, plugin, actor, "plugin.installer_updated")
    _apagar_arquivo(old)
    return result


def remover_instalador(db: Session, plugin_id: int, sistema: str, actor):
    plugin = _obter(db, plugin_id, lock=True)
    row = next((item for item in plugin.arquivos if item.sistema == sistema), None)
    if row is None:
        raise HTTPException(404, "Instalador não encontrado.")
    if plugin.status == "publicado" and len(plugin.arquivos) == 1:
        raise HTTPException(409, "Um plugin publicado precisa de pelo menos um instalador.")
    old = row.arquivo_ref
    plugin.arquivos.remove(row)
    result = _salvar(db, plugin, actor, "plugin.installer_removed")
    _apagar_arquivo(old)
    return result


def licencas(db: Session, plugin_id: int):
    _obter(db, plugin_id)
    rows = db.execute(
        select(PluginLicencaModel, ClienteModel)
        .join(ClienteModel, ClienteModel.id == PluginLicencaModel.cliente_id)
        .where(PluginLicencaModel.plugin_id == plugin_id)
        .order_by(PluginLicencaModel.id.desc())
    ).all()
    return [
        {"id": license.id, "cliente_id": client.id, "cliente": client.nome, "email": client.email,
         "origem": license.origem, "status": license.status, "chave": license.chave,
         "valor": _money(license.valor), "proposta_id": license.proposta_id,
         "ativada_em": license.ativada_em.isoformat() if license.ativada_em else None,
         "encerrada_em": license.encerrada_em.isoformat() if license.encerrada_em else None,
         "motivo": license.motivo}
        for license, client in rows
    ]


def conceder_cortesia(db: Session, plugin_id: int, cliente_id: int, actor):
    plugin = _obter(db, plugin_id)
    client = db.get(ClienteModel, cliente_id)
    if client is None:
        raise HTTPException(404, "Cliente não encontrado.")
    if _licenca_ativa(db, plugin.id, client.id) is not None:
        raise HTTPException(409, "Este cliente já tem uma licença ativa deste plugin.")
    license = _conceder(db, plugin, client.id, "cortesia")
    audit_service.record(db, actor=actor, action="plugin.license_granted", entity_type="plugin_licenca",
                         entity_id=license.id, metadata={"plugin_id": plugin.id, "origem": "cortesia"})
    db.commit()
    return {"id": license.id, "status": license.status}


def revogar(db: Session, license_id: int, motivo: str, actor):
    license = db.scalar(select(PluginLicencaModel).where(PluginLicencaModel.id == license_id).with_for_update())
    if license is None:
        raise HTTPException(404, "Licença não encontrada.")
    if license.status not in ("ativa", "reservada"):
        raise HTTPException(409, "Esta licença já está encerrada.")
    license.status = "revogada"
    license.encerrada_em = _now()
    license.motivo = motivo
    audit_service.record(db, actor=actor, action="plugin.license_revoked", entity_type="plugin_licenca",
                         entity_id=license.id, metadata={"plugin_id": license.plugin_id})
    db.commit()
    return {"id": license.id, "status": license.status}


# ---------------------------------------------------------------- licenses


def _licenca_ativa(db, plugin_id, cliente_id):
    return db.scalar(select(PluginLicencaModel).where(
        PluginLicencaModel.plugin_id == plugin_id,
        PluginLicencaModel.cliente_id == cliente_id,
        PluginLicencaModel.status == "ativa",
    ).limit(1))


def _conceder(db, plugin, cliente_id, origem, *, proposta_id=None, valor=Decimal(0), status="ativa"):
    for _ in range(5):
        license = PluginLicencaModel(
            plugin_id=plugin.id, cliente_id=cliente_id, proposta_id=proposta_id, origem=origem,
            status=status, chave=nova_chave(), valor=valor,
            ativada_em=_now() if status == "ativa" else None,
        )
        try:
            with db.begin_nested():
                db.add(license)
                db.flush()
            return license
        except IntegrityError:
            if origem != "compra":
                # A previous free/courtesy license (revoked or ended) is reactivated.
                existing = db.scalar(select(PluginLicencaModel).where(
                    PluginLicencaModel.plugin_id == plugin.id,
                    PluginLicencaModel.cliente_id == cliente_id,
                    PluginLicencaModel.origem != "compra",
                ).with_for_update())
                if existing is not None:
                    existing.status, existing.origem = "ativa", origem
                    existing.ativada_em, existing.encerrada_em, existing.motivo = _now(), None, None
                    db.flush()
                    return existing
            continue
    raise HTTPException(409, "Não foi possível gerar a licença; tente de novo.")


def reserve_for_proposal(db: Session, proposta, cliente_id):
    """On acceptance: a reserved license per plugin line, activated by the payment."""
    for item in proposta.itens_json or []:
        plugin_id = (item or {}).get("plugin_id")
        if not plugin_id:
            continue
        plugin = db.scalar(select(PluginModel).where(PluginModel.id == plugin_id))
        if plugin is None or plugin.status != "publicado":
            raise HTTPException(409, "Plugin indisponível para esta compra.")
        exists = db.scalar(select(PluginLicencaModel.id).where(
            PluginLicencaModel.proposta_id == proposta.id, PluginLicencaModel.plugin_id == plugin.id))
        if exists:
            continue
        if Decimal(str(item["valor_unitario"])) != preco_vigente(plugin):
            raise HTTPException(409, "O preço do plugin mudou; refaça a compra.")
        _conceder(db, plugin, cliente_id, "compra", proposta_id=proposta.id,
                  valor=preco_vigente(plugin), status="reservada")


def confirm_paid(db: Session, cobranca):
    """Keep plugin licenses in step with the charge (called on every payment change)."""
    now = _now()
    paid = cobranca.status == CobrancaStatus.PAGA.value
    licenses = db.scalars(
        select(PluginLicencaModel)
        .where(PluginLicencaModel.proposta_id == cobranca.proposta_id)
        .with_for_update()
    ).all()
    for license in licenses:
        if paid and license.status == "reservada":
            license.status = "ativa"
            license.ativada_em = now
            audit_service.record(db, actor=None, action="plugin.license_activated",
                                 entity_type="plugin_licenca", entity_id=license.id,
                                 metadata={"plugin_id": license.plugin_id, "proposal_id": license.proposta_id})
        elif not paid and license.status == "ativa":
            # A refund or chargeback stops the license; a new payment can bring it back.
            license.status = "reservada"
            license.encerrada_em = now
            license.motivo = "pagamento_revertido"
            audit_service.record(db, actor=None, action="plugin.license_suspended",
                                 entity_type="plugin_licenca", entity_id=license.id,
                                 metadata={"plugin_id": license.plugin_id, "proposal_id": license.proposta_id})


def finalidade_plugins(proposta):
    return getattr(proposta, "finalidade", "producao") == "plugins"


def comprar(db: Session, slug: str, actor, idempotency_key: str, request_id=None):
    from services import proposta_comercial_service, proposta_service

    plugin = _publicado(db, slug)
    client = actor.cliente
    if client is None or not client.ativo or not client.email:
        raise HTTPException(409, "Complete seu cadastro antes de comprar.")
    if _licenca_ativa(db, plugin.id, client.id) is not None:
        raise HTTPException(409, "Você já tem este plugin. Baixe em Meus plugins.")
    price = preco_vigente(plugin)
    if price == 0:
        license = _conceder(db, plugin, client.id, "gratuito")
        audit_service.record(db, actor=actor, action="plugin.license_granted", entity_type="plugin_licenca",
                             entity_id=license.id, metadata={"plugin_id": plugin.id, "origem": "gratuito"},
                             request_id=request_id)
        db.commit()
        return {"gratuito": True, "licenca_id": license.id, "destino": "/cliente/plugins"}

    # A purchase already waiting for payment goes back to the same checkout.
    pending = db.scalar(select(PluginLicencaModel).where(
        PluginLicencaModel.plugin_id == plugin.id, PluginLicencaModel.cliente_id == client.id,
        PluginLicencaModel.status == "reservada", PluginLicencaModel.origem == "compra",
        PluginLicencaModel.valor == price, PluginLicencaModel.motivo.is_(None),
    ).order_by(PluginLicencaModel.id.desc()).limit(1))
    if pending is not None:
        from services import financial_service

        charge = financial_service.buscar_por_proposta(db, pending.proposta_id)
        if charge is not None and charge.status in (CobrancaStatus.PENDENTE.value,):
            db.commit()
            return {"gratuito": False, "proposta_id": pending.proposta_id,
                    "checkout_path": f"/checkout?proposta={pending.proposta_id}"}

    def accept(proposal_id):
        try:
            return proposta_comercial_service.aceitar_compra_catalogo(
                db, proposal_id, cliente_id=client.id, actor=actor, request_id=request_id)
        except proposta_service.PropostaNaoEncontrada as error:
            raise HTTPException(404, str(error)) from None
        except (proposta_service.PropostaConflito, proposta_service.PropostaInvalida) as error:
            raise HTTPException(409, str(error)) from None

    fingerprint = hashlib.sha256(json.dumps(
        {"user": actor.id, "plugin": plugin.id, "price": str(price)}, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(OrcamentoModel).where(OrcamentoModel.idempotency_key == idempotency_key))
    if existing is None:
        budget = OrcamentoModel(
            idempotency_key=idempotency_key, request_hash=fingerprint,
            nome_cliente=client.nome, email=client.email or "", whatsapp=client.telefone,
            servico=f"Plugin {plugin.nome}"[:100], valor_total=float(price),
            detalhes=f"Compra do plugin {plugin.nome} na Mirai Hit Labs (licença pessoal).",
            cliente_id=client.id, is_test=bool(client.is_test), plugin_id=plugin.id,
        )
        db.add(budget)
        try:
            db.commit()
            db.refresh(budget)
        except IntegrityError:
            db.rollback()
            budget = db.scalar(select(OrcamentoModel).where(OrcamentoModel.idempotency_key == idempotency_key))
            if budget is None:
                raise HTTPException(409, "Compra concorrente; recarregue a página.") from None
    else:
        budget = existing
    if budget.request_hash != fingerprint:
        raise HTTPException(409, "Chave de repetição usada para outra compra.")
    try:
        proposal = proposta_service.criar_por_orcamento(db, budget.id)
    except (proposta_service.PropostaConflito, proposta_service.PropostaInvalida) as error:
        raise HTTPException(409, str(error)) from None
    accepted = accept(proposal.id)
    return {"gratuito": False, "proposta_id": accepted.id, "checkout_path": f"/checkout?proposta={accepted.id}"}


def minhas_licencas(db: Session, actor):
    if actor.cliente_id is None:
        return []
    rows = db.execute(
        select(PluginLicencaModel, PluginModel)
        .join(PluginModel, PluginModel.id == PluginLicencaModel.plugin_id)
        .options(selectinload(PluginModel.arquivos))
        .where(PluginLicencaModel.cliente_id == actor.cliente_id,
               PluginLicencaModel.status.in_(("ativa", "reservada")))
        .order_by(PluginLicencaModel.status, PluginLicencaModel.id.desc())
    ).all()
    active, suspended, pending = {}, {}, {}
    for license, plugin in rows:
        if license.status == "ativa":
            active.setdefault(plugin.id, (license, plugin))
        elif license.motivo == "pagamento_revertido":
            suspended.setdefault(plugin.id, (license, plugin))
        else:
            pending.setdefault(plugin.id, (license, plugin))
    result = []
    for license, plugin in active.values():
        result.append({
            "id": license.id, "status": "ativa", "plugin": plugin.nome, "slug": plugin.slug,
            "capa_url": plugin.capa_url, "versao": plugin.versao, "formatos": list(plugin.formatos_json or []),
            "chave": license.chave, "origem": license.origem,
            "ativada_em": license.ativada_em.isoformat() if license.ativada_em else None,
            "sistemas": _sistemas(plugin),
        })
    for plugin_id, (license, plugin) in suspended.items():
        if plugin_id not in active:
            result.append({"id": license.id, "status": "suspensa", "plugin": plugin.nome, "slug": plugin.slug,
                           "capa_url": plugin.capa_url, "sistemas": []})
    for plugin_id, (license, plugin) in pending.items():
        if plugin_id not in active and plugin_id not in suspended:
            # A purchase still waiting for payment: the way back to its checkout.
            result.append({"id": license.id, "status": "aguardando_pagamento", "plugin": plugin.nome,
                           "slug": plugin.slug, "capa_url": plugin.capa_url, "sistemas": [],
                           "checkout_path": f"/checkout?proposta={license.proposta_id}"})
    return result


def download(db: Session, license_id: int, sistema: str, actor):
    if actor.cliente_id is None or sistema not in SISTEMAS:
        raise HTTPException(404, "Instalador não encontrado.")
    license = db.scalar(select(PluginLicencaModel).where(
        PluginLicencaModel.id == license_id, PluginLicencaModel.cliente_id == actor.cliente_id,
        PluginLicencaModel.status == "ativa"))
    if license is None:
        raise HTTPException(404, "Instalador não encontrado.")
    plugin = _obter(db, license.plugin_id)
    row = next((item for item in plugin.arquivos if item.sistema == sistema), None)
    if row is None:
        raise HTTPException(404, "Ainda não há instalador para este sistema.")
    audit_service.record(db, actor=actor, action="plugin.installer_downloaded", entity_type="plugin_licenca",
                         entity_id=license.id, metadata={"plugin_id": plugin.id, "sistema": sistema})
    db.commit()
    if row.link_externo:
        return {"type": "link", "url": row.link_externo}
    storage = new_production_file_storage("previa")
    filename = row.nome_arquivo or _download_name(plugin, sistema, row.versao)
    link = getattr(storage, "download_link", None)
    if link is not None:
        try:
            url = link(row.arquivo_ref, filename=filename, content_type="application/zip", sha256=row.sha256,
                       expires_seconds=300)
        except ProducaoArquivoIntegridadeError:
            raise HTTPException(409, "Integridade do instalador inválida; avise o estúdio.") from None
        except ProducaoArquivoStorageError:
            raise HTTPException(503, "Instalador temporariamente indisponível.") from None
        if url:
            return {"type": "download", "url": url, "filename": filename}
    try:
        contents = storage.read(row.arquivo_ref)
    except ProducaoArquivoStorageError:
        raise HTTPException(503, "Instalador temporariamente indisponível.") from None
    if hashlib.sha256(contents).hexdigest() != row.sha256:
        raise HTTPException(409, "Integridade do instalador inválida; avise o estúdio.")
    return {"type": "file", "contents": contents, "mime": "application/zip", "filename": filename}


def validar_chave(db: Session, chave: str, slug: str):
    """For the plugins themselves: is this key active for this plugin? No personal data."""
    license = db.scalar(
        select(PluginLicencaModel).join(PluginModel, PluginModel.id == PluginLicencaModel.plugin_id)
        .where(PluginLicencaModel.chave == chave.strip().upper(), PluginModel.slug == slug.strip().lower())
    )
    valid = license is not None and license.status == "ativa"
    return {"valida": valid, "plugin": slug.strip().lower(), "status": "ativa" if valid else "invalida"}
