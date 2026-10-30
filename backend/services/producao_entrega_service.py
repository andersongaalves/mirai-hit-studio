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


def _new_file(production, actor, item, role, storage):
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
    )
    return model, key


def create(db, *, production, actor, request_id, category, title, main, wav=None, archive=None,
           multitrack_url=None, license_file=None, note=None, bpm=None, tonalidade=None,
           creditos_adicionais=None, request_log_id=None, storage=None):
    try:
        request_key = str(UUID(str(request_id)))
    except (TypeError, ValueError, AttributeError):
        raise ProducaoEntregaError("Identificador do envio invalido.") from None
    title = _text(title, field="Titulo", limit=150)
    note = producao_arquivo_service._normalize_note(note)
    external = _multitrack_url(multitrack_url)
    bpm, tonalidade, credits = _technical_sheet(category, bpm, tonalidade, creditos_adicionais)
    _validate_files(category, main, wav, archive, license_file, external)
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
        principal, key = _new_file(production, actor, main, "principal", storage)
        saved.append(key)
        db.add(principal)
        db.flush()
        wav_model = archive_model = license_model = None
        for item, role in ((wav, "WAV"), (archive, "multitrack"), (license_file, "licenca")):
            if item is None:
                continue
            model, key = _new_file(production, actor, item, role, storage)
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
        return delivery
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


def list_for_production(db, production_id, *, blocked=False):
    models = db.query(ProducaoEntregaFinalModel).filter_by(producao_id=production_id).order_by(
        ProducaoEntregaFinalModel.created_at.desc(), ProducaoEntregaFinalModel.id.desc(),
    ).all()
    return [response(model, blocked=blocked) for model in models]


def get(db, delivery_id):
    model = db.get(ProducaoEntregaFinalModel, delivery_id)
    if model is None:
        raise ProducaoEntregaError("Entrega final nao encontrada.")
    return model


def external_multitrack(model):
    if not model.multitrack_url:
        raise ProducaoEntregaError("Esta entrega nao possui link de multitrack.")
    return model.multitrack_url
