"""Coordinate persisted proposal, renderer and storage; no sending/status changes."""
from datetime import datetime, timezone
from hashlib import sha256

from crud import crud_proposta as crud
from services import proposta_service, pdf_service
from services.documento_storage import novo_documento_storage, storage_para_referencia


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
        if model.enviada_em and model.pdf_path and model.pdf_sha256:
            _ler_validado(model)
        else:
            gerar_sem_commit(db, model)
        resposta = proposta_service._resposta(model)
        db.commit()
        return resposta
    except Exception:
        db.rollback()
        raise


def gerar_sem_commit(db, model):
    if model.enviada_em and model.pdf_path and model.pdf_sha256:
        return _ler_validado(model)
    data = pdf_service.gerar_pdf(_html(model, final=True))
    return persistir_bytes_sem_commit(db, model, data)


def persistir_bytes_sem_commit(db, model, data):
    digest = sha256(data).hexdigest()
    key = novo_documento_storage().salvar(data, model.id, model.versao)
    crud.atualizar(db, model, {
        "pdf_path": key,
        "pdf_sha256": digest,
        "gerada_em": datetime.now(timezone.utc),
    })
    return data


def _ler_validado(model):
    data = storage_para_referencia(model.pdf_path).ler(model.pdf_path)
    if model.pdf_sha256 and sha256(data).hexdigest() != model.pdf_sha256:
        raise proposta_service.PropostaConflito("Integridade do PDF armazenado nao confirmada.")
    return data


def ler_atual(model):
    return _ler_validado(model)


def obter_documento(db, proposta_id):
    model = _carregar(db, proposta_id)
    if not model.pdf_path or not model.gerada_em:
        raise proposta_service.PropostaNaoEncontrada("Gere o PDF da versao atual da proposta.")
    return _ler_validado(model), f"proposta-{model.id}-v{model.versao}.pdf"
