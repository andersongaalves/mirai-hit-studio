"""Coordinate persisted proposal, renderer and storage; no sending/status changes."""
from datetime import datetime, timezone

from crud import crud_proposta as crud
from services import proposta_service, pdf_service
from services.documento_storage import LocalDocumentoStorage


def _carregar(db, proposta_id, bloquear=False):
    model = crud.buscar_por_id(db, proposta_id, bloquear=bloquear)
    if model is None:
        raise proposta_service.PropostaNaoEncontrada("Proposta nao encontrada.")
    return model


def _html(model, final=False):
    proposta = proposta_service._resposta(model)
    produtor = model.produtor.username if model.produtor else "Nao definido"
    return pdf_service.renderizar_html(proposta, produtor, final=final)


def preview(db, proposta_id):
    return _html(_carregar(db, proposta_id))


def gerar_documento(db, proposta_id):
    try:
        # Same row lock as PATCH: one consistent saved version throughout generation.
        model = _carregar(db, proposta_id, bloquear=True)
        gerar_sem_commit(db, model)
        resposta = proposta_service._resposta(model)
        db.commit()
        return resposta
    except Exception:
        db.rollback()
        raise


def gerar_sem_commit(db, model):
    storage = LocalDocumentoStorage()
    data = pdf_service.gerar_pdf(_html(model, final=True))
    key = storage.salvar(data, model.id, model.versao)
    crud.atualizar(db, model, {"pdf_path": key, "gerada_em": datetime.now(timezone.utc)})
    return data


def obter_documento(db, proposta_id):
    model = _carregar(db, proposta_id)
    if not model.pdf_path or not model.gerada_em:
        raise proposta_service.PropostaNaoEncontrada("Gere o PDF da versao atual da proposta.")
    return LocalDocumentoStorage().ler(model.pdf_path), f"proposta-{model.id}-v{model.versao}.pdf"
