"""Admin file manager: every stored file in one place, by folder and type.

Built from the records that own each object (so every file has a context and a reason
when it cannot be deleted), never by listing buckets blindly.
"""
import logging
import mimetypes
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException
from models import (
    AudioTagModel,
    AudioTagPerfilModel,
    BeatLicencaModel,
    BeatModel,
    PreviaTagJobModel,
    ProducaoArquivoModel,
    ProducaoEntregaFinalModel,
    ProducaoModel,
    ProjetoModel,
    PropostaModel,
    RepasseProdutorModel,
)
from services import audit_service
from sqlalchemy import select

logger = logging.getLogger(__name__)

CATEGORIAS = ("audio", "pdf", "imagem", "compactado", "outro")


def categoria(mime, nome=""):
    mime = (mime or "").lower()
    if not mime and nome:
        mime = (mimetypes.guess_type(nome)[0] or "").lower()
    if mime.startswith(("audio/", "video/")):
        return "audio"
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("image/"):
        return "imagem"
    if mime in ("application/zip", "application/vnd.rar", "application/x-rar-compressed", "application/x-zip-compressed"):
        return "compactado"
    return "outro"


SERVICOS = {
    "r2": "Cloudflare R2",
    "supabase": "Supabase Storage",
    "cloudinary": "Cloudinary",
    "memory": "Memória (teste)",
    "legacy_document": "Servidor (local)",
    "local": "Servidor (local)",
}
BANCO = "Banco de dados"


def servico_de(key):
    """Storage service that holds an object, from the reference stored for it."""
    if not key:
        return "Desconhecido"
    if key.startswith(("http://", "https://")):
        host = (urlsplit(key).hostname or "").lower()
        if "cloudinary" in host:
            return "Cloudinary"
        if "supabase" in host:
            return "Supabase Storage"
        if host.endswith(("r2.dev", "r2.cloudflarestorage.com")):
            return "Cloudflare R2"
        return "Link externo"
    if "://" not in key:
        # Bare keys are the legacy Supabase bucket layout.
        return "Supabase Storage"
    return SERVICOS.get(key.split("://", 1)[0], key.split("://", 1)[0])


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _entry(ref, pasta, nome, mime, tamanho, criado_em, *, contexto, funcao, servico, protegido=None, baixar="api",
           url=None, miniatura=None, detalhes=None):
    mime = mime or (mimetypes.guess_type(nome or "")[0] or "application/octet-stream")
    if miniatura is None and url and categoria(mime, nome) == "imagem":
        miniatura = url
    return {
        "ref": ref,
        "pasta": pasta,
        "nome": nome,
        "mime_type": mime,
        "categoria": categoria(mime, nome),
        "tamanho_bytes": tamanho,
        "criado_em": _iso(criado_em),
        "contexto": contexto,
        "funcao": funcao,
        "servico": servico,
        "miniatura": miniatura,
        "protegido": bool(protegido),
        "motivo_protecao": protegido or None,
        "baixar": baixar,
        "url": url,
        "detalhes": detalhes or {},
    }


def _receipt_ids(db):
    from models.repasse_etapa import RepasseEtapaPagamentoModel

    ids = {row for row in db.scalars(select(RepasseProdutorModel.comprovante_arquivo_id)) if row}
    ids |= {row for row in db.scalars(select(RepasseEtapaPagamentoModel.comprovante_arquivo_id)) if row}
    return ids


def protecao_arquivo(model, *, replaced, attached, delivery, receipts, production_status):
    """Why a production file must stay (None = it can be deleted)."""
    if model.id in delivery:
        return "Faz parte de uma entrega final: exclua a entrega inteira pelo portal do produtor."
    if model.id in receipts:
        return "É o comprovante de um repasse registrado."
    if model.id in attached:
        return "Está anexado a uma mensagem da produção (histórico)."
    if model.id in replaced:
        return "Tem uma versão mais nova: as versões anteriores formam o histórico."
    if model.tipo == "entrega" and production_status == "entregue":
        return "Arquivo final de uma produção já entregue ao cliente."
    return None


FUNCOES_PRODUCAO = {
    "previa": "Prévia",
    "entrega": "Entrega final",
    "material": "Material do cliente",
    "referencia": "Referência",
    "comprovante": "Comprovante de repasse",
}


def _production_files(db):
    from models import ProducaoMensagemModel

    productions = {row.id: row for row in db.scalars(select(ProducaoModel))}
    files = db.scalars(select(ProducaoArquivoModel).order_by(ProducaoArquivoModel.created_at.desc())).all()
    replaced = {row.substitui_arquivo_id for row in files if row.substitui_arquivo_id}
    attached = {row for row in db.scalars(select(ProducaoMensagemModel.arquivo_id)) if row}
    delivery = set()
    for row in db.scalars(select(ProducaoEntregaFinalModel)):
        delivery |= {item for item in (row.arquivo_principal_id, row.wav_arquivo_id, row.multitrack_arquivo_id, row.licenca_arquivo_id) if item}
    receipts = _receipt_ids(db)
    entries = []
    for model in files:
        production = productions.get(model.producao_id)
        label = f"#{model.producao_id} {production.titulo}" if production else f"#{model.producao_id}"
        pasta = ["Produções", label, {"previa": "Prévias", "entrega": "Entregas", "material": "Materiais",
                                      "referencia": "Referências", "comprovante": "Comprovantes"}.get(model.tipo, model.tipo)]
        protected = protecao_arquivo(model, replaced=replaced, attached=attached, delivery=delivery,
                                     receipts=receipts, production_status=getattr(production, "status", None))
        contexto = {"tipo": "producao", "id": model.producao_id, "titulo": getattr(production, "titulo", "")}
        detalhes = {
            "tipo": model.tipo, "versao": model.versao, "etapa_id": model.etapa_id, "sha256": model.sha256,
            "visivel_produtor": model.visivel_produtor, "visivel_cliente": model.visivel_cliente,
            "observacao": model.observacao, "comprimido_em": _iso(getattr(model, "comprimido_em", None)),
            "lufs_integrado": getattr(model, "lufs_integrado", None),
        }
        entries.append(_entry(f"arq:{model.id}", pasta, model.nome_exibicao, model.mime_type, model.tamanho_bytes,
                              model.created_at, contexto=contexto, funcao=FUNCOES_PRODUCAO.get(model.tipo, model.tipo),
                              servico=servico_de(model.object_key), protegido=protected, detalhes=detalhes))
        job = model.tag_processamento
        if job is not None and job.object_key:
            entries.append(_entry(
                f"tag:{model.id}", pasta, f"{model.nome_exibicao} (versão com tag)", "audio/mpeg", job.tamanho_bytes,
                job.concluido_em or model.created_at, contexto=contexto, funcao="Prévia com tag",
                servico=servico_de(job.object_key), protegido="Versão com tag de uma prévia: sai junto com a prévia (ou gere de novo pelo Admin).",
                detalhes={"tipo": "previa_com_tag", "sha256": job.sha256, "estado": job.estado, "tag_id": job.tag_id},
            ))
    return entries


FUNCOES_BEAT = {
    "original": "Original do beat",
    "previa": "Prévia do beat (com tag)",
    "wav": "WAV do beat",
    "multitrack": "Multitrack do beat",
}


def _beat_files(db):
    sold = {row for row in db.scalars(select(BeatLicencaModel.beat_id))}
    entries = []
    for beat in db.scalars(select(BeatModel).order_by(BeatModel.created_at.desc())):
        pasta = ["Beats", f"#{beat.id} {beat.titulo}"]
        contexto = {"tipo": "beat", "id": beat.id, "titulo": beat.titulo}
        reason = ("Beat com pedido ou venda: os arquivos ficam para os contratos." if beat.id in sold or beat.status == "vendido"
                  else "Arquivo de um beat: exclua o beat inteiro (o produtor pode, pelo portal).")
        cover = beat.capa_url or None
        slots = [
            ("original", "Original (sem tag)", beat.original_ref, beat.mime_type or "audio/mpeg", beat.tamanho_bytes),
            ("previa", "Prévia com tag (MP3)", beat.mp3_ref or beat.preview_ref, "audio/mpeg", None),
            ("wav", "WAV", beat.wav_ref, "audio/wav", None),
            ("multitrack", "Multitrack", beat.multitrack_ref, beat.multitrack_mime or "application/zip", None),
        ]
        for slot, label, ref, mime, size in slots:
            if ref and not (slot == "previa" and ref == beat.original_ref):
                entries.append(_entry(f"beat:{beat.id}:{slot}", pasta, f"{beat.titulo} · {label}", mime, size,
                                      beat.created_at, contexto=contexto, funcao=FUNCOES_BEAT[slot],
                                      servico=servico_de(ref), protegido=reason, miniatura=cover,
                                      detalhes={"status": beat.status, "slot": slot}))
        if beat.multitrack_url:
            entries.append(_entry(f"beat:{beat.id}:multitrack_link", pasta, f"{beat.titulo} · Multitrack (link externo)", "", None,
                                  beat.created_at, contexto=contexto, funcao="Multitrack do beat",
                                  servico="Link externo", protegido="Link externo: fica no serviço do produtor.",
                                  baixar="url", url=beat.multitrack_url, miniatura=cover))
        if beat.capa_url:
            entries.append(_entry(f"beat:{beat.id}:capa", pasta, f"{beat.titulo} · Capa", "image/jpeg", None, beat.created_at,
                                  contexto=contexto, funcao="Capa do beat", servico=servico_de(beat.capa_url),
                                  protegido=reason, baixar="url", url=beat.capa_url))
    return entries


def _portfolio_files(db):
    from services.portfolio_audio_storage import new_portfolio_audio_storage

    storage = None
    entries = []
    for project in db.scalars(select(ProjetoModel).order_by(ProjetoModel.id.desc())):
        pasta = ["Portfólio", f"#{project.id} {project.titulo}"]
        contexto = {"tipo": "projeto", "id": project.id, "titulo": project.titulo}
        reason = "Em uso no portfólio público: troque ou remova pelo editor do projeto."
        for slot, label, key in (("antes", "Áudio antes", project.audio_before_key), ("depois", "Áudio depois", project.audio_after_key)):
            if not key:
                continue
            try:
                storage = storage or new_portfolio_audio_storage()
                url = storage.public_url(key)
            except Exception:  # noqa: BLE001 - storage not configured here; the entry still lists.
                url = None
            entries.append(_entry(f"proj:{project.id}:{slot}", pasta, f"{project.titulo} · {label}", "audio/mpeg", None, None,
                                  contexto=contexto, funcao="Áudio do portfólio", servico="Supabase Storage",
                                  protegido=reason, baixar="url", url=url, miniatura=project.link_capa or None))
        if project.link_capa:
            entries.append(_entry(f"proj:{project.id}:capa", pasta, f"{project.titulo} · Capa", "image/jpeg", None, None,
                                  contexto=contexto, funcao="Capa do portfólio", servico=servico_de(project.link_capa),
                                  protegido=reason, baixar="url", url=project.link_capa))
    return entries


def _documents(db):
    entries = []
    for proposal in db.scalars(select(PropostaModel).where(PropostaModel.pdf_path.is_not(None)).order_by(PropostaModel.id.desc())):
        numero = getattr(proposal, "numero", None) or f"#{proposal.id}"
        entries.append(_entry(f"doc:{proposal.id}", ["Documentos", "Propostas"], f"Proposta {numero}.pdf", "application/pdf",
                              None, getattr(proposal, "updated_at", None) or getattr(proposal, "created_at", None),
                              contexto={"tipo": "proposta", "id": proposal.id, "titulo": str(numero)},
                              funcao="Proposta (PDF)",
                              servico=servico_de(proposal.pdf_path) if "://" in proposal.pdf_path else "Servidor (local)",
                              protegido="Documento comercial enviado ao cliente."))
    return entries


def _audio_tags(db):
    in_use = {row for row in db.scalars(select(AudioTagPerfilModel.tag_id)) if row}
    in_use |= {row for row in db.scalars(select(PreviaTagJobModel.tag_id)) if row}
    entries = []
    for tag in db.scalars(select(AudioTagModel).order_by(AudioTagModel.created_at.desc())):
        entries.append(_entry(f"audiotag:{tag.id}", ["Tags de áudio"], tag.nome, tag.mime_type, len(tag.conteudo or b""),
                              tag.created_at, contexto={"tipo": "tag", "id": tag.id, "titulo": tag.nome},
                              funcao="Tag de áudio", servico=BANCO,
                              protegido="Tag em uso (perfil atual ou prévias geradas com ela)." if tag.id in in_use else None,
                              detalhes={"duracao_s": tag.duracao, "sha256": tag.sha256, "usuario_id": tag.usuario_id}))
    return entries


def indice(db):
    entries = []
    for source in (_production_files, _beat_files, _portfolio_files, _documents, _audio_tags):
        try:
            entries.extend(source(db))
        except Exception:  # noqa: BLE001 - one unavailable source must not hide the others.
            db.rollback()
            logger.warning("file_manager_source_failed source=%s", source.__name__)
    return entries


def _facet(entries, field):
    counts = {}
    for entry in entries:
        item = counts.setdefault(entry[field], {"valor": entry[field], "arquivos": 0, "tamanho_bytes": 0})
        item["arquivos"] += 1
        item["tamanho_bytes"] += entry["tamanho_bytes"] or 0
    return sorted(counts.values(), key=lambda item: (-item["arquivos"], item["valor"]))


def listar(db, *, pasta=None, categoria_filtro=None, funcao=None, servico=None, protegido=None, busca=None,
           ordem="recentes"):
    entries = indice(db)
    folders = {}
    for entry in entries:
        for depth in range(1, len(entry["pasta"]) + 1):
            key = "/".join(entry["pasta"][:depth])
            item = folders.setdefault(key, {"caminho": key, "nome": entry["pasta"][depth - 1], "nivel": depth,
                                            "arquivos": 0, "tamanho_bytes": 0})
            item["arquivos"] += 1
            item["tamanho_bytes"] += entry["tamanho_bytes"] or 0
    totals = {name: {"arquivos": 0, "tamanho_bytes": 0} for name in CATEGORIAS}
    for entry in entries:
        totals[entry["categoria"]]["arquivos"] += 1
        totals[entry["categoria"]]["tamanho_bytes"] += entry["tamanho_bytes"] or 0
    selected = entries
    if pasta:
        selected = [entry for entry in selected if "/".join(entry["pasta"]).startswith(pasta)
                    and ("/".join(entry["pasta"]) == pasta or "/".join(entry["pasta"]).startswith(pasta + "/"))]
    if categoria_filtro:
        selected = [entry for entry in selected if entry["categoria"] == categoria_filtro]
    if funcao:
        selected = [entry for entry in selected if entry["funcao"] == funcao]
    if servico:
        selected = [entry for entry in selected if entry["servico"] == servico]
    if protegido is not None:
        selected = [entry for entry in selected if entry["protegido"] is bool(protegido)]
    if busca:
        words = busca.lower().split()
        selected = [entry for entry in selected
                    if all(word in f"{entry['nome']} {entry['contexto'].get('titulo', '')} {entry['funcao']}".lower()
                           for word in words)]
    if ordem == "maiores":
        selected = sorted(selected, key=lambda entry: entry["tamanho_bytes"] or 0, reverse=True)
    elif ordem == "nome":
        selected = sorted(selected, key=lambda entry: entry["nome"].lower())
    elif ordem == "antigos":
        selected = sorted(selected, key=lambda entry: entry["criado_em"] or "")
    else:
        selected = sorted(selected, key=lambda entry: entry["criado_em"] or "", reverse=True)
    return {
        "arquivos": selected,
        "pastas": sorted(folders.values(), key=lambda item: item["caminho"]),
        "totais": totals,
        "funcoes": _facet(entries, "funcao"),
        "servicos": _facet(entries, "servico"),
        "total": {"arquivos": len(entries), "tamanho_bytes": sum(entry["tamanho_bytes"] or 0 for entry in entries)},
        "compressao": compressao_resumo(db),
    }


def _find(db, ref):
    try:
        kind, *rest = ref.split(":")
    except ValueError:
        raise HTTPException(404, "Arquivo nao encontrado.") from None
    for entry in indice(db):
        if entry["ref"] == ref:
            return kind, rest, entry
    raise HTTPException(404, "Arquivo nao encontrado.")


def conteudo(db, ref):
    """(bytes, filename, mime) or {"url": ...} for files that live behind a public link."""
    from services import producao_arquivo_service
    from services.producao_arquivo_storage import (
        ProducaoArquivoStorageError,
        new_production_file_storage,
    )

    kind, rest, entry = _find(db, ref)
    if entry["baixar"] == "url":
        if not entry["url"]:
            raise HTTPException(409, "Link indisponivel para este arquivo.")
        return {"url": entry["url"]}
    try:
        if kind in ("arq", "tag"):
            model = db.get(ProducaoArquivoModel, int(rest[0]))
            data = producao_arquivo_service.read(model, versao="processada" if kind == "tag" else "original")
            name = model.nome_exibicao if kind == "arq" else f"{model.nome_exibicao.rsplit('.', 1)[0]}-com-tag.mp3"
            return data, name, entry["mime_type"]
        if kind == "beat":
            beat = db.get(BeatModel, int(rest[0]))
            ref_key = {"original": beat.original_ref, "previa": beat.mp3_ref or beat.preview_ref,
                       "wav": beat.wav_ref, "multitrack": beat.multitrack_ref}[rest[1]]
            data = new_production_file_storage("previa").read(ref_key)
            extension = {"original": "mp3", "previa": "mp3", "wav": "wav", "multitrack": "zip"}[rest[1]]
            return data, f"{beat.titulo}-{rest[1]}.{extension}", entry["mime_type"]
        if kind == "doc":
            from services.documento_storage import storage_para_referencia

            proposal = db.get(PropostaModel, int(rest[0]))
            return storage_para_referencia(proposal.pdf_path).ler(proposal.pdf_path), entry["nome"], "application/pdf"
        if kind == "audiotag":
            tag = db.get(AudioTagModel, int(rest[0]))
            return bytes(tag.conteudo), tag.nome, tag.mime_type
    except (producao_arquivo_service.ProducaoArquivoError, ProducaoArquivoStorageError):
        raise HTTPException(503, "Arquivo indisponivel no armazenamento agora.") from None
    except Exception:  # noqa: BLE001 - provider errors surface as unavailable.
        logger.warning("file_manager_read_failed ref=%s", ref)
        raise HTTPException(503, "Arquivo indisponivel no armazenamento agora.") from None
    raise HTTPException(404, "Arquivo nao encontrado.")


def excluir(db, ref, actor, motivo, request_id=None):
    """Deletes what can go; protected files explain why and stay."""
    from services import producao_arquivo_service

    motivo = (motivo or "").strip()
    if len(motivo) < 3:
        raise HTTPException(422, "Informe o motivo da exclusao.")
    kind, rest, entry = _find(db, ref)
    if entry["protegido"]:
        raise HTTPException(409, entry["motivo_protecao"])
    if kind == "arq":
        producao_arquivo_service.delete_for_admin(db, file_id=int(rest[0]), actor=actor, motivo=motivo, request_id=request_id)
        return
    if kind == "audiotag":
        tag = db.get(AudioTagModel, int(rest[0]))
        audit_service.record(db, actor=actor, action="file_manager.audio_tag_deleted", entity_type="audio_tag",
                             entity_id=tag.id, metadata={"motivo": motivo}, request_id=request_id)
        db.delete(tag)
        db.commit()
        return
    raise HTTPException(409, "Este arquivo nao pode ser excluido por aqui.")


# ---------- Delivered productions: previews compressed to save storage ----------

PREVIEW_BITRATE = "96k"


def compressao_resumo(db):
    rows = db.execute(
        select(ProducaoArquivoModel.comprimido_em, ProducaoArquivoModel.tamanho_bytes)
        .join(ProducaoModel, ProducaoArquivoModel.producao_id == ProducaoModel.id)
        .where(ProducaoArquivoModel.tipo == "previa", ProducaoModel.status == "entregue")
    ).all()
    return {
        "previas_entregues": len(rows),
        "comprimidas": sum(1 for done, _ in rows if done is not None),
        "pendentes": sum(1 for done, _ in rows if done is None),
        "bitrate": PREVIEW_BITRATE,
    }


def _transcode(data):
    import os
    import subprocess
    import tempfile

    from imageio_ffmpeg import get_ffmpeg_exe
    from services.audio_tag_service import _baixa_prioridade

    with tempfile.TemporaryDirectory() as directory:
        source = os.path.join(directory, "in")
        target = os.path.join(directory, "out.mp3")
        with open(source, "wb") as handle:
            handle.write(data)
        result = subprocess.run([
            get_ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "1",
            "-protocol_whitelist", "file,pipe", "-i", source, "-vn", "-codec:a", "libmp3lame",
            "-b:a", PREVIEW_BITRATE, "-f", "mp3", target,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300, check=False,
            preexec_fn=_baixa_prioridade if os.name == "posix" else None)
        if result.returncode != 0:
            raise RuntimeError("preview_transcode_failed")
        with open(target, "rb") as handle:
            return handle.read()


def comprimir_uma(session_factory, *, storage=None, transcoder=None):
    """Compress one preview of a delivered production (original and tagged version) to MP3
    96 kbps, replacing the stored objects. Irreversible by design (the production is closed)."""
    import hashlib

    from services import producao_arquivo_service
    from services.producao_arquivo_storage import new_production_file_storage

    transcoder = transcoder or _transcode
    old_keys = []
    with session_factory() as db:
        model = db.scalar(
            select(ProducaoArquivoModel)
            .join(ProducaoModel, ProducaoArquivoModel.producao_id == ProducaoModel.id)
            .where(ProducaoArquivoModel.tipo == "previa", ProducaoModel.status == "entregue",
                   ProducaoArquivoModel.comprimido_em.is_(None))
            .order_by(ProducaoArquivoModel.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if model is None:
            return False
        provider = storage or new_production_file_storage("previa")
        saved = []
        try:
            if str(model.mime_type or "").startswith("audio/"):
                original = producao_arquivo_service.read(model, provider, versao="original")
                smaller = transcoder(original)
                if smaller and len(smaller) < len(original):
                    key = provider.save(smaller, "audio/mpeg")
                    saved.append(key)
                    old_keys.append(model.object_key)
                    model.object_key, model.sha256, model.tamanho_bytes = key, hashlib.sha256(smaller).hexdigest(), len(smaller)
                    model.mime_type = "audio/mpeg"
                    base = model.nome_exibicao.rsplit(".", 1)[0] if "." in model.nome_exibicao else model.nome_exibicao
                    model.nome_exibicao = f"{base}.mp3"[:180]
                job = model.tag_processamento
                if job is not None and job.estado == "pronto" and job.object_key:
                    tagged = producao_arquivo_service.read(model, provider, versao="processada")
                    smaller_tagged = transcoder(tagged)
                    if smaller_tagged and len(smaller_tagged) < len(tagged):
                        key = provider.save(smaller_tagged, "audio/mpeg")
                        saved.append(key)
                        old_keys.append(job.object_key)
                        job.object_key, job.sha256, job.tamanho_bytes = key, hashlib.sha256(smaller_tagged).hexdigest(), len(smaller_tagged)
            model.comprimido_em = datetime.now(timezone.utc)
            db.commit()
        except Exception:  # noqa: BLE001 - any transcode/storage failure rolls back and moves on.
            db.rollback()
            for key in saved:
                try:
                    provider.delete(key)
                except Exception:  # noqa: BLE001
                    logger.error("preview_compression_compensation_failed")
            # Mark it as handled so a broken file does not block the queue.
            try:
                failed = db.get(ProducaoArquivoModel, model.id)
                failed.comprimido_em = datetime.now(timezone.utc)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
            logger.warning("preview_compression_failed file_id=%s", model.id)
            return True
        for key in old_keys:
            try:
                provider.delete(key)
            except Exception:  # noqa: BLE001
                logger.warning("preview_compression_cleanup_failed")
        return True
