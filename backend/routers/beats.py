from typing import Annotated
from uuid import UUID

from core.dependencies import (
    get_current_user,
    require_admin,
    require_client,
    require_producer,
)
from database import get_db
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import Response
from pydantic import ValidationError
from schemas.beat import (
    BeatCreate,
    BeatRequest,
    BeatReview,
    BeatUploadConfigResponse,
    BeatUploadLimits,
)
from services import beat_service, beat_upload_config_service
from sqlalchemy.orm import Session

router = APIRouter(tags=["Catalogo de beats"])
Db = Annotated[Session, Depends(get_db)]
Producer = Annotated[object, Depends(require_producer)]
Client = Annotated[object, Depends(require_client)]
Admin = Annotated[object, Depends(require_admin)]
User = Annotated[object, Depends(get_current_user)]


async def _file(upload, kind, limits):
    if upload is None:
        return None
    limit = limits[kind]
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
    try:
        return BeatCreate(titulo=titulo, descricao=descricao, bpm=bpm, tonalidade=tonalidade,
                          generos=generos, preco_lease=preco_lease or None,
                          preco_wav=preco_wav or None, preco_multitrack=preco_multitrack or None,
                          preco_exclusivo=preco_exclusivo or None)
    except ValidationError:
        raise HTTPException(422, "Revise os campos e preços do beat.") from None


@router.get("/portal/produtor/beats")
def producer_beats(db: Db, user: Producer):
    return beat_service.producer_list(db, user)


@router.get("/portal/produtor/beats/configuracao", response_model=BeatUploadConfigResponse)
def producer_beat_config(db: Db, user: Producer):
    if not user.painel_beats:
        raise HTTPException(403, "Painel de beats não habilitado para esta conta.")
    try:
        beat_service._tag(db, user.id)
        ready, message = True, ""
    except HTTPException as error:
        ready, message = False, str(error.detail)
    return {"limits": beat_upload_config_service.limits(db), "ready": ready, "message": message}


@router.post("/portal/produtor/beats", status_code=201)
async def submit_beat(
    db: Db,
    user: Producer,
    mp3: Annotated[UploadFile, File()],
    capa: Annotated[UploadFile, File()],
    titulo: Annotated[str, Form()],
    wav: Annotated[UploadFile | None, File()] = None,
    multitrack: Annotated[UploadFile | None, File()] = None,
    multitrack_url: Annotated[str | None, Form()] = None,
    descricao: Annotated[str, Form()] = "",
    bpm: Annotated[int | None, Form()] = None,
    tonalidade: Annotated[str | None, Form()] = None,
    generos: Annotated[str, Form()] = "",
    preco_lease: Annotated[str | None, Form()] = None,
    preco_wav: Annotated[str | None, Form()] = None,
    preco_multitrack: Annotated[str | None, Form()] = None,
    preco_exclusivo: Annotated[str | None, Form()] = None,
):
    limits = beat_upload_config_service.limits_bytes(db)
    payload = _payload(titulo, descricao, bpm, tonalidade, generos,
                       preco_lease, preco_wav, preco_multitrack, preco_exclusivo)
    return beat_service.create(db, actor=user, payload=payload,
                               mp3=await _file(mp3, "mp3", limits), wav=await _file(wav, "wav", limits),
                               archive=await _file(multitrack, "multitrack", limits), cover=await _file(capa, "capa", limits),
                               multitrack_url=multitrack_url)


@router.get("/portal/cliente/beats")
def client_beats(db: Db, user: Client):
    return beat_service.client_list(db)


@router.get("/portal/cliente/beats/adquiridos")
def client_acquired_beats(db: Db, user: Client):
    return beat_service.acquired_multitracks(db, user)


@router.get("/portal/cliente/beats/{beat_id}/multitrack")
def client_multitrack(beat_id: int, db: Db, user: Client):
    delivery = beat_service.multitrack_delivery(db, beat_id, user)
    if delivery["type"] == "link":
        return {"type": "link", "url": delivery["url"]}
    return Response(
        delivery["contents"],
        media_type=delivery["mime"],
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{delivery["filename"]}"',
        },
    )


@router.get("/portal/cliente/beats/{beat_id}/arquivo/{kind}")
def client_purchased_file(beat_id: int, kind: str, db: Db, user: Client):
    delivery = beat_service.purchased_file(db, beat_id, kind, user)
    if delivery["type"] == "link":
        return {"type": "link", "url": delivery["url"]}
    return Response(
        delivery["contents"],
        media_type=delivery["mime"],
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{delivery["filename"]}"',
        },
    )


@router.post("/portal/cliente/beats/{beat_id}/solicitar", status_code=201)
def request_beat(
    beat_id: int,
    payload: BeatRequest,
    request: Request,
    db: Db,
    user: Client,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
):
    if idempotency_key is None:
        from fastapi import HTTPException

        raise HTTPException(422, "Idempotency-Key obrigatoria.")
    return beat_service.request_license(
        db, beat_id, payload.licenca, user, str(idempotency_key),
        getattr(request.state, "request_id", None),
    )


@router.get("/admin/beats")
def admin_beats(db: Db, user: Admin):
    return beat_service.admin_list(db)


@router.get("/admin/beats/configuracao", response_model=BeatUploadLimits)
def admin_beat_config(db: Db, user: Admin):
    return beat_upload_config_service.limits(db)


@router.put("/admin/beats/configuracao", response_model=BeatUploadLimits)
def update_admin_beat_config(payload: BeatUploadLimits, db: Db, user: Admin):
    return beat_upload_config_service.update(db, payload, user)


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
    multitrack_url: Annotated[str | None, Form()] = None,
    capa: Annotated[UploadFile | None, File()] = None,
):
    limits = beat_upload_config_service.limits_bytes(db)
    payload = _payload(titulo, descricao, bpm, tonalidade, generos,
                       preco_lease, preco_wav, preco_multitrack, preco_exclusivo)
    return beat_service.edit(db, beat_id, payload, user,
                             mp3=await _file(mp3, "mp3", limits), wav=await _file(wav, "wav", limits),
                             archive=await _file(multitrack, "multitrack", limits), cover=await _file(capa, "capa", limits),
                             multitrack_url=multitrack_url)


@router.get("/beats/{beat_id}/preview")
def preview(beat_id: int, db: Db, user: User):
    return Response(
        beat_service.preview(db, beat_id, user),
        media_type="audio/mpeg",
        headers={"Cache-Control": "private, no-store"},
    )
