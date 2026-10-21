from typing import Annotated
from uuid import UUID

from core.dependencies import (
    get_current_user,
    require_admin,
    require_client,
    require_producer,
)
from database import get_db
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from schemas.beat import BeatCreate, BeatRequest, BeatReview
from services import beat_service
from sqlalchemy.orm import Session

router = APIRouter(tags=["Catalogo de beats"])
Db = Annotated[Session, Depends(get_db)]
Producer = Annotated[object, Depends(require_producer)]
Client = Annotated[object, Depends(require_client)]
Admin = Annotated[object, Depends(require_admin)]
User = Annotated[object, Depends(get_current_user)]


async def _file(upload, kind):
    if upload is None:
        return None
    limit = 10 * 1024 * 1024 if kind == "capa" else beat_service.MAX_BEAT_BYTES
    data = await upload.read(limit + 1)
    await upload.close()
    extension = (upload.filename or "").lower().rsplit(".", 1)[-1]
    allowed = {"mp3": {"mp3": "audio/mpeg"}, "wav": {"wav": "audio/wav"},
               "multitrack": {"zip": "application/zip", "rar": "application/vnd.rar"},
               "capa": {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}}[kind]
    if extension not in allowed:
        raise HTTPException(422, "Extensao de arquivo invalida.")
    return data, allowed[extension]


def _payload(titulo, descricao, bpm, tonalidade, generos, preco_lease, preco_wav, preco_multitrack, preco_exclusivo):
    return BeatCreate(titulo=titulo, descricao=descricao, bpm=bpm, tonalidade=tonalidade,
                      generos=generos, preco_lease=preco_lease or None,
                      preco_wav=preco_wav or None, preco_multitrack=preco_multitrack or None,
                      preco_exclusivo=preco_exclusivo or None)


@router.get("/portal/produtor/beats")
def producer_beats(db: Db, user: Producer):
    return beat_service.producer_list(db, user)


@router.post("/portal/produtor/beats", status_code=201)
async def submit_beat(
    db: Db,
    user: Producer,
    mp3: Annotated[UploadFile, File()],
    capa: Annotated[UploadFile, File()],
    titulo: Annotated[str, Form()],
    wav: Annotated[UploadFile | None, File()] = None,
    multitrack: Annotated[UploadFile | None, File()] = None,
    descricao: Annotated[str, Form()] = "",
    bpm: Annotated[int | None, Form()] = None,
    tonalidade: Annotated[str | None, Form()] = None,
    generos: Annotated[str, Form()] = "",
    preco_lease: Annotated[str | None, Form()] = None,
    preco_wav: Annotated[str | None, Form()] = None,
    preco_multitrack: Annotated[str | None, Form()] = None,
    preco_exclusivo: Annotated[str | None, Form()] = None,
):
    payload = _payload(titulo, descricao, bpm, tonalidade, generos,
                       preco_lease, preco_wav, preco_multitrack, preco_exclusivo)
    return beat_service.create(db, actor=user, payload=payload,
                               mp3=await _file(mp3, "mp3"), wav=await _file(wav, "wav"),
                               archive=await _file(multitrack, "multitrack"), cover=await _file(capa, "capa"))


@router.get("/portal/cliente/beats")
def client_beats(db: Db, user: Client):
    return beat_service.client_list(db)


@router.post("/portal/cliente/beats/{beat_id}/solicitar", status_code=201)
def request_beat(
    beat_id: int,
    payload: BeatRequest,
    db: Db,
    user: Client,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
):
    if idempotency_key is None:
        from fastapi import HTTPException

        raise HTTPException(422, "Idempotency-Key obrigatoria.")
    return beat_service.request_license(
        db, beat_id, payload.licenca, user, str(idempotency_key)
    )


@router.get("/admin/beats")
def admin_beats(db: Db, user: Admin):
    return beat_service.admin_list(db)


@router.patch("/admin/beats/{beat_id}")
def review(beat_id: int, payload: BeatReview, db: Db, user: Admin):
    return beat_service.review(db, beat_id, payload, user)


@router.put("/admin/beats/{beat_id}")
async def edit_beat(
    beat_id: int, db: Db, user: Admin, titulo: Annotated[str, Form()],
    descricao: Annotated[str, Form()] = "", bpm: Annotated[int | None, Form()] = None,
    tonalidade: Annotated[str | None, Form()] = None, generos: Annotated[str, Form()] = "",
    preco_lease: Annotated[str | None, Form()] = None, preco_wav: Annotated[str | None, Form()] = None,
    preco_multitrack: Annotated[str | None, Form()] = None,
    preco_exclusivo: Annotated[str | None, Form()] = None,
    mp3: Annotated[UploadFile | None, File()] = None,
    wav: Annotated[UploadFile | None, File()] = None,
    multitrack: Annotated[UploadFile | None, File()] = None,
    capa: Annotated[UploadFile | None, File()] = None,
):
    payload = _payload(titulo, descricao, bpm, tonalidade, generos,
                       preco_lease, preco_wav, preco_multitrack, preco_exclusivo)
    return beat_service.edit(db, beat_id, payload, user,
                             mp3=await _file(mp3, "mp3"), wav=await _file(wav, "wav"),
                             archive=await _file(multitrack, "multitrack"), cover=await _file(capa, "capa"))


@router.get("/beats/{beat_id}/preview")
def preview(beat_id: int, db: Db, user: User):
    return Response(
        beat_service.preview(db, beat_id, user),
        media_type="audio/mpeg",
        headers={"Cache-Control": "private, no-store"},
    )
