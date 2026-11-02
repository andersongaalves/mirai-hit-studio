"""Pop-ups: the Admin writes them; the client and producer portals show and close them."""
from typing import Annotated

from core.dependencies import get_current_user, require_admin
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response
from schemas.portal_popup import PopupAdminResponse, PopupDados, PopupPortalResponse
from services import portal_popup_service as service
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(tags=["Pop-ups dos portais"])
Db = Annotated[Session, Depends(get_db)]
IdPath = Annotated[int, Path(gt=0)]


def _papel(user):
    role = getattr(user, "role", None)
    if not getattr(user, "ativo", False) or getattr(user, "is_admin", False) or role not in ("cliente", "produtor"):
        raise HTTPException(403, "Pop-ups sao exibidos nos portais de cliente e produtor.")
    return role


@router.get("/admin/popups", response_model=list[PopupAdminResponse])
def admin_list(db: Db, user=Depends(require_admin)):
    return service.listar_admin(db)


@router.post("/admin/popups", response_model=PopupAdminResponse, status_code=201)
def admin_create(dados: PopupDados, db: Db, user=Depends(require_admin)):
    return service.criar(db, user, dados)


@router.put("/admin/popups/{popup_id}", response_model=PopupAdminResponse)
def admin_update(popup_id: IdPath, dados: PopupDados, db: Db, user=Depends(require_admin)):
    return service.atualizar(db, user, popup_id, dados)


@router.delete("/admin/popups/{popup_id}", status_code=204)
def admin_delete(popup_id: IdPath, db: Db, user=Depends(require_admin)):
    service.excluir(db, user, popup_id)
    return Response(status_code=204)


@router.get("/portal/popups", response_model=list[PopupPortalResponse])
def portal_list(db: Db, user=Depends(get_current_user)):
    return service.para_usuario(db, user, _papel(user))


@router.post("/portal/popups/{popup_id}/fechar", status_code=204)
def portal_close(popup_id: IdPath, db: Db, user=Depends(get_current_user)):
    try:
        service.fechar(db, user, _papel(user), popup_id)
    except IntegrityError:
        db.rollback()  # closed twice at the same time: already recorded
    return Response(status_code=204)
