from typing import Annotated

from core.dependencies import require_admin, require_producer
from database import get_db
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from models import AudioTagModel, AudioTagPerfilModel, PreviaTagJobModel
from schemas.audio_tag import AudioTagSettings
from services import audio_tag_service as service
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Tags de audio"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/admin/audio-tag")
def configuracao(db: Db, user=Depends(require_admin)):
    return service.resposta(db, "studio")


@router.put("/admin/audio-tag")
def configurar(payload: AudioTagSettings, db: Db, user=Depends(require_admin)):
    return service.configurar(db, user, payload)


@router.get("/portal/produtor/audio-tag")
def meu_perfil(db: Db, user=Depends(require_producer)):
    return service.resposta(db, f"producer:{user.id}")


async def _upload(arquivo, versao, db, user, chave):
    data = await arquivo.read(service.MAX_TAG_BYTES + 1)
    await arquivo.close()
    return service.salvar(db, actor=user, chave=chave, data=data, filename=arquivo.filename or "tag.mp3",
                          mime_type=arquivo.content_type or "application/octet-stream", versao=versao)


@router.post("/admin/audio-tag")
async def upload_padrao(db: Db, arquivo: Annotated[UploadFile, File()], versao: Annotated[int, Form(ge=0)],
                        user=Depends(require_admin)):
    return await _upload(arquivo, versao, db, user, "studio")


@router.post("/portal/produtor/audio-tag")
async def upload_pessoal(db: Db, arquivo: Annotated[UploadFile, File()], versao: Annotated[int, Form(ge=0)],
                         user=Depends(require_producer)):
    return await _upload(arquivo, versao, db, user, f"producer:{user.id}")


def _conteudo(db, chave):
    current = db.get(AudioTagPerfilModel, chave)
    tag = db.get(AudioTagModel, current.tag_id) if current and current.tag_id else None
    if tag is None:
        raise HTTPException(404, "Tag nao cadastrada.")
    return Response(tag.conteudo, media_type=tag.mime_type, headers={"Cache-Control": "private, no-store"})


@router.get("/admin/audio-tag/conteudo")
def ouvir_padrao(db: Db, user=Depends(require_admin)):
    return _conteudo(db, "studio")


@router.get("/portal/produtor/audio-tag/conteudo")
def ouvir_pessoal(db: Db, user=Depends(require_producer)):
    return _conteudo(db, f"producer:{user.id}")


@router.get("/admin/audio-tag/previas/falhas")
def falhas(db: Db, user=Depends(require_admin)):
    # AUD6-S08-002: the Admin sees which previews failed and can retry each one.
    from models import ProducaoArquivoModel, ProducaoModel
    from services.dashboard_service import _producao_oficial

    rows = db.execute(
        select(PreviaTagJobModel.arquivo_id, PreviaTagJobModel.created_at, ProducaoArquivoModel.nome_exibicao,
               ProducaoModel.id, ProducaoModel.titulo)
        .join(ProducaoArquivoModel, ProducaoArquivoModel.id == PreviaTagJobModel.arquivo_id)
        .join(ProducaoModel, ProducaoModel.id == ProducaoArquivoModel.producao_id)
        .where(PreviaTagJobModel.estado == "erro", _producao_oficial())
        .order_by(PreviaTagJobModel.created_at.desc())
        .limit(20)
    ).all()
    return [
        {"arquivo_id": arquivo_id, "arquivo_nome": nome, "producao_id": producao_id,
         "producao_titulo": titulo, "created_at": created_at}
        for arquivo_id, created_at, nome, producao_id, titulo in rows
    ]


@router.post("/admin/audio-tag/previas/{arquivo_id}/reprocessar")
def reprocessar(arquivo_id: int, db: Db, user=Depends(require_admin)):
    from services import audit_service

    job = db.scalar(select(PreviaTagJobModel).where(PreviaTagJobModel.arquivo_id == arquivo_id).with_for_update())
    if job is None:
        raise HTTPException(404, "Processamento nao encontrado.")
    if job.estado == "erro":
        job.estado = "pendente"
        audit_service.record(db, actor=user, action="audio_tag.retry", entity_type="production_file", entity_id=arquivo_id)
        db.commit()
    return {"estado": job.estado}
