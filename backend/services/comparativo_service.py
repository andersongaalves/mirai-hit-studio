"""Before/after comparison of a production (Rough Mix x final).

The Admin may choose the two files; otherwise the portals pick them automatically.
Both play at the same integrated loudness, with the final (master) as reference: the
"before" gets the gain that brings its LUFS to the final's.
"""
import logging
import os
import tempfile

from models import ProducaoArquivoModel
from services import audio_tag_service, audit_service, producao_arquivo_service

logger = logging.getLogger(__name__)

MAX_GAIN_DB = 24.0


class ComparativoError(Exception):
    pass


def _audio(model):
    return bool(model) and str(model.mime_type or "").startswith(("audio/", "video/"))


def medir(db, model, storage=None):
    """Integrated loudness of the original upload, measured once and kept on the file."""
    if model is None:
        return None
    if model.lufs_integrado is not None:
        return model.lufs_integrado
    try:
        content = producao_arquivo_service.read(model, storage, versao="original")
    except producao_arquivo_service.ProducaoArquivoError:
        return None
    suffix = os.path.splitext(model.nome_exibicao or "")[1][:8] or ".audio"
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, f"audio{suffix}")
        with open(path, "wb") as handle:
            handle.write(content)
        value = audio_tag_service.medir_loudness(path)
    if value is None:
        return None
    model.lufs_integrado = round(float(value), 2)
    db.commit()
    return model.lufs_integrado


def ganho(db, antes, depois, storage=None):
    """Gain (dB) for the "before" file so it plays at the final's integrated loudness."""
    lufs_antes = medir(db, antes, storage)
    lufs_depois = medir(db, depois, storage)
    gain = None
    if lufs_antes is not None and lufs_depois is not None:
        gain = round(max(-MAX_GAIN_DB, min(MAX_GAIN_DB, lufs_depois - lufs_antes)), 1)
    return {"lufs_antes": lufs_antes, "lufs_depois": lufs_depois, "ganho_antes_db": gain}


def _file_of(db, production, file_id):
    if file_id is None:
        return None
    model = db.get(ProducaoArquivoModel, file_id)
    if model is None or model.producao_id != production.id:
        raise ComparativoError("Arquivo nao encontrado nesta producao.")
    if not _audio(model):
        raise ComparativoError("Escolha arquivos de audio para o comparativo.")
    return model


def escolha(db, production):
    """The Admin's choice, or (None, None) for automatic. Ignores files that no longer exist."""
    antes = db.get(ProducaoArquivoModel, production.comparativo_antes_arquivo_id) if production.comparativo_antes_arquivo_id else None
    depois = db.get(ProducaoArquivoModel, production.comparativo_depois_arquivo_id) if production.comparativo_depois_arquivo_id else None
    if antes is None or depois is None or antes.producao_id != production.id or depois.producao_id != production.id:
        return None, None
    return antes, depois


def definir(db, production, actor, *, antes_id, depois_id, request_id=None):
    if (antes_id is None) != (depois_id is None):
        raise ComparativoError("Escolha os dois arquivos ou volte para o automatico.")
    if antes_id is not None and antes_id == depois_id:
        raise ComparativoError("Antes e depois precisam ser arquivos diferentes.")
    antes = _file_of(db, production, antes_id)
    depois = _file_of(db, production, depois_id)
    production.comparativo_antes_arquivo_id = getattr(antes, "id", None)
    production.comparativo_depois_arquivo_id = getattr(depois, "id", None)
    audit_service.record(
        db, actor=actor, action="production.comparison_set", entity_type="production", entity_id=production.id,
        metadata={"antes": production.comparativo_antes_arquivo_id, "depois": production.comparativo_depois_arquivo_id},
        request_id=request_id,
    )
    db.commit()
    return antes, depois


def resposta(db, production, *, antes=None, depois=None, storage=None, permitido=None):
    """The chosen pair (manual), or the pair the portal picked, with the loudness match.

    permitido(file) -> bool hides a manual choice the viewer cannot see (client portal).
    """
    manual_antes, manual_depois = escolha(db, production)
    if permitido is not None and manual_antes is not None and not (permitido(manual_antes) and permitido(manual_depois)):
        manual_antes = manual_depois = None
    origem = "manual" if manual_antes is not None else "automatica"
    if manual_antes is not None:
        antes, depois = manual_antes, manual_depois
    result = {
        "origem": origem,
        "antes_arquivo_id": getattr(manual_antes, "id", None),
        "depois_arquivo_id": getattr(manual_depois, "id", None),
        "lufs_antes": None, "lufs_depois": None, "ganho_antes_db": None,
    }
    if _audio(antes) and _audio(depois) and antes.id != depois.id:
        try:
            result.update(ganho(db, antes, depois, storage))
        except Exception:  # noqa: BLE001 - loudness is a convenience; the comparison still plays.
            db.rollback()
            logger.warning("comparison_loudness_failed production_id=%s", production.id)
    return result
