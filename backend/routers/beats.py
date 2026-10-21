from typing import Annotated
from uuid import UUID

from core.dependencies import (
    get_current_user,
    require_admin,
    require_client,
    require_producer,
)
from database import get_db
from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
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


@router.get("/portal/produtor/beats")
def producer_beats(db: Db, user: Producer):
    return beat_service.producer_list(db, user)


@router.post("/portal/produtor/beats", status_code=201)
async def submit_beat(
    db: Db,
    user: Producer,
    arquivo: Annotated[UploadFile, File()],
    titulo: Annotated[str, Form()],
    descricao: Annotated[str, Form()] = "",
    bpm: Annotated[int | None, Form()] = None,
    tonalidade: Annotated[str | None, Form()] = None,
    generos: Annotated[str, Form()] = "",
    preco_lease: Annotated[str | None, Form()] = None,
    preco_exclusivo: Annotated[str | None, Form()] = None,
):
    data = await arquivo.read(beat_service.MAX_BEAT_BYTES + 1)
    await arquivo.close()
    payload = BeatCreate(
        titulo=titulo,
        descricao=descricao,
        bpm=bpm,
        tonalidade=tonalidade,
        generos=generos,
        preco_lease=preco_lease,
        preco_exclusivo=preco_exclusivo,
    )
    return beat_service.create(
        db, actor=user, payload=payload, data=data, mime_type=arquivo.content_type or ""
    )


@router.get("/portal/cliente/beats")
def client_beats(db: Db, user: Client):
    return beat_service.client_list(db)


@router.post("/portal/cliente/beats/{beat_id}/solicitar", status_code=201)
def request_beat(
    beat_id: int,
    payload: BeatRequest,
    db: Db,
    user: Client,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")] = None,
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


@router.get("/beats/{beat_id}/preview")
def preview(beat_id: int, db: Db, user: User):
    return Response(
        beat_service.preview(db, beat_id, user),
        media_type="audio/mpeg",
        headers={"Cache-Control": "private, no-store"},
    )
