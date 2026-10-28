"""Private tags and bounded local rendering, without changing original uploads."""

import hashlib
import io
import logging
import math
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import mutagen
from fastapi import HTTPException
from models import AudioTagModel, AudioTagPerfilModel, PreviaTagJobModel
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from services import audit_service
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)
MAX_TAG_BYTES = 2 * 1024 * 1024
TAG_MIMES = {"audio/mpeg", "audio/wav", "audio/x-wav"}
LEVEL_DEFAULTS = {
    "nivelamento_automatico": True,
    "alvo_relativo_db": -3.0,
    "ganho_min_db": -40.0,
    "ganho_max_db": 30.0,
    "silencio_lufs": -60.0,
    "limiter_dbfs": -0.9,
}
LEVEL_FIELDS = tuple(LEVEL_DEFAULTS)


def duracao(data, *, limite):
    try:
        audio = mutagen.File(io.BytesIO(data))
        length = float(audio.info.length) if audio is not None else 0
    except Exception:
        length = 0
    if not 0 < length <= limite:
        raise HTTPException(422, "Audio invalido ou acima do limite de duracao.")
    return length


def perfil(db, chave):
    return db.get(AudioTagPerfilModel, chave)


def level_values(source=None):
    return {
        key: getattr(source, key, default) if source is not None else default
        for key, default in LEVEL_DEFAULTS.items()
    }


def resposta(db, chave):
    current = perfil(db, chave)
    studio = current if chave == "studio" else perfil(db, "studio")
    tag = db.get(AudioTagModel, current.tag_id) if current and current.tag_id else None
    return {
        "versao": current.versao if current else 0,
        "nome": tag.nome if tag else None,
        "tag_id": tag.id if tag else None,
        "intervalo_segundos": studio.intervalo_segundos if studio else 10,
        "volume_percentual": studio.volume_percentual if studio else 40,
        "padrao_disponivel": bool(studio and studio.tag_id),
        **level_values(studio),
    }


def salvar(db, *, actor, chave, data, filename, mime_type, versao):
    if not data or len(data) > MAX_TAG_BYTES or mime_type not in TAG_MIMES:
        raise HTTPException(422, "Envie uma tag MP3 ou WAV de ate 2 MB e 10 segundos.")
    length = duracao(data, limite=10)
    if not isinstance(mutagen.File(io.BytesIO(data)), (MP3, WAVE)):
        raise HTTPException(422, "Envie uma tag MP3 ou WAV valida.")
    current = db.scalar(select(AudioTagPerfilModel).where(AudioTagPerfilModel.chave == chave).with_for_update())
    if (current.versao if current else 0) != versao:
        raise HTTPException(409, "A tag foi alterada. Recarregue antes de salvar.")
    if current is None:
        current = AudioTagPerfilModel(chave=chave, versao=1)
        db.add(current)
    else:
        current.versao += 1
    tag = AudioTagModel(usuario_id=actor.id, nome=Path(filename).name[:180] or "tag.mp3", mime_type=mime_type,
                        conteudo=data, sha256=hashlib.sha256(data).hexdigest(), duracao=length)
    db.add(tag)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A tag foi alterada. Recarregue antes de salvar.") from None
    current.tag_id = tag.id
    audit_service.record(db, actor=actor, action="audio_tag.updated", entity_type="audio_tag", entity_id=tag.id,
                         metadata={"scope": chave, "version": current.versao})
    db.commit()
    return resposta(db, chave)


def configurar(db, actor, payload):
    current = db.scalar(select(AudioTagPerfilModel).where(AudioTagPerfilModel.chave == "studio").with_for_update())
    if (current.versao if current else 0) != payload.versao:
        raise HTTPException(409, "A configuracao foi alterada. Recarregue antes de salvar.")
    if current is None:
        current = AudioTagPerfilModel(chave="studio", versao=1)
        db.add(current)
    else:
        current.versao += 1
    current.intervalo_segundos = payload.intervalo_segundos
    current.volume_percentual = payload.volume_percentual
    for field in LEVEL_FIELDS:
        setattr(current, field, getattr(payload, field))
    audit_service.record(db, actor=actor, action="audio_tag.settings_updated", entity_type="audio_tag_settings",
                         entity_id=1, metadata={"interval": current.intervalo_segundos,
                                                "volume": current.volume_percentual, **level_values(current)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A configuracao foi alterada. Recarregue antes de salvar.") from None
    return resposta(db, "studio")


def opcoes_preview(db):
    from models import BeatModel, ProducaoArquivoModel, ProducaoModel, UsuarioModel

    current_scopes = {}
    for profile in db.scalars(select(AudioTagPerfilModel).where(AudioTagPerfilModel.tag_id.is_not(None))):
        current_scopes.setdefault(profile.tag_id, []).append(profile.chave)
    tags = []
    for tag, owner in db.execute(
        select(AudioTagModel, UsuarioModel)
        .join(UsuarioModel, UsuarioModel.id == AudioTagModel.usuario_id)
        .order_by(AudioTagModel.created_at.desc(), AudioTagModel.id.desc())
    ):
        scopes = current_scopes.get(tag.id, [])
        if "studio" in scopes:
            label = f"Tag padrao da Mirai - {tag.nome}"
        else:
            producer = owner.nome_exibicao or owner.username
            label = f"{producer} - {tag.nome}"
        tags.append({
            "id": tag.id,
            "label": label,
            "nome": tag.nome,
            "duracao": tag.duracao,
            "atual": bool(scopes),
            "created_at": tag.created_at,
        })

    sources = []
    for beat in db.scalars(select(BeatModel).order_by(BeatModel.created_at.desc(), BeatModel.id.desc())):
        sources.append({
            "type": "beat",
            "id": beat.id,
            "label": f"Beat - {beat.titulo}",
            "detail": f"Beat #{beat.id} - {beat.status}",
        })
    files = db.execute(
        select(ProducaoArquivoModel, ProducaoModel)
        .join(ProducaoModel, ProducaoModel.id == ProducaoArquivoModel.producao_id)
        .where(
            ProducaoModel.status.in_(("finalizado", "entregue")),
            ProducaoArquivoModel.tipo.in_(("previa", "entrega")),
            ProducaoArquivoModel.mime_type.like("audio/%"),
        )
        .order_by(ProducaoModel.id.desc(), ProducaoArquivoModel.created_at.desc(), ProducaoArquivoModel.id.desc())
    ).all()
    for file, production in files:
        kind = "Previa" if file.tipo == "previa" else "Entrega"
        sources.append({
            "type": "arquivo",
            "id": file.id,
            "label": f"{kind} - {production.titulo} - {file.nome_exibicao}",
            "detail": f"Producao #{production.id} - versao {file.versao}",
        })
    return {"fontes": sources, "tags": tags}


def gerar_preview(db, actor, payload):
    from models import BeatModel, ProducaoArquivoModel, ProducaoModel
    from services import producao_arquivo_service
    from services.producao_arquivo_storage import (
        ProducaoArquivoStorageError,
        new_production_file_storage,
    )

    tag = db.get(AudioTagModel, payload.tag_id)
    if tag is None:
        raise HTTPException(404, "Tag nao encontrada.")
    if hashlib.sha256(tag.conteudo).hexdigest() != tag.sha256:
        raise HTTPException(409, "Integridade da tag nao confirmada.")
    try:
        if payload.source_type == "beat":
            source = db.get(BeatModel, payload.source_id)
            if source is None:
                raise HTTPException(404, "Beat nao encontrado.")
            original = new_production_file_storage("previa").read(source.original_ref)
            expected_sha = source.original_sha256
        else:
            source = db.scalar(
                select(ProducaoArquivoModel)
                .join(ProducaoModel, ProducaoModel.id == ProducaoArquivoModel.producao_id)
                .where(
                    ProducaoArquivoModel.id == payload.source_id,
                    ProducaoModel.status.in_(("finalizado", "entregue")),
                    ProducaoArquivoModel.tipo.in_(("previa", "entrega")),
                    ProducaoArquivoModel.mime_type.like("audio/%"),
                )
            )
            if source is None:
                raise HTTPException(404, "Audio de producao nao encontrado.")
            original = producao_arquivo_service.read(source, client=False, versao="original")
            expected_sha = source.sha256
    except HTTPException:
        raise
    except (ProducaoArquivoStorageError, producao_arquivo_service.ProducaoArquivoUnavailable):
        raise HTTPException(503, "O audio selecionado esta temporariamente indisponivel.") from None
    if hashlib.sha256(original).hexdigest() != expected_sha:
        raise HTTPException(409, "Integridade do audio nao confirmada.")
    controls = payload.model_dump(exclude={"source_type", "source_id", "tag_id", "intervalo_segundos", "volume_percentual"})
    try:
        output = mixar(
            original,
            tag.conteudo,
            payload.intervalo_segundos,
            payload.volume_percentual,
            **controls,
        )
    except RuntimeError as error:
        if str(error) == "audio_original_too_large":
            raise HTTPException(422, "O audio selecionado excede o limite de 50 MB para esta previa.") from None
        raise HTTPException(503, "Nao foi possivel gerar a previa agora.") from None
    audit_service.record(
        db,
        actor=actor,
        action="audio_tag.preview_generated",
        entity_type=payload.source_type,
        entity_id=payload.source_id,
        metadata={"tag_id": tag.id, **controls},
    )
    db.commit()
    return output


def preparar(db, *, actor, file_type, mime_type, data):
    if file_type != "previa" or not mime_type.startswith("audio/"):
        return None
    own = perfil(db, f"producer:{actor.id}") if getattr(actor, "role", None) == "produtor" else None
    studio = perfil(db, "studio")
    tag_id = own.tag_id if own and own.tag_id else studio.tag_id if studio else None
    if not tag_id:
        return None  # No tag was configured yet; preserve the existing preview flow, without claiming a tag.
    seconds = duracao(data, limite=1800)
    return {"tag_id": tag_id, "intervalo_segundos": studio.intervalo_segundos if studio else 10,
            "volume_percentual": studio.volume_percentual if studio else 40,
            "reserva_bytes": math.ceil(seconds * 24000) + 512 * 1024, **level_values(studio)}


# AUD6-S12-002: the tag runs inside the web process, so ffmpeg yields CPU to the API.
FFMPEG_NICE = 15
MAX_ORIGINAL_BYTES = 50 * 1024 * 1024
_despertar = None


def _baixa_prioridade():
    try:
        os.nice(FFMPEG_NICE)
    except OSError:
        pass


def registrar_despertador(callback):
    """The worker loop registers how to wake up when a preview is queued."""
    global _despertar
    _despertar = callback


def sinalizar_fila():
    if _despertar is not None:
        try:
            _despertar()
        except Exception:
            logger.warning("audio_tag_worker_wake_failed")


# Automatic tag level: the tag is matched to the loudness of each audio (EBU R128).
# The relative target, gain bounds and limiter are frozen with every queued job.
_INTEGRADO = re.compile(r"\bI:\s+(-?\d+(?:\.\d+)?) LUFS")


def medir_loudness(path, silencio_lufs=-60.0):
    """Integrated loudness in LUFS, or None when it cannot be measured (silence, error)."""
    from imageio_ffmpeg import get_ffmpeg_exe

    try:
        result = subprocess.run([
            get_ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "info", "-threads", "1",
            "-protocol_whitelist", "file,pipe", "-i", str(path), "-t", "1800",
            "-af", "ebur128=framelog=quiet", "-f", "null", "-",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60, check=False,
            preexec_fn=_baixa_prioridade if os.name == "posix" else None)
    except (OSError, subprocess.TimeoutExpired):
        return None
    found = _INTEGRADO.findall(result.stderr.decode("utf-8", "ignore")) if result.returncode == 0 else []
    value = float(found[-1]) if found else None
    return value if value is not None and value > silencio_lufs else None


def ganho_tag_db(audio_lufs, tag_lufs, alvo_relativo_db=-3.0, ganho_min_db=-40.0, ganho_max_db=30.0):
    """Gain for the tag so it sits at the chosen level relative to the audio."""
    if audio_lufs is None or tag_lufs is None:
        return None
    alvo = audio_lufs + alvo_relativo_db
    return round(max(ganho_min_db, min(ganho_max_db, alvo - tag_lufs)), 2)


def mixar(original, tag, intervalo, volume, **controls):
    from imageio_ffmpeg import get_ffmpeg_exe

    if len(original) > MAX_ORIGINAL_BYTES:
        raise RuntimeError("audio_original_too_large")

    with TemporaryDirectory(prefix="mirai-audio-tag-") as directory:
        folder = Path(directory)
        source, stamp, output = folder / "source.audio", folder / "tag.audio", folder / "preview.mp3"
        source.write_bytes(original)
        stamp.write_bytes(tag)
        config = {**LEVEL_DEFAULTS, **{key: controls[key] for key in LEVEL_FIELDS if key in controls}}
        ganho = None
        if config["nivelamento_automatico"]:
            ganho = ganho_tag_db(
                medir_loudness(source, config["silencio_lufs"]),
                medir_loudness(stamp, config["silencio_lufs"]),
                config["alvo_relativo_db"],
                config["ganho_min_db"],
                config["ganho_max_db"],
            )
        limiter = round(10 ** (config["limiter_dbfs"] / 20), 6)
        # Disabled leveling or unmeasurable audio uses the explicit fixed fallback.
        nivel = f"volume={ganho}dB,alimiter=limit={limiter}:level=false" if ganho is not None else f"volume={volume / 100}"
        graph = (f"[1:a]aresample=48000,apad=whole_dur={intervalo},"
                 f"aloop=loop=-1:size={intervalo * 48000},{nivel}[tag];"
                 f"[0:a][tag]amix=inputs=2:duration=first:normalize=0,alimiter=limit={limiter}:level=false[out]")
        try:
            result = subprocess.run([
                get_ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "1", "-filter_complex_threads", "1",
                "-protocol_whitelist", "file,pipe", "-i", str(source),
                "-protocol_whitelist", "file,pipe", "-i", str(stamp), "-filter_complex", graph,
                "-map", "[out]", "-map_metadata", "-1", "-c:a", "libmp3lame", "-b:a", "192k",
                "-t", "1800", "-fs", str(50 * 1024 * 1024), "-y", str(output),
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=False,
                preexec_fn=_baixa_prioridade if os.name == "posix" else None)
            if result.returncode != 0 or not output.exists():
                raise RuntimeError("audio_render_failed")
            content = output.read_bytes()
            if not content or len(content) >= 50 * 1024 * 1024:
                raise RuntimeError("audio_render_invalid")
            duracao(content, limite=1800)
            return content
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("audio_render_unavailable") from None


def processar_um(session_factory, *, storage=None, renderer=mixar):
    from models import ProducaoArquivoModel
    from services import portal_notificacao_service, producao_arquivo_service
    from services.producao_arquivo_storage import new_production_file_storage

    arquivo_id, key = None, None
    with session_factory() as db:
        try:
            job = db.scalar(select(PreviaTagJobModel).where(PreviaTagJobModel.estado == "pendente")
                            .order_by(PreviaTagJobModel.arquivo_id).with_for_update(skip_locked=True).limit(1))
            if job is None:
                return False
            arquivo_id = job.arquivo_id
            model = db.get(ProducaoArquivoModel, arquivo_id)
            tag = db.get(AudioTagModel, job.tag_id)
            if model.tipo != "previa" or hashlib.sha256(tag.conteudo).hexdigest() != tag.sha256:
                raise RuntimeError("audio_tag_integrity")
            original = producao_arquivo_service.read(model, storage=storage)
            content = renderer(
                original,
                tag.conteudo,
                job.intervalo_segundos,
                job.volume_percentual,
                **level_values(job),
            )
            if not content or len(content) > job.reserva_bytes:
                raise RuntimeError("audio_render_exceeds_reservation")
            provider = storage or new_production_file_storage("previa")
            key = provider.save(content, "audio/mpeg")
            job.object_key, job.sha256, job.tamanho_bytes = key, hashlib.sha256(content).hexdigest(), len(content)
            job.estado, job.concluido_em = "pronto", datetime.now(timezone.utc)
            portal_notificacao_service.arquivo_compartilhado(db, model)
            db.commit()
            return True
        except Exception:
            db.rollback()
            if arquivo_id is not None:
                # Verify durable state before compensating: a failed commit acknowledgement may have committed.
                try:
                    job = db.scalar(select(PreviaTagJobModel).where(PreviaTagJobModel.arquivo_id == arquivo_id)
                                    .with_for_update().execution_options(populate_existing=True))
                except Exception:
                    logger.error("audio_tag_outcome_unknown file_id=%s", arquivo_id)
                    return False
                if job is not None and job.estado == "pronto":
                    return True
                if key is not None:
                    try:
                        provider.delete(key)
                    except Exception:
                        logger.error("audio_tag_compensation_failed file_id=%s", arquivo_id)
                if job is not None and job.estado == "pendente":
                    job.estado = "erro"
                    try:
                        # AUD6-S08-002: the studio hears about the failure; the job state never depends on it.
                        with db.begin_nested():
                            failed = db.get(ProducaoArquivoModel, arquivo_id)
                            if failed is not None:
                                portal_notificacao_service.falha_tag(db, failed)
                    except Exception:
                        logger.warning("audio_tag_failure_notice_failed file_id=%s", arquivo_id)
                    db.commit()
                logger.warning("audio_tag_processing_failed file_id=%s", arquivo_id)
            return False
