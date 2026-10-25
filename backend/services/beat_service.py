import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urlsplit

from fastapi import HTTPException
from models import AudioTagModel, BeatLicencaModel, BeatModel
from models.enums.financeiro import CobrancaStatus, PagamentoStatus
from schemas.beat import BeatCreate
from services import audio_tag_service, audit_service, beat_upload_config_service
from services.producao_arquivo_storage import (
    ProducaoArquivoStorageError,
    new_production_file_storage,
)
from services.storage.contracts import (
    StorageError,
    StorageScope,
    StorageValidationError,
)
from services.storage.policies import DEFAULT_POLICIES
from services.storage.registry import storage_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

ARCHIVE_MIMES = {"application/zip", "application/vnd.rar"}
logger = logging.getLogger(__name__)
# A payment attempt started before the deadline keeps the reservation alive for
# this long, so a Pix generated at the last minute can still be paid.
PENDING_PAYMENT_GRACE = timedelta(hours=24)


def _external_multitrack_url(value):
    if not value:
        return None
    value = value.strip()
    parsed = urlsplit(value)
    if (
        len(value) > 2000
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise HTTPException(422, "Informe um link HTTPS válido para o multitrack.")
    return value


def _validate_files(
    db, payload, mp3, wav, archive, cover=None, *, multitrack_url=None,
    has_wav=False, has_archive=False, has_external=False,
):
    policy = DEFAULT_POLICIES[StorageScope.PRODUCTION_TEMP]
    limits = beat_upload_config_service.limits_bytes(db)
    for kind, item, allowed in (
        ("mp3", mp3, {"audio/mpeg"}),
        ("wav", wav, {"audio/wav", "audio/x-wav"}),
        ("multitrack", archive, ARCHIVE_MIMES),
    ):
        if item is None:
            continue
        data, mime = item
        if mime not in allowed:
            raise HTTPException(422, f"Formato inválido no arquivo {kind}.")
        if len(data) > limits[kind]:
            raise HTTPException(413, f"O arquivo {kind} excede o limite configurado.")
        try:
            policy.validate(data, mime)
        except StorageValidationError:
            raise HTTPException(422, "Conteudo do arquivo invalido.") from None
    if payload.preco_wav is not None and wav is None and not has_wav:
        raise HTTPException(422, "Envie o WAV para definir o preco WAV.")
    external = _external_multitrack_url(multitrack_url)
    if archive is not None and external:
        raise HTTPException(422, "Escolha arquivo ou link para o multitrack, não ambos.")
    if payload.preco_multitrack is not None and archive is None and not external and not has_archive and not has_external:
        raise HTTPException(422, "Envie o multitrack para definir seu preco.")
    if mp3 is not None:
        audio_tag_service.duracao(mp3[0], limite=1800)
    if cover is not None:
        if len(cover[0]) > limits["capa"]:
            raise HTTPException(413, "A capa excede o limite configurado.")
        try:
            DEFAULT_POLICIES[StorageScope.PUBLIC_IMAGE].validate(*cover)
        except StorageValidationError:
            raise HTTPException(422, "Conteudo da capa invalido.") from None


def price_details(db, model, kind):
    from services import promocao_service

    bases = {
        "lease": model.preco_lease if model.mp3_ref is None else None,
        "lease_mp3": model.preco_lease if model.mp3_ref else None,
        "lease_wav": model.preco_wav if model.wav_ref else None,
        "multitrack": model.preco_multitrack if (model.multitrack_ref or model.multitrack_url) else None,
        "exclusivo": model.preco_exclusivo,
    }
    base = bases.get(kind)
    if base is None:
        return None
    target = SimpleNamespace(
        valor_base=base,
        promocao=None,
        # Service-catalog promotions do not alter producer-defined license prices.
        aplica_desconto=False,
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
        "tem_multitrack": bool(model.multitrack_ref or model.multitrack_url),
        "multitrack_origem": "link" if model.multitrack_url else ("arquivo" if model.multitrack_ref else None),
        "capa_url": model.capa_url,
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


def create(db: Session, *, actor, payload: BeatCreate, mp3, cover, wav=None, archive=None, multitrack_url=None):
    if not actor.painel_beats:
        raise HTTPException(403, "Painel de beats nao habilitado para esta conta.")
    settings = beat_upload_config_service.limits(db)
    external = _external_multitrack_url(multitrack_url)
    if settings.multitrack_mode == "link" and archive is not None:
        raise HTTPException(422, "O multitrack deve ser enviado por link.")
    if settings.multitrack_mode == "arquivo" and external:
        raise HTTPException(422, "O multitrack deve ser enviado como arquivo.")
    _validate_files(db, payload, mp3, wav, archive, cover, multitrack_url=external)
    tag, profile = _tag(db, actor.id)
    tagged_mp3 = audio_tag_service.mixar(
        mp3[0], tag.conteudo, profile.intervalo_segundos, profile.volume_percentual
    )
    storage = new_production_file_storage("previa")
    image_storage = storage_for(StorageScope.PUBLIC_IMAGE)
    saved = []
    saved_cover = None
    try:
        saved_cover = image_storage.save(*cover)
        cover_url = saved_cover.public_url or image_storage.get_public_url(saved_cover.reference)
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
            multitrack_url=external,
            capa_ref=str(saved_cover.reference),
            capa_url=cover_url,
            capa_sha256=hashlib.sha256(cover[0]).hexdigest(),
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
        if saved_cover is not None:
            try:
                image_storage.delete(saved_cover.reference)
            except StorageError:
                logger.warning("beat_cover_compensation_failed")
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


def producer_catalog(db):
    return client_list(db)


def admin_list(db):
    if expire_reservations(db):
        db.commit()
    rows = db.scalars(select(BeatModel).order_by(BeatModel.created_at.desc())).all()
    licenses = {}
    for license in db.scalars(
        select(BeatLicencaModel).order_by(BeatLicencaModel.created_at.desc())
    ).all():
        licenses.setdefault(license.beat_id, []).append(_license_response(license))
    result = []
    for row in rows:
        item = _response(db, row, include_base=True)
        item["licencas"] = licenses.get(row.id, [])
        item["pode_voltar_ao_catalogo"] = row.status == "vendido" and not any(
            entry["tipo"] == "exclusivo" and entry["status"] == "adquirida"
            for entry in item["licencas"]
        )
        result.append(item)
    return result


def _license_response(license):
    return {
        "id": license.id,
        "tipo": license.tipo,
        "status": license.status,
        "proposta_id": license.proposta_id,
        "valor": license.valor,
        "created_at": license.created_at,
        "expira_em": _deadline(license),
        "adquirida_em": license.adquirida_em,
        "cancelada_em": license.cancelada_em,
        "motivo_cancelamento": license.motivo_cancelamento,
    }


def client_list(db):
    if expire_reservations(db):
        db.commit()
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


def acquired_multitracks(db, actor):
    if actor.cliente_id is None:
        return []
    rows = db.execute(
        select(BeatLicencaModel, BeatModel)
        .join(BeatModel, BeatModel.id == BeatLicencaModel.beat_id)
        .where(
            BeatLicencaModel.cliente_id == actor.cliente_id,
            BeatLicencaModel.status == "adquirida",
            BeatLicencaModel.tipo.in_(("lease", "lease_mp3", "lease_wav", "multitrack", "exclusivo")),
        )
        .order_by(BeatLicencaModel.adquirida_em.desc())
    ).all()
    return [
        {
            "beat_id": beat.id,
            "titulo": beat.titulo,
            "licenca": license.tipo,
            "adquirida_em": license.adquirida_em,
            "arquivos": _available_files(beat, license.tipo),
            "disponivel": bool(_available_files(beat, license.tipo)),
        }
        for license, beat in rows
    ]


def _available_files(beat, license_type):
    allowed = {
        "lease": ("mp3",),
        "lease_mp3": ("mp3",),
        "lease_wav": ("wav",),
        "multitrack": ("multitrack",),
        "exclusivo": ("mp3", "wav", "multitrack"),
    }.get(license_type, ())
    available = []
    if "mp3" in allowed and beat.original_ref and beat.original_sha256:
        available.append("mp3")
    if "wav" in allowed and beat.wav_ref and beat.wav_sha256:
        available.append("wav")
    if "multitrack" in allowed and (beat.multitrack_url or beat.multitrack_ref):
        available.append("multitrack")
    return available


def purchased_file(db, beat_id, kind, actor):
    if kind not in {"mp3", "wav", "multitrack"} or actor.cliente_id is None:
        raise HTTPException(404, "Arquivo adquirido nao encontrado.")
    rows = db.execute(
        select(BeatLicencaModel, BeatModel)
        .join(BeatModel, BeatModel.id == BeatLicencaModel.beat_id)
        .where(
            BeatLicencaModel.beat_id == beat_id,
            BeatLicencaModel.cliente_id == actor.cliente_id,
            BeatLicencaModel.status == "adquirida",
        )
        .order_by(BeatLicencaModel.adquirida_em.desc())
    ).all()
    if not rows:
        raise HTTPException(404, "Arquivo adquirido nao encontrado.")
    beat = rows[0][1]
    if not any(kind in _available_files(item, license.tipo) for license, item in rows):
        raise HTTPException(404, "Arquivo adquirido nao encontrado.")
    if kind == "multitrack":
        return multitrack_delivery(db, beat_id, actor)
    reference, expected_hash, mime, extension = (
        (beat.original_ref, beat.original_sha256, "audio/mpeg", "mp3")
        if kind == "mp3"
        else (beat.wav_ref, beat.wav_sha256, "audio/wav", "wav")
    )
    contents = new_production_file_storage("previa").read(reference)
    if hashlib.sha256(contents).hexdigest() != expected_hash:
        raise HTTPException(409, "Integridade do arquivo adquirido invalida.")
    return {
        "type": "file",
        "contents": contents,
        "mime": mime,
        "filename": f"beat-{beat.id}.{extension}",
    }


def multitrack_delivery(db, beat_id, actor):
    if actor.cliente_id is None:
        raise HTTPException(404, "Multitrack não encontrado.")
    row = db.execute(
        select(BeatLicencaModel, BeatModel)
        .join(BeatModel, BeatModel.id == BeatLicencaModel.beat_id)
        .where(
            BeatLicencaModel.beat_id == beat_id,
            BeatLicencaModel.cliente_id == actor.cliente_id,
            BeatLicencaModel.status == "adquirida",
            BeatLicencaModel.tipo.in_(("multitrack", "exclusivo")),
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Multitrack não encontrado.")
    _, beat = row
    if beat.multitrack_url:
        return {"type": "link", "url": beat.multitrack_url}
    if not beat.multitrack_ref or not beat.multitrack_sha256:
        raise HTTPException(409, "O multitrack adquirido ainda não está disponível.")
    contents = new_production_file_storage("previa").read(beat.multitrack_ref)
    if hashlib.sha256(contents).hexdigest() != beat.multitrack_sha256:
        raise HTTPException(409, "Integridade do multitrack inválida.")
    extension = "rar" if beat.multitrack_mime == "application/vnd.rar" else "zip"
    return {
        "type": "file",
        "contents": contents,
        "mime": beat.multitrack_mime or "application/octet-stream",
        "filename": f"beat-{beat.id}-multitrack.{extension}",
    }


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
    # AUD6-S04-003: a beat promised to a client is not rejected silently.
    if payload.decisao == "rejeitar" and db.scalar(
        select(BeatLicencaModel.id).where(
            BeatLicencaModel.beat_id == beat_id,
            BeatLicencaModel.status.in_(("reservada", "adquirida")),
        )
    ):
        raise HTTPException(
            409,
            "Este beat tem licença reservada ou vendida. Libere a reserva antes de rejeitar.",
        )
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


def edit(db, beat_id, payload, actor, *, mp3=None, wav=None, archive=None, cover=None, multitrack_url=None):
    model = db.scalar(select(BeatModel).where(BeatModel.id == beat_id).with_for_update())
    if model is None:
        raise HTTPException(404, "Beat nao encontrado.")
    if model.status == "vendido" or db.scalar(select(BeatLicencaModel.id).where(
        BeatLicencaModel.beat_id == beat_id, BeatLicencaModel.status.in_(("reservada", "adquirida"))
    )):
        raise HTTPException(409, "Beat com licenca ativa nao pode ser alterado.")
    settings = beat_upload_config_service.limits(db)
    external = _external_multitrack_url(multitrack_url)
    if settings.multitrack_mode == "link" and archive is not None:
        raise HTTPException(422, "O multitrack deve ser enviado por link.")
    if settings.multitrack_mode == "arquivo" and external:
        raise HTTPException(422, "O multitrack deve ser enviado como arquivo.")
    _validate_files(db, payload, mp3, wav, archive, cover, multitrack_url=external,
                    has_wav=bool(model.wav_ref), has_archive=bool(model.multitrack_ref),
                    has_external=bool(model.multitrack_url))
    tagged_mp3 = None
    if mp3 is not None:
        tag, profile = _tag(db, model.produtor_id)
        tagged_mp3 = audio_tag_service.mixar(
            mp3[0], tag.conteudo, profile.intervalo_segundos, profile.volume_percentual
        )
    storage = new_production_file_storage("previa")
    image_storage = storage_for(StorageScope.PUBLIC_IMAGE) if cover else None
    saved_cover = None
    old_cover = None
    saved, old = [], []
    try:
        if cover is not None:
            saved_cover = image_storage.save(*cover)
            old_cover = model.capa_ref
            model.capa_ref = str(saved_cover.reference)
            model.capa_url = saved_cover.public_url or image_storage.get_public_url(saved_cover.reference)
            model.capa_sha256 = hashlib.sha256(cover[0]).hexdigest()
        if mp3 is not None:
            original_ref = storage.save(*mp3)
            saved.append(original_ref)
            old.append(model.original_ref)
            model.original_ref = original_ref
            model.original_sha256 = hashlib.sha256(mp3[0]).hexdigest()
        if external:
            if model.multitrack_ref:
                old.append(model.multitrack_ref)
            model.multitrack_ref = None
            model.multitrack_sha256 = None
            model.multitrack_mime = None
            model.multitrack_url = external
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
                model.multitrack_url = None
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
        if saved_cover is not None:
            try:
                image_storage.delete(saved_cover.reference)
            except StorageError:
                logger.warning("beat_cover_compensation_failed")
        raise
    for reference in set(old) - set(saved):
        try:
            storage.delete(reference)
        except ProducaoArquivoStorageError:
            pass
    if old_cover:
        try:
            image_storage.delete(old_cover)
        except StorageError:
            logger.warning("beat_cover_retirement_failed beat_id=%s", beat_id)
    return _response(db, model, include_base=True)


def preview(db, beat_id, actor):
    model = db.get(BeatModel, beat_id)
    if model is None:
        raise HTTPException(404, "Beat nao encontrado.")
    allowed = (
        actor.role == "admin"
        or (
            actor.role == "produtor"
            and (
                model.produtor_id == actor.id
                or (model.status == "aprovado" and model.ativo)
            )
        )
        or (actor.role == "cliente" and model.status == "aprovado" and model.ativo)
    )
    if not allowed:
        raise HTTPException(404, "Beat nao encontrado.")
    data = new_production_file_storage("previa").read(model.preview_ref)
    if hashlib.sha256(data).hexdigest() != model.preview_sha256:
        raise HTTPException(409, "Integridade do preview invalida.")
    return data


def request_license(db, beat_id, kind, actor, idempotency_key, request_id=None):
    from models import OrcamentoModel
    from services import proposta_comercial_service, proposta_service

    def accept_purchase(proposal_id, client_id):
        try:
            return proposta_comercial_service.aceitar_compra_catalogo(
                db,
                proposal_id,
                cliente_id=client_id,
                actor=actor,
                request_id=request_id,
            )
        except proposta_service.PropostaNaoEncontrada as error:
            raise HTTPException(404, str(error)) from None
        except (proposta_service.PropostaConflito, proposta_service.PropostaInvalida) as error:
            raise HTTPException(409, str(error)) from None

    beat = db.scalar(select(BeatModel).where(BeatModel.id == beat_id).with_for_update())
    if beat is None or beat.status != "aprovado" or not beat.ativo:
        raise HTTPException(404, "Beat nao encontrado.")
    expire_reservations(db, beat_id=beat.id)
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
        proposal = proposta_service.criar_por_orcamento(db, existing.id)
        accepted = accept_purchase(proposal.id, client.id)
        return {**accepted.model_dump(mode="json"), "checkout_path": f"/checkout?proposta={accepted.id}"}
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
    proposal = proposta_service.criar_por_orcamento(db, budget.id)
    accepted = accept_purchase(proposal.id, client.id)
    return {**accepted.model_dump(mode="json"), "checkout_path": f"/checkout?proposta={accepted.id}"}


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
        expire_reservations(db, beat_id=beat.id)
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
                expira_em=_now() + _reservation_window(),
            )
        )
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "O beat foi reservado por outra proposta.") from None


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _reservation_window():
    from core.config import settings

    # Some isolated harnesses replace settings with a namespace; 48 h is the default.
    return timedelta(hours=int(getattr(settings, "BEAT_RESERVATION_HOURS", 48)))


def _deadline(license):
    if license.status != "reservada":
        return _aware(license.expira_em)
    if license.expira_em is not None:
        return _aware(license.expira_em)
    return _aware(license.created_at) + _reservation_window()


def _cancel(license, reason, now=None):
    license.status = "cancelada"
    license.cancelada_em = now or _now()
    license.motivo_cancelamento = reason


def _recent_payment_attempt(db, proposta_id, now):
    from models import CobrancaModel, PagamentoModel

    rows = db.execute(
        select(PagamentoModel.status, PagamentoModel.created_at)
        .join(CobrancaModel, CobrancaModel.id == PagamentoModel.cobranca_id)
        .where(
            CobrancaModel.proposta_id == proposta_id,
            PagamentoModel.status.in_(
                (PagamentoStatus.PENDENTE.value, PagamentoStatus.APROVADO.value)
            ),
        )
    ).all()
    # Money already received always keeps the reservation; an open attempt
    # keeps it only during the grace window.
    return any(
        status == PagamentoStatus.APROVADO.value
        or _aware(created) > now - PENDING_PAYMENT_GRACE
        for status, created in rows
    )


def expire_reservations(db, *, beat_id=None, proposta_id=None):
    """AUD6-S06-001: release unpaid reservations past their deadline.

    Runs lazily wherever availability is decided, so no scheduler is needed. A
    reservation whose charge has a payment attempt younger than the grace
    window is kept until that attempt resolves.
    """
    query = select(BeatLicencaModel).where(BeatLicencaModel.status == "reservada")
    if beat_id is not None:
        query = query.where(BeatLicencaModel.beat_id == beat_id)
    if proposta_id is not None:
        query = query.where(BeatLicencaModel.proposta_id == proposta_id)
    now = _now()
    expired = 0
    for license in db.scalars(query.with_for_update()).all():
        if _deadline(license) > now:
            continue
        if _recent_payment_attempt(db, license.proposta_id, now):
            continue
        _cancel(license, "expirada", now)
        audit_service.record(
            db,
            actor=None,
            action="beat.licenca.expirada",
            entity_type="beat_licenca",
            entity_id=license.id,
            metadata={"beat_id": license.beat_id, "proposal_id": license.proposta_id},
        )
        expired += 1
    if expired:
        db.flush()
    return expired


def checkout_blocked_reason(db, proposta_id):
    """Return a client-facing reason when a beat proposal can no longer be paid."""
    licenses = db.scalars(
        select(BeatLicencaModel).where(BeatLicencaModel.proposta_id == proposta_id)
    ).all()
    if not licenses:
        return None
    expire_reservations(db, proposta_id=proposta_id)
    if any(license.status == "cancelada" for license in licenses):
        return (
            "A reserva deste beat expirou ou foi liberada. "
            "Solicite a licença novamente no catálogo."
        )
    return None


def _license_conflict(db, license):
    beat = db.scalar(
        select(BeatModel).where(BeatModel.id == license.beat_id).with_for_update()
    )
    if beat is None or beat.status != "aprovado" or not beat.ativo:
        return beat, True
    others = select(BeatLicencaModel.id).where(
        BeatLicencaModel.beat_id == license.beat_id,
        BeatLicencaModel.id != license.id,
        BeatLicencaModel.status.in_(("reservada", "adquirida")),
    )
    if license.tipo != "exclusivo":
        others = others.where(BeatLicencaModel.tipo == "exclusivo")
    return beat, db.scalar(others) is not None


def _flag_payment_conflict(db, cobranca, reason):
    from models import PagamentoModel

    payment = db.scalar(
        select(PagamentoModel)
        .where(
            PagamentoModel.cobranca_id == cobranca.id,
            PagamentoModel.status == PagamentoStatus.APROVADO.value,
        )
        .order_by(PagamentoModel.id.desc())
        .limit(1)
    )
    if payment is not None:
        payment.reconciliation_status = "conflict"
        payment.reconciliation_reason = reason


def _revoke_reverted(db, cobranca, now):
    """AUD6-S06-002: a charge that is no longer fully paid stops granting files."""
    licenses = db.scalars(
        select(BeatLicencaModel)
        .where(
            BeatLicencaModel.proposta_id == cobranca.proposta_id,
            BeatLicencaModel.status == "adquirida",
        )
        .with_for_update()
    ).all()
    for license in licenses:
        _cancel(license, "pagamento_revertido", now)
        # An exclusive beat stays out of the catalog until an administrator
        # decides to list it again (relist).
        audit_service.record(
            db,
            actor=None,
            action="beat.licenca.revogada",
            entity_type="beat_licenca",
            entity_id=license.id,
            metadata={"beat_id": license.beat_id, "proposal_id": license.proposta_id},
        )


def release_reservation(db, license_id, motivo, actor):
    motivo = (motivo or "").strip()
    if not motivo:
        raise HTTPException(422, "Informe o motivo da liberação.")
    license = db.scalar(
        select(BeatLicencaModel).where(BeatLicencaModel.id == license_id).with_for_update()
    )
    if license is None:
        raise HTTPException(404, "Licença não encontrada.")
    if license.status != "reservada":
        raise HTTPException(409, "Somente reservas em aberto podem ser liberadas.")
    _cancel(license, "admin")
    audit_service.record(
        db,
        actor=actor,
        action="beat.licenca.liberada",
        entity_type="beat_licenca",
        entity_id=license.id,
        metadata={"beat_id": license.beat_id, "proposal_id": license.proposta_id, "reason": motivo},
    )
    db.commit()
    db.refresh(license)
    return _license_response(license)


def relist(db, beat_id, motivo, actor):
    motivo = (motivo or "").strip()
    if not motivo:
        raise HTTPException(422, "Informe o motivo para devolver o beat ao catálogo.")
    beat = db.scalar(select(BeatModel).where(BeatModel.id == beat_id).with_for_update())
    if beat is None:
        raise HTTPException(404, "Beat não encontrado.")
    if beat.status != "vendido":
        raise HTTPException(409, "Somente beats vendidos podem voltar ao catálogo.")
    if db.scalar(
        select(BeatLicencaModel.id).where(
            BeatLicencaModel.beat_id == beat_id,
            BeatLicencaModel.tipo == "exclusivo",
            BeatLicencaModel.status == "adquirida",
        )
    ):
        raise HTTPException(409, "O exclusivo deste beat continua ativo.")
    beat.status, beat.ativo = "aprovado", True
    audit_service.record(
        db,
        actor=actor,
        action="beat.relistado",
        entity_type="beat",
        entity_id=beat.id,
        metadata={"reason": motivo},
    )
    db.commit()
    db.refresh(beat)
    return _response(db, beat, include_base=True)


def confirm_paid(db, cobranca):
    """Keep beat licenses in step with the charge (called on every payment change)."""
    now = _now()
    if cobranca.status != CobrancaStatus.PAGA.value:
        _revoke_reverted(db, cobranca, now)
        return
    licenses = db.scalars(
        select(BeatLicencaModel)
        .where(
            BeatLicencaModel.proposta_id == cobranca.proposta_id,
            BeatLicencaModel.status.in_(("reservada", "cancelada")),
        )
        .with_for_update()
    ).all()
    for license in licenses:
        if license.status == "cancelada":
            if license.motivo_cancelamento not in ("expirada", "admin"):
                continue
            # Paid after the reservation lapsed: honour it only if the beat is
            # still free; otherwise the payment needs a human decision.
            beat, conflict = _license_conflict(db, license)
            if conflict:
                _flag_payment_conflict(db, cobranca, "beat_reservation_released")
                audit_service.record(
                    db,
                    actor=None,
                    action="beat.licenca.pagamento_apos_liberacao",
                    entity_type="beat_licenca",
                    entity_id=license.id,
                    metadata={"beat_id": license.beat_id, "proposal_id": license.proposta_id},
                )
                continue
            license.cancelada_em = None
            license.motivo_cancelamento = None
        else:
            beat = db.scalar(
                select(BeatModel).where(BeatModel.id == license.beat_id).with_for_update()
            )
        license.status = "adquirida"
        license.adquirida_em = now
        if license.tipo == "exclusivo":
            beat.status = "vendido"
            beat.ativo = False
