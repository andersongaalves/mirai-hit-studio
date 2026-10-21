import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from models import AudioTagModel, BeatLicencaModel, BeatModel
from models.enums.financeiro import CobrancaStatus
from schemas.beat import BeatCreate
from services import audio_tag_service, audit_service
from services.producao_arquivo_storage import (
    ProducaoArquivoStorageError,
    new_production_file_storage,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

MAX_BEAT_BYTES = 50 * 1024 * 1024
BEAT_MIMES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/flac"}


def price_details(db, model, kind):
    from services import promocao_service

    base = model.preco_exclusivo if kind == "exclusivo" else model.preco_lease
    if base is None:
        return None
    target = SimpleNamespace(
        valor_base=base, promocao=None, aplica_desconto=model.aplica_desconto
    )
    return promocao_service.preco(target, promocao_service.desconto_global(db))


def price(db, model, kind):
    details = price_details(db, model, kind)
    return details["preco_vigente"] if details else None


def _response(db, model, *, exclusive_available=True):
    return {
        "id": model.id,
        "produtor_id": model.produtor_id,
        "produtor": model.produtor.nome_exibicao or model.produtor.username,
        "titulo": model.titulo,
        "descricao": model.descricao,
        "bpm": model.bpm,
        "tonalidade": model.tonalidade,
        "generos": model.generos,
        "preco_lease": price(db, model, "lease"),
        "preco_exclusivo": price(db, model, "exclusivo")
        if exclusive_available
        else None,
        "status": model.status,
        "ativo": model.ativo,
        "motivo_rejeicao": model.motivo_rejeicao,
        "created_at": model.created_at,
    }


def _tag(db, producer_id):
    own = audio_tag_service.perfil(db, f"producer:{producer_id}")
    studio = audio_tag_service.perfil(db, "studio")
    profile = own if own and own.tag_id else studio
    tag = db.get(AudioTagModel, profile.tag_id) if profile and profile.tag_id else None
    if tag is None:
        raise HTTPException(
            409, "Cadastre uma tag pessoal ou a tag padrao antes de enviar beats."
        )
    return tag, studio or profile


def create(db: Session, *, actor, payload: BeatCreate, data: bytes, mime_type: str):
    if not actor.painel_beats:
        raise HTTPException(403, "Painel de beats nao habilitado para esta conta.")
    if mime_type not in BEAT_MIMES or not data or len(data) > MAX_BEAT_BYTES:
        raise HTTPException(422, "Envie um audio valido de ate 50 MB.")
    audio_tag_service.duracao(data, limite=1800)
    tag, profile = _tag(db, actor.id)
    preview = audio_tag_service.mixar(
        data, tag.conteudo, profile.intervalo_segundos, profile.volume_percentual
    )
    storage = new_production_file_storage("previa")
    original_ref = preview_ref = None
    try:
        original_ref = storage.save(data, mime_type)
        preview_ref = storage.save(preview, "audio/mpeg")
        model = BeatModel(
            produtor_id=actor.id,
            **payload.model_dump(),
            status="revisao",
            original_ref=original_ref,
            original_sha256=hashlib.sha256(data).hexdigest(),
            preview_ref=preview_ref,
            preview_sha256=hashlib.sha256(preview).hexdigest(),
            tamanho_bytes=len(data),
            mime_type=mime_type,
        )
        db.add(model)
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action="beat.submitted",
            entity_type="beat",
            entity_id=model.id,
        )
        db.commit()
        db.refresh(model)
        return _response(db, model)
    except Exception:
        db.rollback()
        for reference in (preview_ref, original_ref):
            if reference:
                try:
                    storage.delete(reference)
                except ProducaoArquivoStorageError:
                    pass
        raise


def producer_list(db, actor):
    if not actor.painel_beats:
        raise HTTPException(403, "Painel de beats nao habilitado para esta conta.")
    return [
        _response(db, row)
        for row in db.scalars(
            select(BeatModel)
            .where(BeatModel.produtor_id == actor.id)
            .order_by(BeatModel.created_at.desc())
        ).all()
    ]


def admin_list(db):
    return [
        _response(db, row)
        for row in db.scalars(
            select(BeatModel).order_by(BeatModel.created_at.desc())
        ).all()
    ]


def client_list(db):
    query = (
        select(BeatModel)
        .where(BeatModel.status == "aprovado", BeatModel.ativo.is_(True))
        .order_by(BeatModel.created_at.desc())
    )
    result = []
    for row in db.scalars(query).all():
        active = db.scalars(
            select(BeatLicencaModel.tipo).where(
                BeatLicencaModel.beat_id == row.id,
                BeatLicencaModel.status == "reservada",
            )
        ).all()
        if "exclusivo" in active:
            continue
        result.append(_response(db, row, exclusive_available=not active))
    return result


def review(db, beat_id, payload, actor):
    model = db.scalar(
        select(BeatModel).where(BeatModel.id == beat_id).with_for_update()
    )
    if model is None:
        raise HTTPException(404, "Beat nao encontrado.")
    if model.status == "vendido":
        raise HTTPException(409, "Beat vendido nao pode ser revisado.")
    if payload.decisao == "rejeitar" and not payload.motivo.strip():
        raise HTTPException(422, "Informe o motivo da rejeicao.")
    model.status = "aprovado" if payload.decisao == "aprovar" else "rejeitado"
    model.motivo_rejeicao = (
        None if payload.decisao == "aprovar" else payload.motivo.strip()
    )
    model.revisado_por_id = actor.id
    model.revisado_em = datetime.now(timezone.utc)
    audit_service.record(
        db,
        actor=actor,
        action=f"beat.{model.status}",
        entity_type="beat",
        entity_id=model.id,
    )
    db.commit()
    db.refresh(model)
    return _response(db, model)


def preview(db, beat_id, actor):
    model = db.get(BeatModel, beat_id)
    if model is None:
        raise HTTPException(404, "Beat nao encontrado.")
    allowed = (
        actor.role == "admin"
        or (actor.role == "produtor" and model.produtor_id == actor.id)
        or (actor.role == "cliente" and model.status == "aprovado" and model.ativo)
    )
    if not allowed:
        raise HTTPException(404, "Beat nao encontrado.")
    data = new_production_file_storage("previa").read(model.preview_ref)
    if hashlib.sha256(data).hexdigest() != model.preview_sha256:
        raise HTTPException(409, "Integridade do preview invalida.")
    return data


def request_license(db, beat_id, kind, actor, idempotency_key):
    from models import OrcamentoModel
    from services import proposta_service

    beat = db.scalar(select(BeatModel).where(BeatModel.id == beat_id).with_for_update())
    if beat is None or beat.status != "aprovado" or not beat.ativo:
        raise HTTPException(404, "Beat nao encontrado.")
    current_price = price(db, beat, kind)
    if current_price is None:
        raise HTTPException(409, "Licenca indisponivel para este beat.")
    active_query = select(BeatLicencaModel.id).where(
        BeatLicencaModel.beat_id == beat.id,
        BeatLicencaModel.status == "reservada",
    )
    if kind == "lease":
        active_query = active_query.where(BeatLicencaModel.tipo == "exclusivo")
    active = db.scalar(active_query)
    if active:
        raise HTTPException(
            409, "Este beat possui uma licenca incompatível em andamento."
        )
    client = actor.cliente
    if client is None or not client.ativo or not client.email:
        raise HTTPException(
            409, "Cadastro do cliente incompleto para solicitar uma proposta."
        )
    fingerprint = hashlib.sha256(
        json.dumps(
            {"user": actor.id, "beat": beat.id, "license": kind}, sort_keys=True
        ).encode()
    ).hexdigest()
    existing = db.scalar(
        select(OrcamentoModel).where(OrcamentoModel.idempotency_key == idempotency_key)
    )
    if existing:
        if existing.request_hash != fingerprint:
            raise HTTPException(409, "Chave de repeticao usada para outra solicitacao.")
        return proposta_service.criar_por_orcamento(db, existing.id)
    budget = OrcamentoModel(
        idempotency_key=idempotency_key,
        request_hash=fingerprint,
        nome_cliente=client.nome,
        email=client.email or "",
        whatsapp=client.telefone,
        servico=f"Beat {beat.titulo} - {kind}",
        valor_total=float(current_price),
        detalhes=f"Solicitacao de licenca {kind} pelo catalogo interno.",
        cliente_id=client.id,
        is_test=bool(client.is_test),
        beat_id=beat.id,
        licenca_beat=kind,
    )
    db.add(budget)
    try:
        db.commit()
        db.refresh(budget)
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(OrcamentoModel).where(
                OrcamentoModel.idempotency_key == idempotency_key
            )
        )
        if existing is None or existing.request_hash != fingerprint:
            raise HTTPException(
                409, "Solicitacao concorrente; recarregue o catalogo."
            ) from None
        budget = existing
    return proposta_service.criar_por_orcamento(db, budget.id)


def reserve_for_proposal(db, proposta, cliente_id):
    for item in proposta.itens_json or []:
        beat_id, kind = item.get("beat_id"), item.get("licenca_beat")
        if not beat_id:
            continue
        beat = db.scalar(
            select(BeatModel).where(BeatModel.id == beat_id).with_for_update()
        )
        if beat is None or beat.status != "aprovado" or not beat.ativo:
            raise HTTPException(409, "Beat indisponivel para esta proposta.")
        existing = db.scalar(
            select(BeatLicencaModel).where(
                BeatLicencaModel.proposta_id == proposta.id,
                BeatLicencaModel.beat_id == beat_id,
                BeatLicencaModel.tipo == kind,
            )
        )
        if existing:
            continue
        active = select(BeatLicencaModel.id).where(
            BeatLicencaModel.beat_id == beat_id,
            BeatLicencaModel.status == "reservada",
        )
        if kind == "lease":
            active = active.where(BeatLicencaModel.tipo == "exclusivo")
        conflict = db.scalar(active.with_for_update())
        if conflict:
            raise HTTPException(
                409, "Este beat possui uma licenca incompatível em andamento."
            )
        current_price = price(db, beat, kind)
        if current_price is None or Decimal(str(item["valor_unitario"])) != Decimal(
            str(current_price)
        ):
            raise HTTPException(409, "O preco do beat mudou; revise a proposta.")
        db.add(
            BeatLicencaModel(
                beat_id=beat.id,
                proposta_id=proposta.id,
                cliente_id=cliente_id,
                tipo=kind,
                valor=current_price,
            )
        )
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "O beat foi reservado por outra proposta.") from None


def confirm_paid(db, cobranca):
    if cobranca.status != CobrancaStatus.PAGA.value:
        return
    licenses = db.scalars(
        select(BeatLicencaModel)
        .where(
            BeatLicencaModel.proposta_id == cobranca.proposta_id,
            BeatLicencaModel.status == "reservada",
        )
        .with_for_update()
    ).all()
    now = datetime.now(timezone.utc)
    for license in licenses:
        beat = db.scalar(
            select(BeatModel).where(BeatModel.id == license.beat_id).with_for_update()
        )
        license.status = "adquirida"
        license.adquirida_em = now
        if license.tipo == "exclusivo":
            beat.status = "vendido"
            beat.ativo = False
