"""Mirai Hit Labs: public plugin catalog, purchases, downloads and the Admin catalog."""
from typing import Annotated
from uuid import UUID

from core import rate_limit
from core.dependencies import require_admin, require_client
from database import get_db
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Path, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from schemas.plugin import (
    PluginCortesia,
    PluginInstaladorLink,
    PluginPayload,
    PluginRevogacao,
    PluginValidacao,
)
from services import plugin_service
from sqlalchemy.orm import Session

router = APIRouter(tags=["Mirai Hit Labs"])
Db = Annotated[Session, Depends(get_db)]
Client = Annotated[object, Depends(require_client)]
Admin = Annotated[object, Depends(require_admin)]
Slug = Annotated[str, Path(max_length=60)]
PUBLIC_CACHE = {"Cache-Control": "public, max-age=60"}
COVERS = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


# ---------------------------------------------------------------- public


@router.get("/labs/plugins")
def plugins_publicos(db: Db):
    return JSONResponse(jsonable_encoder(plugin_service.publico_lista(db)), headers=PUBLIC_CACHE)


@router.get("/labs/plugins/{slug}")
def plugin_publico(slug: Slug, db: Db):
    return JSONResponse(jsonable_encoder(plugin_service.publico_detalhe(db, slug)), headers=PUBLIC_CACHE)


@router.post("/labs/licencas/validar")
def validar_licenca(payload: PluginValidacao, request: Request, db: Db):
    """For the plugins themselves (activation). Limited per address; never returns personal data."""
    client = request.client.host if request.client else "unknown"
    try:
        allowed, _ = rate_limit.allow_request(f"labs-validar:{client}", 30, 300)
    except Exception:  # noqa: BLE001 - the limiter fails open, like the other public routes
        allowed = True
    if not allowed:
        raise HTTPException(429, "Muitas tentativas; aguarde alguns minutos.")
    return JSONResponse(plugin_service.validar_chave(db, payload.chave, payload.plugin),
                        headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------- client


@router.post("/labs/plugins/{slug}/comprar", status_code=201)
def comprar_plugin(
    slug: Slug,
    request: Request,
    db: Db,
    user: Client,
    idempotency_key: Annotated[UUID | None, Header(alias="Idempotency-Key")] = None,
):
    if idempotency_key is None:
        raise HTTPException(422, "Idempotency-Key obrigatoria.")
    return plugin_service.comprar(db, slug, user, str(idempotency_key), getattr(request.state, "request_id", None))


@router.get("/portal/cliente/plugins")
def meus_plugins(db: Db, user: Client):
    return JSONResponse(jsonable_encoder(plugin_service.minhas_licencas(db, user)),
                        headers={"Cache-Control": "private, no-store"})


@router.get("/portal/cliente/plugins/{licenca_id}/download/{sistema}")
def baixar_plugin(licenca_id: int, sistema: str, db: Db, user: Client):
    delivery = plugin_service.download(db, licenca_id, sistema, user)
    if delivery["type"] in ("link", "download"):
        return JSONResponse({key: delivery[key] for key in ("type", "url", "filename") if key in delivery},
                            headers={"Cache-Control": "private, no-store"})
    return Response(delivery["contents"], media_type=delivery["mime"], headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'attachment; filename="{delivery["filename"]}"',
    })


# ---------------------------------------------------------------- admin


@router.get("/admin/labs/plugins")
def admin_plugins(db: Db, user: Admin):
    return plugin_service.admin_lista(db)


@router.post("/admin/labs/plugins", status_code=201)
def admin_criar(payload: PluginPayload, db: Db, user: Admin):
    return plugin_service.criar(db, payload, user)


@router.get("/admin/labs/plugins/{plugin_id}")
def admin_obter(plugin_id: int, db: Db, user: Admin):
    return plugin_service.admin_obter(db, plugin_id)


@router.put("/admin/labs/plugins/{plugin_id}")
def admin_editar(plugin_id: int, payload: PluginPayload, db: Db, user: Admin):
    return plugin_service.editar(db, plugin_id, payload, user)


@router.post("/admin/labs/plugins/{plugin_id}/capa")
async def admin_capa(plugin_id: int, db: Db, user: Admin, capa: Annotated[UploadFile, File()]):
    extension = (capa.filename or "").lower().rsplit(".", 1)[-1]
    if extension not in COVERS:
        raise HTTPException(422, "Envie a capa em JPG, PNG ou WebP.")
    data = await capa.read(plugin_service.COVER_MAX_BYTES + 1)
    await capa.close()
    if len(data) > plugin_service.COVER_MAX_BYTES:
        raise HTTPException(413, "A capa passa de 8 MB.")
    return plugin_service.enviar_capa(db, plugin_id, data, COVERS[extension], user)


@router.post("/admin/labs/plugins/{plugin_id}/instaladores/{sistema}")
async def admin_instalador(
    plugin_id: int,
    sistema: str,
    db: Db,
    user: Admin,
    arquivo: Annotated[UploadFile, File()],
    versao: Annotated[str | None, Form(max_length=20)] = None,
):
    if not (arquivo.filename or "").lower().endswith(".zip"):
        raise HTTPException(422, "Envie o instalador compactado em .zip.")
    data = await arquivo.read(plugin_service.INSTALLER_MAX_BYTES + 1)
    await arquivo.close()
    return plugin_service.enviar_instalador(db, plugin_id, sistema, data, versao, user)


@router.put("/admin/labs/plugins/{plugin_id}/instaladores/{sistema}/link")
def admin_instalador_link(plugin_id: int, sistema: str, payload: PluginInstaladorLink, db: Db, user: Admin):
    if sistema not in plugin_service.SISTEMAS:
        raise HTTPException(422, "Sistema inválido.")
    return plugin_service.definir_link(db, plugin_id, sistema, payload, user)


@router.delete("/admin/labs/plugins/{plugin_id}/instaladores/{sistema}")
def admin_remover_instalador(plugin_id: int, sistema: str, db: Db, user: Admin):
    return plugin_service.remover_instalador(db, plugin_id, sistema, user)


@router.get("/admin/labs/plugins/{plugin_id}/licencas")
def admin_licencas(plugin_id: int, db: Db, user: Admin):
    return plugin_service.licencas(db, plugin_id)


@router.post("/admin/labs/plugins/{plugin_id}/cortesias", status_code=201)
def admin_cortesia(plugin_id: int, payload: PluginCortesia, db: Db, user: Admin):
    return plugin_service.conceder_cortesia(db, plugin_id, payload.cliente_id, user)


@router.post("/admin/labs/licencas/{licenca_id}/revogar")
def admin_revogar(licenca_id: int, payload: PluginRevogacao, db: Db, user: Admin):
    return plugin_service.revogar(db, licenca_id, payload.motivo, user)
