import hashlib
import logging
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crud import crud_producao
from models.orcamento import OrcamentoModel
from models.portal_produtor import ProducaoArquivoModel
from models.producao import ProducaoModel
from services import audit_service, cota_arquivo_service
from services.producao_arquivo_storage import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
    ProducaoArquivoStorageError,
    new_production_file_storage,
)

logger = logging.getLogger(__name__)
PRODUCER_UPLOAD_TYPES = {"previa", "entrega"}
CLIENT_UPLOAD_TYPES = {"material", "referencia"}
ALL_FILE_TYPES = {"material", "referencia", "previa", "entrega", "comprovante"}


class ProducaoArquivoError(Exception):
    pass


class ProducaoArquivoConflict(ProducaoArquivoError):
    pass


class ProducaoArquivoNotFound(ProducaoArquivoError):
    pass


class ProducaoArquivoUnavailable(ProducaoArquivoError):
    pass


def _display_name(filename):
    name = Path(filename or "arquivo").name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return (name or "arquivo")[:180]


def _validate_upload(data, mime_type, file_type):
    if file_type not in ALL_FILE_TYPES:
        raise ProducaoArquivoError("Tipo de arquivo invalido.")
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ProducaoArquivoError("Tipo de arquivo nao permitido.")
    if not data or len(data) > MAX_FILE_SIZE:
        raise ProducaoArquivoError("Tamanho de arquivo nao permitido.")


MAX_NOTE_LENGTH = 1000


def _normalize_note(note):
    """Keep notes as plain single-paragraph-safe text; empty input means no note."""
    if note is None:
        return None
    if not isinstance(note, str):
        raise ProducaoArquivoError("Observacao invalida.")
    cleaned = "".join(
        character for character in note
        if character in "\n\t" or (ord(character) >= 32 and ord(character) != 127)
    ).strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_NOTE_LENGTH:
        raise ProducaoArquivoError(f"A observacao deve ter ate {MAX_NOTE_LENGTH} caracteres.")
    return cleaned


def _version(db, production_id, file_type, replaces_id, replacement_actor_id=None):
    if replaces_id is None:
        return str(uuid4()), 1, None
    previous = db.get(ProducaoArquivoModel, replaces_id)
    if (
        previous is None
        or previous.producao_id != production_id
        or previous.tipo != file_type
        or (
            replacement_actor_id is not None
            and previous.remetente_usuario_id != replacement_actor_id
        )
    ):
        raise ProducaoArquivoNotFound("Arquivo anterior nao encontrado.")
    replacement = (
        db.query(ProducaoArquivoModel.id)
        .filter(ProducaoArquivoModel.substitui_arquivo_id == previous.id)
        .first()
    )
    if replacement:
        raise ProducaoArquivoConflict("Esta versao ja foi substituida.")
    return previous.grupo_versao, previous.versao + 1, previous


def upload(
    db: Session,
    *,
    production: ProducaoModel,
    actor,
    file_type: str,
    filename: str,
    mime_type: str,
    data: bytes,
    visible_to_producer: bool,
    visible_to_client: bool,
    replaces_id: int | None = None,
    replacement_actor_id: int | None = None,
    storage=None,
    request_id=None,
    note: str | None = None,
    enforce_quota: bool = False,
):
    _validate_upload(data, mime_type, file_type)
    note = _normalize_note(note)
    from services import audio_tag_service

    tag_job = audio_tag_service.preparar(db, actor=actor, file_type=file_type, mime_type=mime_type, data=data)
    if file_type == "comprovante" and visible_to_client:
        raise ProducaoArquivoError("Comprovantes de repasse nao podem ser visiveis ao cliente.")
    if enforce_quota:
        # 5.09: lock the production so simultaneous uploads are counted one after the other.
        cota_arquivo_service.travar_producao(db, production.id)
    group_id, version, previous = _version(
        db,
        production.id,
        file_type,
        replaces_id,
        replacement_actor_id,
    )
    if enforce_quota:
        try:
            cota_arquivo_service.verificar(
                db, production.id, tipo=file_type, mime_type=mime_type, tamanho=len(data),
                nova_versao=version if previous is not None else None, data=data,
                extra_storage_bytes=tag_job["reserva_bytes"] if tag_job is not None else 0,
            )
        except cota_arquivo_service.CotaFormato as exc:
            db.rollback()
            raise ProducaoArquivoError(str(exc)) from None
        except cota_arquivo_service.CotaExcedida as exc:
            db.rollback()
            raise ProducaoArquivoConflict(str(exc)) from None
    storage = storage or new_production_file_storage(file_type)
    try:
        object_key = storage.save(data, mime_type)
    except ProducaoArquivoStorageError as exc:
        raise ProducaoArquivoUnavailable(str(exc)) from None

    model = ProducaoArquivoModel(
        producao_id=production.id,
        remetente_usuario_id=getattr(actor, "id", None),
        tipo=file_type,
        nome_exibicao=_display_name(filename),
        mime_type=mime_type,
        tamanho_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        object_key=object_key,
        grupo_versao=group_id,
        versao=version,
        substitui_arquivo_id=previous.id if previous else None,
        visivel_produtor=visible_to_producer,
        visivel_cliente=visible_to_client if tag_job is None else False,
        original_restrito=tag_job is not None,
        observacao=note,
    )
    production_id = production.id
    sender_id = getattr(actor, "id", None)
    try:
        db.add(model)
        db.flush()
        if tag_job is not None:
            from models import PreviaTagJobModel

            model.tag_processamento = PreviaTagJobModel(arquivo_id=model.id, visivel_cliente=visible_to_client, **tag_job)
        audit_service.record(
            db,
            actor=actor,
            action="production.file_uploaded",
            entity_type="production_file",
            entity_id=model.id,
            request_id=request_id,
        )
        from services import portal_notificacao_service

        portal_notificacao_service.arquivo_compartilhado(db, model, actor_id=getattr(actor, "id", None))
        db.commit()
        db.refresh(model)
        return model
    except Exception as exc:
        db.rollback()
        try:
            persisted = db.query(ProducaoArquivoModel).filter_by(object_key=object_key).first()
        except Exception:
            logger.error("production_file_outcome_unknown production_id=%s", production_id)
            raise ProducaoArquivoUnavailable("Envio nao confirmado. Atualize a lista antes de reenviar.") from None
        if persisted is not None:
            # Never compensate an object already referenced after an ambiguous commit.
            if (persisted.producao_id == production_id and persisted.grupo_versao == group_id
                    and persisted.versao == version and persisted.sha256 == hashlib.sha256(data).hexdigest()
                    and persisted.tipo == file_type and persisted.remetente_usuario_id == sender_id):
                return persisted
            raise ProducaoArquivoConflict("Conflito ao registrar o arquivo.") from None
        try:
            storage.delete(object_key)
        except ProducaoArquivoStorageError:
            logger.error(
                "production_file_compensation_failed production_id=%s",
                production_id,
            )
        if isinstance(exc, IntegrityError):
            raise ProducaoArquivoConflict("Conflito ao registrar a nova versao.") from None
        raise


def list_for_admin(db, production_id):
    return (
        db.query(ProducaoArquivoModel)
        .filter(ProducaoArquivoModel.producao_id == production_id)
        .order_by(ProducaoArquivoModel.created_at.desc(), ProducaoArquivoModel.id.desc())
        .all()
    )


def list_for_producer(db, production_id, producer_id):
    production = (
        db.query(ProducaoModel.id)
        .filter(
            ProducaoModel.id == production_id,
            crud_producao.acesso_produtor(producer_id),
        )
        .first()
    )
    if not production:
        raise ProducaoArquivoNotFound("Producao nao encontrada.")
    return (
        db.query(ProducaoArquivoModel)
        .filter(
            ProducaoArquivoModel.producao_id == production_id,
            ProducaoArquivoModel.visivel_produtor.is_(True),
        )
        .order_by(ProducaoArquivoModel.created_at.desc(), ProducaoArquivoModel.id.desc())
        .all()
    )


def get_for_admin(db, production_id, file_id):
    model = db.get(ProducaoArquivoModel, file_id)
    if model is None or model.producao_id != production_id:
        raise ProducaoArquivoNotFound("Arquivo nao encontrado.")
    return model


def get_for_producer(db, file_id, producer_id):
    model = (
        db.query(ProducaoArquivoModel)
        .join(ProducaoModel, ProducaoArquivoModel.producao_id == ProducaoModel.id)
        .filter(
            ProducaoArquivoModel.id == file_id,
            ProducaoArquivoModel.visivel_produtor.is_(True),
            crud_producao.acesso_produtor(producer_id),
        )
        .first()
    )
    if model is None:
        raise ProducaoArquivoNotFound("Arquivo nao encontrado.")
    return model


def list_for_client(db, production_id, client_id):
    from models import PreviaTagJobModel
    from sqlalchemy import or_
    production = (
        db.query(ProducaoModel.id)
        .join(OrcamentoModel, ProducaoModel.orcamento_id == OrcamentoModel.id)
        .filter(
            ProducaoModel.id == production_id,
            OrcamentoModel.cliente_id == client_id,
        )
        .first()
    )
    if not production:
        raise ProducaoArquivoNotFound("Producao nao encontrada.")
    return (
        db.query(ProducaoArquivoModel)
        .outerjoin(PreviaTagJobModel, PreviaTagJobModel.arquivo_id == ProducaoArquivoModel.id)
        .filter(
            ProducaoArquivoModel.producao_id == production_id,
            or_(ProducaoArquivoModel.visivel_cliente.is_(True), PreviaTagJobModel.visivel_cliente.is_(True)),
            ProducaoArquivoModel.tipo != "comprovante",
        )
        .order_by(ProducaoArquivoModel.created_at.desc(), ProducaoArquivoModel.id.desc())
        .all()
    )


def get_for_client(db, file_id, client_id):
    from models import PreviaTagJobModel
    from sqlalchemy import or_
    model = (
        db.query(ProducaoArquivoModel)
        .outerjoin(PreviaTagJobModel, PreviaTagJobModel.arquivo_id == ProducaoArquivoModel.id)
        .join(ProducaoModel, ProducaoArquivoModel.producao_id == ProducaoModel.id)
        .join(OrcamentoModel, ProducaoModel.orcamento_id == OrcamentoModel.id)
        .filter(
            ProducaoArquivoModel.id == file_id,
            or_(ProducaoArquivoModel.visivel_cliente.is_(True), PreviaTagJobModel.visivel_cliente.is_(True)),
            ProducaoArquivoModel.tipo != "comprovante",
            OrcamentoModel.cliente_id == client_id,
        )
        .first()
    )
    if model is None:
        raise ProducaoArquivoNotFound("Arquivo nao encontrado.")
    return model


def read(model, storage=None, *, client=False):
    storage = storage or new_production_file_storage(model.tipo)
    job = getattr(model, "tag_processamento", None) if client else None
    if client and getattr(model, "original_restrito", False) and job is None:
        raise ProducaoArquivoUnavailable("Previa em processamento.")
    if job is not None and job.estado != "pronto":
        raise ProducaoArquivoUnavailable("Previa em processamento. Tente novamente em instantes.")
    key = job.object_key if job is not None else model.object_key
    checksum = job.sha256 if job is not None else model.sha256
    try:
        content = storage.read(key)
    except ProducaoArquivoStorageError as exc:
        raise ProducaoArquivoUnavailable(str(exc)) from None
    if hashlib.sha256(content).hexdigest() != checksum:
        logger.error(
            "production_file_integrity_mismatch production_id=%s file_id=%s",
            model.producao_id,
            model.id,
        )
        raise ProducaoArquivoUnavailable("Integridade do arquivo nao confirmada.")
    return content


def update_visibility(db, *, model, actor, producer, client, request_id=None):
    if model.tipo == "comprovante" and client:
        raise ProducaoArquivoConflict("Comprovantes de repasse nao podem ser visiveis ao cliente.")
    model.visivel_produtor = producer
    if model.original_restrito:
        if model.tag_processamento is None:
            raise ProducaoArquivoConflict("Processamento da previa indisponivel.")
        model.visivel_cliente = False
        model.tag_processamento.visivel_cliente = client
    else:
        model.visivel_cliente = client
    audit_service.record(
        db,
        actor=actor,
        action="production.file_visibility_changed",
        entity_type="production_file",
        entity_id=model.id,
        request_id=request_id,
    )
    from services import portal_notificacao_service

    portal_notificacao_service.arquivo_compartilhado(db, model, actor_id=getattr(actor, "id", None))
    db.commit()
    db.refresh(model)
    return model
