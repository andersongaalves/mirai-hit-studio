import hashlib
import logging
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.orcamento import OrcamentoModel
from models.portal_produtor import ProducaoArquivoModel
from models.producao import ProducaoModel
from services import audit_service
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
):
    _validate_upload(data, mime_type, file_type)
    if file_type == "comprovante" and visible_to_client:
        raise ProducaoArquivoError("Comprovantes de repasse nao podem ser visiveis ao cliente.")
    group_id, version, previous = _version(
        db,
        production.id,
        file_type,
        replaces_id,
        replacement_actor_id,
    )
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
        visivel_cliente=visible_to_client,
    )
    try:
        db.add(model)
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action="production.file_uploaded",
            entity_type="production_file",
            entity_id=model.id,
            request_id=request_id,
        )
        db.commit()
        db.refresh(model)
        return model
    except IntegrityError:
        db.rollback()
        try:
            storage.delete(object_key)
        except ProducaoArquivoStorageError:
            logger.error(
                "production_file_compensation_failed production_id=%s",
                production.id,
            )
        raise ProducaoArquivoConflict("Conflito ao registrar a nova versao.") from None
    except Exception:
        db.rollback()
        try:
            storage.delete(object_key)
        except ProducaoArquivoStorageError:
            logger.error(
                "production_file_compensation_failed production_id=%s",
                production.id,
            )
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
            ProducaoModel.produtor_id == producer_id,
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
            ProducaoModel.produtor_id == producer_id,
        )
        .first()
    )
    if model is None:
        raise ProducaoArquivoNotFound("Arquivo nao encontrado.")
    return model


def list_for_client(db, production_id, client_id):
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
        .filter(
            ProducaoArquivoModel.producao_id == production_id,
            ProducaoArquivoModel.visivel_cliente.is_(True),
            ProducaoArquivoModel.tipo != "comprovante",
        )
        .order_by(ProducaoArquivoModel.created_at.desc(), ProducaoArquivoModel.id.desc())
        .all()
    )


def get_for_client(db, file_id, client_id):
    model = (
        db.query(ProducaoArquivoModel)
        .join(ProducaoModel, ProducaoArquivoModel.producao_id == ProducaoModel.id)
        .join(OrcamentoModel, ProducaoModel.orcamento_id == OrcamentoModel.id)
        .filter(
            ProducaoArquivoModel.id == file_id,
            ProducaoArquivoModel.visivel_cliente.is_(True),
            ProducaoArquivoModel.tipo != "comprovante",
            OrcamentoModel.cliente_id == client_id,
        )
        .first()
    )
    if model is None:
        raise ProducaoArquivoNotFound("Arquivo nao encontrado.")
    return model


def read(model, storage=None):
    storage = storage or new_production_file_storage(model.tipo)
    try:
        content = storage.read(model.object_key)
    except ProducaoArquivoStorageError as exc:
        raise ProducaoArquivoUnavailable(str(exc)) from None
    if hashlib.sha256(content).hexdigest() != model.sha256:
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
    model.visivel_cliente = client
    audit_service.record(
        db,
        actor=actor,
        action="production.file_visibility_changed",
        entity_type="production_file",
        entity_id=model.id,
        request_id=request_id,
    )
    db.commit()
    db.refresh(model)
    return model
