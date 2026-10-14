from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.dependencies import require_admin, require_client, require_producer
from database import get_db
from schemas.portal_config import (
    PortalConfigAdminResponse,
    PortalConfigPublishRequest,
    PortalConfigResponse,
    PortalConfigRestoreRequest,
    PortalConfigVersion,
)
from services import portal_config_service as service

router = APIRouter(tags=["Configuração dos portais"])
Db = Annotated[Session, Depends(get_db)]
Portal = Literal["cliente", "produtor"]


def _error(exc):
    if isinstance(exc, service.PortalConfigNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, service.PortalConfigConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/portal/cliente/configuracao", response_model=PortalConfigResponse)
def client_settings(db: Db, user=Depends(require_client)):
    return service.active(db, "cliente")


@router.get("/portal/produtor/configuracao", response_model=PortalConfigResponse)
def producer_settings(db: Db, user=Depends(require_producer)):
    return service.active(db, "produtor")


@router.get("/admin/portais/{portal}/configuracao", response_model=PortalConfigAdminResponse)
def admin_settings(portal: Portal, db: Db, user=Depends(require_admin)):
    return {**service.active(db, portal), "padrao": service.defaults(portal)}


@router.get("/admin/portais/{portal}/configuracao/versoes", response_model=list[PortalConfigVersion])
def admin_versions(portal: Portal, db: Db, user=Depends(require_admin)):
    return service.versions(db, portal)


@router.put("/admin/portais/{portal}/configuracao", response_model=PortalConfigResponse)
def admin_publish(
    portal: Portal,
    payload: PortalConfigPublishRequest,
    request: Request,
    db: Db,
    user=Depends(require_admin),
):
    try:
        return service.publish(
            db, portal, payload.config, actor=user, base_versao=payload.base_versao,
            request_id=getattr(request.state, "request_id", None),
        )
    except service.PortalConfigError as exc:
        raise _error(exc) from None


@router.post(
    "/admin/portais/{portal}/configuracao/versoes/{versao}/restaurar",
    response_model=PortalConfigResponse,
)
def admin_restore(
    portal: Portal,
    versao: int,
    payload: PortalConfigRestoreRequest,
    request: Request,
    db: Db,
    user=Depends(require_admin),
):
    try:
        return service.restore(
            db, portal, versao, actor=user, base_versao=payload.base_versao,
            request_id=getattr(request.state, "request_id", None),
        )
    except service.PortalConfigError as exc:
        raise _error(exc) from None
