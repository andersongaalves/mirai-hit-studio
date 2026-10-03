from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from models.portal_produtor import ProducaoArquivoModel, RepasseProdutorModel
from models.producao import ProducaoModel
from models.usuario import UsuarioModel
from services import audit_service


class RepasseError(Exception):
    pass


class RepasseNotFound(RepasseError):
    pass


class RepasseConflict(RepasseError):
    pass


def _response(repasse, production_title=None, producer_name=None):
    return {
        "id": repasse.id,
        "producao_id": repasse.producao_id,
        "producao_titulo": production_title,
        "produtor_id": repasse.produtor_id,
        "produtor_nome": producer_name,
        "valor_combinado": repasse.valor_combinado,
        "moeda": repasse.moeda,
        "status": repasse.status,
        "liberado_em": repasse.liberado_em,
        "pago_em": repasse.pago_em,
        "referencia_pagamento": repasse.referencia_pagamento,
        "comprovante_arquivo_id": repasse.comprovante_arquivo_id,
        "created_at": repasse.created_at,
        "updated_at": repasse.updated_at,
    }


def _query(db: Session):
    return (
        db.query(RepasseProdutorModel, ProducaoModel.titulo, UsuarioModel.username)
        .join(ProducaoModel, RepasseProdutorModel.producao_id == ProducaoModel.id)
        .join(UsuarioModel, RepasseProdutorModel.produtor_id == UsuarioModel.id)
    )


def get_admin(db, production_id):
    row = _query(db).filter(RepasseProdutorModel.producao_id == production_id).first()
    if not row:
        return None
    repasse, title, producer = row
    return _response(repasse, title, producer)


def list_for_producer(db, producer_id):
    rows = (
        _query(db)
        .filter(RepasseProdutorModel.produtor_id == producer_id)
        .order_by(RepasseProdutorModel.id.desc())
        .all()
    )
    return [_response(repasse, title, producer) for repasse, title, producer in rows]


def get_for_producer(db, payout_id, producer_id):
    model = (
        db.query(RepasseProdutorModel)
        .filter(
            RepasseProdutorModel.id == payout_id,
            RepasseProdutorModel.produtor_id == producer_id,
        )
        .first()
    )
    if model is None:
        raise RepasseNotFound("Repasse nao encontrado.")
    return model


def _audit_amount(db, actor, repasse, old_amount, request_id):
    audit_service.record(
        db,
        actor=actor,
        action="producer_payout.amount_changed",
        entity_type="producer_payout",
        entity_id=repasse.id,
        metadata={
            "old_amount": str(old_amount) if old_amount is not None else None,
            "new_amount": str(repasse.valor_combinado),
        },
        request_id=request_id,
    )


def define(db, *, production_id, amount: Decimal, actor, request_id=None):
    production = db.get(ProducaoModel, production_id)
    if production is None:
        raise RepasseNotFound("Producao nao encontrada.")
    producer = db.get(UsuarioModel, production.produtor_id) if production.produtor_id else None
    if producer is None or producer.role != "produtor":
        raise RepasseConflict("A producao precisa de um produtor valido.")

    repasse = (
        db.query(RepasseProdutorModel)
        .filter(RepasseProdutorModel.producao_id == production_id)
        .first()
    )
    if repasse is None:
        repasse = RepasseProdutorModel(
            producao_id=production_id,
            produtor_id=producer.id,
            valor_combinado=amount,
            moeda="BRL",
            status="definido",
        )
        db.add(repasse)
        db.flush()
        old_amount = None
    else:
        if repasse.status != "definido":
            raise RepasseConflict("Use a correcao auditada para alterar este repasse.")
        old_amount = repasse.valor_combinado
        repasse.valor_combinado = amount
        db.flush()
    _audit_amount(db, actor, repasse, old_amount, request_id)
    db.commit()
    return get_admin(db, production_id)


def release(db, *, production_id, actor, request_id=None):
    repasse = db.query(RepasseProdutorModel).filter_by(producao_id=production_id).first()
    if repasse is None:
        raise RepasseNotFound("Repasse nao encontrado.")
    if repasse.status != "definido":
        raise RepasseConflict("Somente repasses definidos podem ser liberados.")
    repasse.status = "liberado"
    repasse.liberado_em = datetime.now(timezone.utc)
    audit_service.record(
        db,
        actor=actor,
        action="producer_payout.released",
        entity_type="producer_payout",
        entity_id=repasse.id,
        metadata={"old_status": "definido", "new_status": "liberado"},
        request_id=request_id,
    )
    db.commit()
    return get_admin(db, production_id)


def _receipt(db, production_id, file_id):
    if file_id is None:
        return None
    model = db.get(ProducaoArquivoModel, file_id)
    if (
        model is None
        or model.producao_id != production_id
        or model.tipo != "comprovante"
    ):
        raise RepasseConflict("Comprovante invalido para esta producao.")
    return model


def mark_paid(
    db,
    *,
    production_id,
    actor,
    reference=None,
    receipt_id=None,
    request_id=None,
):
    repasse = db.query(RepasseProdutorModel).filter_by(producao_id=production_id).first()
    if repasse is None:
        raise RepasseNotFound("Repasse nao encontrado.")
    if repasse.status != "liberado":
        raise RepasseConflict("Somente repasses liberados podem ser marcados como pagos.")
    receipt = _receipt(db, production_id, receipt_id)
    if receipt:
        receipt.visivel_produtor = True
    repasse.status = "pago"
    repasse.pago_em = datetime.now(timezone.utc)
    repasse.referencia_pagamento = reference
    repasse.comprovante_arquivo_id = receipt.id if receipt else None
    audit_service.record(
        db,
        actor=actor,
        action="producer_payout.paid",
        entity_type="producer_payout",
        entity_id=repasse.id,
        metadata={"old_status": "liberado", "new_status": "pago"},
        request_id=request_id,
    )
    db.commit()
    return get_admin(db, production_id)


def correct(
    db,
    *,
    production_id,
    actor,
    fields,
    request_id=None,
):
    repasse = db.query(RepasseProdutorModel).filter_by(producao_id=production_id).first()
    if repasse is None:
        raise RepasseNotFound("Repasse nao encontrado.")
    changed = False
    old_amount = repasse.valor_combinado
    metadata = {}
    if "valor_combinado" in fields and fields["valor_combinado"] is not None:
        repasse.valor_combinado = fields["valor_combinado"]
        metadata.update(
            old_amount=str(old_amount),
            new_amount=str(repasse.valor_combinado),
        )
        changed = True
    if "referencia_pagamento" in fields:
        if repasse.status != "pago":
            raise RepasseConflict("Referencia so pode ser corrigida apos o pagamento.")
        repasse.referencia_pagamento = fields["referencia_pagamento"]
        metadata["reference_changed"] = True
        changed = True
    if "comprovante_arquivo_id" in fields:
        if repasse.status != "pago":
            raise RepasseConflict("Comprovante so pode ser corrigido apos o pagamento.")
        receipt = _receipt(db, production_id, fields["comprovante_arquivo_id"])
        if receipt:
            receipt.visivel_produtor = True
        repasse.comprovante_arquivo_id = receipt.id if receipt else None
        metadata["receipt_changed"] = True
        changed = True
    if not changed:
        raise RepasseConflict("Nenhuma correcao valida foi informada.")
    db.flush()
    audit_service.record(
        db,
        actor=actor,
        action="producer_payout.corrected",
        entity_type="producer_payout",
        entity_id=repasse.id,
        metadata=metadata,
        request_id=request_id,
    )
    db.commit()
    return get_admin(db, production_id)
