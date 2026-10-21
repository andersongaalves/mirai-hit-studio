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
from services.storage.contracts import StorageScope, StorageValidationError
from services.storage.policies import DEFAULT_POLICIES
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

MAX_BEAT_BYTES = 50 * 1024 * 1024
ARCHIVE_MIMES = {"application/zip", "application/vnd.rar"}


def _validate_files(payload, mp3, wav, archive, *, has_wav=False, has_archive=False):
    policy = DEFAULT_POLICIES[StorageScope.PRODUCTION_TEMP]
    for item, allowed in ((mp3, {"audio/mpeg"}), (wav, {"audio/wav", "audio/x-wav"}), (archive, ARCHIVE_MIMES)):
        if item is None:
            continue
        data, mime = item
        if mime not in allowed or len(data) > MAX_BEAT_BYTES:
            raise HTTPException(422, "Formato ou tamanho de arquivo invalido.")
        try:
            policy.validate(data, mime)
        except StorageValidationError:
            raise HTTPException(422, "Conteudo do arquivo invalido.") from None
    if payload.preco_wav is not None and wav is None and not has_wav:
        raise HTTPException(422, "Envie o WAV para definir o preco WAV.")
    if payload.preco_multitrack is not None and archive is None and not has_archive:
        raise HTTPException(422, "Envie o multitrack para definir seu preco.")
    if mp3 is not None:
        audio_tag_service.duracao(mp3[0], limite=1800)


def price_details(db, model, kind):
    from services import promocao_service

    bases = {
        "lease": model.preco_lease if model.mp3_ref is None else None,
        "lease_mp3": model.preco_lease if model.mp3_ref else None,
        "lease_wav": model.preco_wav if model.wav_ref else None,
        "multitrack": model.preco_multitrack if model.multitrack_ref else None,
        "exclusivo": model.preco_exclusivo,
    }
    base = bases.get(kind)
    if base is None:
        return None
    target = SimpleNamespace(
        valor_base=base, promocao=None, aplica_desconto=model.aplica_desconto
    )
    return promocao_service.preco(target, promocao_service.desconto_global(db))


def price(db, model, kind):
    details = price_details(db, model, kind)
    return details["preco_vigente"] if details else None


def _response(db, model, *, exclusive_available=True, include_base=False):
    result = {
        "id": model.id,
        "produtor_id": model.produtor_id,
        "produtor": model.produtor.nome_exibicao or model.produtor.username,
        "titulo": model.titulo,
        "descricao": model.descricao,
        "bpm": model.bpm,
        "tonalidade": model.tonalidade,
        "generos": model.generos,
        "preco_lease": price(db, model, "lease_mp3" if model.mp3_ref else "lease"),
        "preco_wav": price(db, model, "lease_wav"),
        "preco_multitrack": price(db, model, "multitrack"),
        "preco_exclusivo": price(db, model, "exclusivo")
        if exclusive_available
        else None,
        "status": model.status,
        "ativo": model.ativo,
        "motivo_rejeicao": model.motivo_rejeicao,
        "created_at": model.created_at,
        "formato_novo": bool(model.mp3_ref),
        "tem_wav": bool(model.wav_ref),
        "tem_multitrack": bool(model.multitrack_ref),
    }
    if include_base:
        result.update({
            "preco_lease_base": model.preco_lease,
            "preco_wav_base": model.preco_wav,
            "preco_multitrack_base": model.preco_multitrack,
            "preco_exclusivo_base": model.preco_exclusivo,
        })
    return result


def _tag(db, producer_id):
    own = audio_tag_service.perfil(db, f"producer:{producer_id}")
    studio = audio_tag_service.perfil(db, "studio")
    profile = own if own and own.tag_id else studio
    tag = db.get(AudioTagModel, profile.tag_id) if profile and profile.tag_id else None
    if tag is None:
        raise HTTPException(409, "Cadastre uma tag pessoal ou a tag padrao antes de enviar beats.")
    return tag, profile


def create(db: Session, *, actor, payload: BeatCreate, mp3, wav=None, archive=None):
    if not actor.painel_beats:
        raise HTTPException(403, "Painel de beats nao habilitado para esta conta.")
    _validate_files(payload, mp3, wav, archive)
    tag, profile = _tag(db, actor.id)
    tagged_mp3 = audio_tag_service.mixar(
        mp3[0], tag.conteudo, profile.intervalo_segundos, profile.volume_percentual
    )
    storage = new_production_file_storage("previa")
    saved = []
    try:
        original_ref = storage.save(*mp3)
        saved.append(original_ref)
        mp3_ref = storage.save(tagged_mp3, "audio/mpeg")
        saved.append(mp3_ref)
        wav_ref = storage.save(*wav) if wav else None
        if wav_ref:
            saved.append(wav_ref)
        archive_ref = storage.save(*archive) if archive else None
        if archive_ref:
            saved.append(archive_ref)
        model = BeatModel(
            produtor_id=actor.id,
            **payload.model_dump(),
            status="revisao",
            original_ref=original_ref,
            original_sha256=hashlib.sha256(mp3[0]).hexdigest(),
            preview_ref=mp3_ref,
            preview_sha256=hashlib.sha256(tagged_mp3).hexdigest(),
            mp3_ref=mp3_ref,
            wav_ref=wav_ref,
            wav_sha256=hashlib.sha256(wav[0]).hexdigest() if wav else None,
            multitrack_ref=archive_ref,
            multitrack_sha256=hashlib.sha256(archive[0]).hexdigest() if archive else None,
            multitrack_mime=archive[1] if archive else None,
            tamanho_bytes=len(mp3[0]),
            mime_type="audio/mpeg",
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
        return _response(db, model, include_base=True)
    except Exception:
        db.rollback()
        for reference in saved:
            try:
                storage.delete(reference)
            except ProducaoArquivoStorageError:
                pass
        raise


def producer_list(db, actor):
    if not actor.painel_beats:
        raise HTTPException(403, "Painel de beats nao habilitado para esta conta.")
    return [
        _response(db, row, include_base=True)
        for row in db.scalars(
            select(BeatModel)
            .where(BeatModel.produtor_id == actor.id)
            .order_by(BeatModel.created_at.desc())
        ).all()
    ]


def admin_list(db):
    return [
        _response(db, row, include_base=True)
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


def edit(db, beat_id, payload, actor, *, mp3=None, wav=None, archive=None):
    model = db.scalar(select(BeatModel).where(BeatModel.id == beat_id).with_for_update())
    if model is None:
        raise HTTPException(404, "Beat nao encontrado.")
    if model.status == "vendido" or db.scalar(select(BeatLicencaModel.id).where(
        BeatLicencaModel.beat_id == beat_id, BeatLicencaModel.status.in_(("reservada", "adquirida"))
    )):
        raise HTTPException(409, "Beat com licenca ativa nao pode ser alterado.")
    _validate_files(payload, mp3, wav, archive, has_wav=bool(model.wav_ref),
                    has_archive=bool(model.multitrack_ref))
    tagged_mp3 = None
    if mp3 is not None:
        tag, profile = _tag(db, model.produtor_id)
        tagged_mp3 = audio_tag_service.mixar(
            mp3[0], tag.conteudo, profile.intervalo_segundos, profile.volume_percentual
        )
    storage = new_production_file_storage("previa")
    saved, old = [], []
    try:
        if mp3 is not None:
            original_ref = storage.save(*mp3)
            saved.append(original_ref)
            old.append(model.original_ref)
            model.original_ref = original_ref
            model.original_sha256 = hashlib.sha256(mp3[0]).hexdigest()
        for item, reference, digest, mime in (
            ((tagged_mp3, "audio/mpeg") if tagged_mp3 is not None else None, "mp3_ref", "preview_sha256", "audio/mpeg"),
            (wav, "wav_ref", "wav_sha256", "audio/wav"),
            (archive, "multitrack_ref", "multitrack_sha256", None),
        ):
            if item is None:
                continue
            new_ref = storage.save(*item)
            saved.append(new_ref)
            if getattr(model, reference):
                old.append(getattr(model, reference))
            elif reference == "mp3_ref":
                old.append(model.preview_ref)
            setattr(model, reference, new_ref)
            setattr(model, digest, hashlib.sha256(item[0]).hexdigest())
            if reference == "mp3_ref":
                model.preview_ref = new_ref
                model.tamanho_bytes = len(mp3[0])
            elif reference == "multitrack_ref":
                model.multitrack_mime = item[1]
        for key, value in payload.model_dump().items():
            setattr(model, key, value)
        model.status = "revisao"
        model.motivo_rejeicao = None
        model.revisado_por_id = None
        model.revisado_em = None
        audit_service.record(db, actor=actor, action="beat.edited", entity_type="beat", entity_id=beat_id)
        db.commit()
        db.refresh(model)
    except Exception:
        db.rollback()
        for reference in saved:
            try:
                storage.delete(reference)
            except ProducaoArquivoStorageError:
                pass
        raise
    for reference in set(old) - set(saved):
        try:
            storage.delete(reference)
        except ProducaoArquivoStorageError:
            pass
    return _response(db, model, include_base=True)


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
    if kind != "exclusivo":
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
        if kind != "exclusivo":
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
