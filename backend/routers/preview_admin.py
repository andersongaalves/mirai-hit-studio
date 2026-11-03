"""Admin "Pré-visualização": every screen of the site and the portals, inside the Admin."""
from typing import Annotated

from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from services import preview_admin_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/preview", tags=["Pré-visualização (Admin)"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[object, Depends(require_admin)]


class SessaoPreview(BaseModel):
    usuario_id: int = Field(gt=0)


@router.get("/contas")
def contas(db: Db, user: Admin, portal: Annotated[str | None, Query(pattern="^(cliente|produtor)$")] = None,
           busca: Annotated[str, Query(max_length=80)] = ""):
    return preview_admin_service.contas(db, portal=portal, busca=busca)


@router.post("/sessao", status_code=201)
def abrir_sessao(dados: SessaoPreview, request: Request, db: Db, user: Admin):
    return preview_admin_service.abrir(db, user, dados.usuario_id, getattr(request.state, "request_id", None))
