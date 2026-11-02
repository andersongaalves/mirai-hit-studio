import hashlib
import ipaddress
import json
import logging
from urllib.parse import urlparse
from uuid import UUID, uuid4

from models import ProducaoArquivoModel, ProducaoEntregaFinalModel
from schemas.producao_arquivo import ProducaoArquivoResponse
from services import (
    audit_service,
    cota_arquivo_service,
    producao_arquivo_service,
    producao_licenca_service,
)
from services.producao_arquivo_storage import (
    ProducaoArquivoStorageError,
    new_production_file_storage,
)
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class ProducaoEntregaError(Exception):
    pass


class ProducaoEntregaConflict(ProducaoEntregaError):
    pass


class ProducaoEntregaUnavailable(ProducaoEntregaError):
    pass


def _text(value, *, field, limit):
    cleaned = "".join(character for character in (value or "") if ord(character) >= 32 and ord(character) != 127).strip()
    if not cleaned or len(cleaned) > limit:
        raise ProducaoEntregaError(f"{field} invalido.")
    return cleaned


def _multitrack_url(value):
    value = (value or "").strip()
    if not value:
        return None
    if len(value) > 2000:
        raise ProducaoEntregaError("Link do multitrack invalido.")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ProducaoEntregaError("Use um link HTTPS valido para o multitrack.")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ProducaoEntregaError("Link do multitrack invalido.")
    try:
        if ipaddress.ip_address(hostname).is_private:
            raise ProducaoEntregaError("Link do multitrack invalido.")
    except ValueError:
        pass
    return value


def _technical_sheet(category, bpm, tonalidade, additional_credits):
    if category != "instrumental":
        if bpm is not None or (tonalidade or "").strip() or (additional_credits or "").strip():
            raise ProducaoEntregaError("A ficha tecnica se aplica somente a entregas de beat.")
        return None, None, []
    if not isinstance(bpm, int) or isinstance(bpm, bool) or not 20 <= bpm <= 300:
        raise ProducaoEntregaError("Informe um BPM entre 20 e 300.")
    key = _text(tonalidade, field="Tom / Key", limit=20)
    credits = []
    seen = set()
    for raw in (additional_credits or "").splitlines():
        name = " ".join(raw.split())
        if not name:
            continue
        if len(name) < 2 or len(name) > 120:
            raise ProducaoEntregaError("Cada credito adicional deve ter entre 2 e 120 caracteres.")
        marker = name.casefold()
        if marker not in seen:
            seen.add(marker)
            credits.append(name)
    if len(credits) > 10:
        raise ProducaoEntregaError("Informe no maximo 10 creditos adicionais.")
    return bpm, key, credits


def _file_response(model):
    return ProducaoArquivoResponse.model_validate(model).model_dump()


def response(model, *, blocked=False):
    return {
        "id": model.id,
        "producao_id": model.producao_id,
        "categoria": model.categoria,
        "titulo": model.titulo,
        "etapa_id": getattr(model.arquivo_principal, "etapa_id", None),
        "bpm": model.bpm,
        "tonalidade": model.tonalidade,
        "creditos_adicionais": model.creditos_adicionais or [],
        "observacao": model.observacao,
        "arquivo_principal": _file_response(model.arquivo_principal),
        "wav_arquivo": _file_response(model.wav_arquivo) if model.wav_arquivo else None,
        "multitrack_arquivo": _file_response(model.multitrack_arquivo) if model.multitrack_arquivo else None,
        "multitrack_disponivel": bool(model.multitrack_arquivo_id or model.multitrack_url),
        "licenca_arquivo": _file_response(model.licenca_arquivo) if model.licenca_arquivo else None,
        "bloqueado_pagamento": bool(blocked),
        "created_at": model.created_at,
    }


def _validate_files(category, main, wav, archive, license_file, external):
    for item in (main, wav, archive, license_file):
        if item is not None:
            producao_arquivo_service._validate_upload(item[2], item[1], "entrega")
    if category == "instrumental":
        if main[1] != "audio/mpeg":
            raise ProducaoEntregaError("O instrumental principal deve ser um MP3.")
        if wav is None or wav[1] not in {"audio/wav", "audio/x-wav"}:
            raise ProducaoEntregaError("Envie a versao WAV do instrumental.")
        if (archive is None) == (external is None):
            raise ProducaoEntregaError("Escolha um arquivo ou um link para o multitrack.")
        if archive is not None and archive[1] not in {"application/zip", "application/vnd.rar"}:
            raise ProducaoEntregaError("O multitrack deve ser ZIP ou RAR.")
        if license_file is not None:
            raise ProducaoEntregaError("A licenca exclusiva desta entrega e gerada automaticamente.")
    elif category == "outro":
        if wav is not None or archive is not None or external is not None:
            raise ProducaoEntregaError("Campos de instrumental nao podem ser enviados nesta categoria.")
        if license_file is not None and license_file[1] != "application/pdf":
            raise ProducaoEntregaError("A licenca deve ser um PDF.")
    else:
        raise ProducaoEntregaError("Tipo de entrega invalido.")


def _new_file(production, actor, item, role, storage, stage_id=None):
    filename, mime_type, data = item
    key = storage.save(data, mime_type)
    model = ProducaoArquivoModel(
        producao_id=production.id,
        remetente_usuario_id=actor.id,
        tipo="entrega",
        nome_exibicao=producao_arquivo_service._display_name(filename),
        mime_type=mime_type,
        tamanho_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        object_key=key,
        grupo_versao=str(uuid4()),
        versao=1,
        visivel_produtor=True,
        visivel_cliente=True,
        original_restrito=False,
        observacao=f"Pacote de entrega final: {role}",
        etapa_id=stage_id,
    )
    return model, key


def create(db, *, production, actor, request_id, category, title, main, wav=None, archive=None,
           multitrack_url=None, license_file=None, note=None, bpm=None, tonalidade=None,
           creditos_adicionais=None, request_log_id=None, storage=None, stage_id=None):
    try:
        request_key = str(UUID(str(request_id)))
    except (TypeError, ValueError, AttributeError):
        raise ProducaoEntregaError("Identificador do envio invalido.") from None
    title = _text(title, field="Titulo", limit=150)
    note = producao_arquivo_service._normalize_note(note)
    external = _multitrack_url(multitrack_url)
    bpm, tonalidade, credits = _technical_sheet(category, bpm, tonalidade, creditos_adicionais)
    _validate_files(category, main, wav, archive, license_file, external)
    try:
        stage_id = producao_arquivo_service.resolve_stage(db, production.id, stage_id)
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise ProducaoEntregaError(str(exc)) from None
    media_components = [item for item in (main, wav, archive) if item is not None]
    components = [*media_components, *([license_file] if license_file is not None else [])]
    request_hash = hashlib.sha256(json.dumps({
        "production_id": production.id,
        "producer_id": actor.id,
        "category": category,
        "title": title,
        "bpm": bpm,
        "tonalidade": tonalidade,
        "creditos_adicionais": credits,
        "note": note,
        "multitrack_url": external,
        "etapa_id": stage_id,
        "files": [
            {"name": item[0], "mime": item[1], "sha256": hashlib.sha256(item[2]).hexdigest()}
            for item in components
        ],
    }, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    existing = db.query(ProducaoEntregaFinalModel).filter_by(request_id=request_key).first()
    if existing is not None:
        if (
            existing.producao_id != production.id
            or existing.produtor_id != actor.id
            or existing.request_hash != request_hash
        ):
            raise ProducaoEntregaConflict("Este identificador ja foi usado em outro envio.")
        return existing
    if category == "instrumental":
        license_file = producao_licenca_service.gerar(
            db,
            production=production,
            producer=actor,
            title=title,
            request_id=request_key,
            bpm=bpm,
            tonalidade=tonalidade,
            creditos_adicionais=credits,
        )
    cota_arquivo_service.travar_producao(db, production.id)
    try:
        cota_arquivo_service.verificar_pacote_entrega(
            db,
            production.id,
            [(item[1], len(item[2]), item[2]) for item in media_components],
            extra_storage_bytes=len(license_file[2]) if license_file is not None else 0,
        )
    except cota_arquivo_service.CotaFormato as exc:
        db.rollback()
        raise ProducaoEntregaError(str(exc)) from None
    except cota_arquivo_service.CotaExcedida as exc:
        db.rollback()
        raise ProducaoEntregaConflict(str(exc)) from None

    storage = storage or new_production_file_storage("entrega")
    saved = []
    try:
        principal, key = _new_file(production, actor, main, "principal", storage, stage_id)
        saved.append(key)
        db.add(principal)
        db.flush()
        wav_model = archive_model = license_model = None
        for item, role in ((wav, "WAV"), (archive, "multitrack"), (license_file, "licenca")):
            if item is None:
                continue
            model, key = _new_file(production, actor, item, role, storage, stage_id)
            saved.append(key)
            db.add(model)
            db.flush()
            if role == "WAV":
                wav_model = model
            elif role == "multitrack":
                archive_model = model
            else:
                license_model = model
        delivery = ProducaoEntregaFinalModel(
            request_id=request_key,
            request_hash=request_hash,
            producao_id=production.id,
            produtor_id=actor.id,
            categoria=category,
            titulo=title,
            bpm=bpm,
            tonalidade=tonalidade,
            creditos_adicionais=credits,
            arquivo_principal_id=principal.id,
            wav_arquivo_id=getattr(wav_model, "id", None),
            multitrack_arquivo_id=getattr(archive_model, "id", None),
            multitrack_url=external,
            licenca_arquivo_id=getattr(license_model, "id", None),
            observacao=note,
        )
        db.add(delivery)
        db.flush()
        audit_service.record(
            db, actor=actor, action="production.final_delivery_created",
            entity_type="production_final_delivery", entity_id=delivery.id,
            metadata={"production_id": production.id, "category": category}, request_id=request_log_id,
        )
        db.commit()
        db.refresh(delivery)
    except Exception as exc:
        db.rollback()
        persisted = db.query(ProducaoEntregaFinalModel).filter_by(request_id=request_key).first()
        if persisted is not None and persisted.producao_id == production.id and persisted.produtor_id == actor.id:
            return persisted
        for key in saved:
            try:
                storage.delete(key)
            except ProducaoArquivoStorageError:
                logger.error("final_delivery_cleanup_failed production_id=%s", production.id)
        if isinstance(exc, ProducaoArquivoStorageError):
            raise ProducaoEntregaUnavailable(str(exc)) from None
        if isinstance(exc, IntegrityError):
            raise ProducaoEntregaConflict("Conflito ao registrar a entrega final.") from None
        raise
    _replace_previous(db, delivery=delivery, production=production, actor=actor,
                      request_log_id=request_log_id, storage=storage)
    db.refresh(delivery)
    return delivery


LOCKED_STATUSES = {"entregue"}


def update(db, *, model, production, actor, changes, request_log_id=None, storage=None):
    """The producer corrects a final delivery they sent: title, note, stage and, for beats,
    the technical sheet. Files are replaced by sending a new delivery. A beat's license is
    issued again (as a new version of the license file) when its sheet or title changes.
    Locked once the production is delivered to the client.
    """
    if model.produtor_id != actor.id:
        raise ProducaoEntregaConflict("So quem enviou a entrega pode edita-la.")
    if production.status in LOCKED_STATUSES:
        raise ProducaoEntregaConflict("A producao ja foi entregue ao cliente; a entrega nao pode mais ser editada.")
    title = _text(changes.get("titulo", model.titulo), field="Titulo", limit=150)
    note = producao_arquivo_service._normalize_note(changes["observacao"]) if "observacao" in changes else model.observacao
    current_stage = getattr(model.arquivo_principal, "etapa_id", None)
    stage_id = current_stage
    if "etapa_id" in changes:
        try:
            stage_id = (
                producao_arquivo_service.resolve_stage(db, production.id, changes["etapa_id"])
                if changes["etapa_id"] is not None else None
            )
        except producao_arquivo_service.ProducaoArquivoError as exc:
            raise ProducaoEntregaError(str(exc)) from None
    if model.categoria == "instrumental":
        bpm, key, credits = _technical_sheet(
            "instrumental",
            changes.get("bpm", model.bpm),
            changes.get("tonalidade", model.tonalidade),
            "\n".join(changes["creditos_adicionais"]) if "creditos_adicionais" in changes else "\n".join(model.creditos_adicionais or []),
        )
    else:
        bpm, key, credits = _technical_sheet("outro", None, None, None)
    changed = {
        field for field, old, new in (
            ("titulo", model.titulo, title),
            ("observacao", model.observacao, note),
            ("etapa_id", current_stage, stage_id),
            ("bpm", model.bpm, bpm),
            ("tonalidade", model.tonalidade, key),
            ("creditos_adicionais", list(model.creditos_adicionais or []), credits),
        ) if old != new
    }
    if not changed:
        return model
    reissue = model.categoria == "instrumental" and bool(changed & {"titulo", "bpm", "tonalidade", "creditos_adicionais"})
    storage = storage or (new_production_file_storage("entrega") if reissue else None)
    saved_key = None
    try:
        model.titulo = title
        model.observacao = note
        model.bpm = bpm
        model.tonalidade = key
        model.creditos_adicionais = credits
        files = [model.arquivo_principal, model.wav_arquivo, model.multitrack_arquivo, model.licenca_arquivo]
        for item in files:
            if item is not None:
                item.etapa_id = stage_id
        if reissue:
            previous = model.licenca_arquivo
            license_file = producao_licenca_service.gerar(
                db, production=production, producer=actor, title=title,
                request_id=model.request_id, bpm=bpm, tonalidade=key, creditos_adicionais=credits,
            )
            new_license, saved_key = _new_file(production, actor, license_file, "licenca", storage, stage_id)
            if previous is not None:
                new_license.grupo_versao = previous.grupo_versao
                new_license.versao = previous.versao + 1
                new_license.substitui_arquivo_id = previous.id
            db.add(new_license)
            db.flush()
            model.licenca_arquivo_id = new_license.id
        audit_service.record(
            db, actor=actor, action="production.final_delivery_edited",
            entity_type="production_final_delivery", entity_id=model.id,
            metadata={"production_id": production.id, "fields": sorted(changed), "license_reissued": reissue},
            request_id=request_log_id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if saved_key is not None:
            try:
                storage.delete(saved_key)
            except ProducaoArquivoStorageError:
                logger.error("final_delivery_edit_cleanup_failed delivery_id=%s", model.id)
        if isinstance(exc, ProducaoArquivoStorageError):
            raise ProducaoEntregaUnavailable(str(exc)) from None
        raise
    db.refresh(model)
    if "etapa_id" in changed:
        # Moved to a stage that already had a final delivery: this one becomes that stage's final.
        _replace_previous(db, delivery=model, production=production, actor=actor, request_log_id=request_log_id)
        db.refresh(model)
    return model


def delete(db, *, model, production, actor, request_log_id=None, storage=None):
    """The producer removes a final delivery they sent, with all its files (and earlier
    versions of its license). Locked once the production is delivered to the client."""
    if model.produtor_id != actor.id:
        raise ProducaoEntregaConflict("So quem enviou a entrega pode exclui-la.")
    if production.status in LOCKED_STATUSES:
        raise ProducaoEntregaConflict("A producao ja foi entregue ao cliente; a entrega nao pode mais ser excluida.")
    _remove(db, model=model, production=production, actor=actor, action="production.final_delivery_deleted",
            request_log_id=request_log_id, storage=storage)


def _stage_of(model):
    return getattr(model.arquivo_principal, "etapa_id", None)


def _replace_previous(db, *, delivery, production, actor, request_log_id=None, storage=None):
    """One final delivery per stage: the new one replaces earlier deliveries of the same stage."""
    stage_id = _stage_of(delivery)
    if stage_id is None:
        return
    previous = [
        item for item in db.query(ProducaoEntregaFinalModel).filter(
            ProducaoEntregaFinalModel.producao_id == production.id,
            ProducaoEntregaFinalModel.id != delivery.id,
        ).all()
        if _stage_of(item) == stage_id
    ]
    for item in previous:
        try:
            _remove(db, model=item, production=production, actor=actor, action="production.final_delivery_replaced",
                    request_log_id=request_log_id, storage=storage, replaced_by=delivery.id)
        except ProducaoEntregaError:
            db.rollback()
            logger.warning("final_delivery_replace_kept delivery_id=%s replaced_by=%s", item.id, delivery.id)


def _remove(db, *, model, production, actor, action, request_log_id=None, storage=None, replaced_by=None):
    from models import ProducaoMensagemModel

    files = [item for item in (model.arquivo_principal, model.wav_arquivo, model.multitrack_arquivo, model.licenca_arquivo) if item]
    previous = model.licenca_arquivo
    while previous is not None and previous.substitui_arquivo_id is not None:
        previous = db.get(ProducaoArquivoModel, previous.substitui_arquivo_id)
        if previous is not None:
            files.append(previous)
    ids = [item.id for item in files]
    if db.query(ProducaoArquivoModel.id).filter(
        ProducaoArquivoModel.substitui_arquivo_id.in_(ids), ProducaoArquivoModel.id.notin_(ids),
    ).first() or db.query(ProducaoMensagemModel.id).filter(ProducaoMensagemModel.arquivo_id.in_(ids)).first():
        raise ProducaoEntregaConflict("Um arquivo desta entrega esta em uso em outro lugar (mensagem ou nova versao).")
    keys = [item.object_key for item in files]
    delivery_id = model.id
    metadata = {"production_id": production.id, "files": len(files)}
    if replaced_by is not None:
        metadata["replaced_by"] = replaced_by
    audit_service.record(
        db, actor=actor, action=action,
        entity_type="production_final_delivery", entity_id=delivery_id,
        metadata=metadata, request_id=request_log_id,
    )
    db.delete(model)
    db.flush()
    # Newest first: an older license version is referenced by the newer one.
    for item in sorted(files, key=lambda file: (file.versao, file.id), reverse=True):
        db.delete(item)
        db.flush()
    db.commit()
    storage = storage or new_production_file_storage("entrega")
    for key in dict.fromkeys(keys):
        try:
            storage.delete(key)
        except ProducaoArquivoStorageError:
            logger.error("final_delivery_delete_cleanup_failed delivery_id=%s", delivery_id)


def list_for_production(db, production_id, *, blocked=False):
    models = db.query(ProducaoEntregaFinalModel).filter_by(producao_id=production_id).order_by(
        ProducaoEntregaFinalModel.created_at.desc(), ProducaoEntregaFinalModel.id.desc(),
    ).all()
    # A delivery being deleted right now may already have lost its main file in this
    # read; it is skipped instead of failing the whole list.
    return [response(model, blocked=blocked) for model in models if model.arquivo_principal is not None]


def get(db, delivery_id):
    model = db.get(ProducaoEntregaFinalModel, delivery_id)
    if model is None:
        raise ProducaoEntregaError("Entrega final nao encontrada.")
    return model


def external_multitrack(model):
    if not model.multitrack_url:
        raise ProducaoEntregaError("Esta entrega nao possui link de multitrack.")
    return model.multitrack_url
