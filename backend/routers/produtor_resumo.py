from typing import Annotated

from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from services import produtor_resumo_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/produtores", tags=["Produtores (Admin)"])


@router.get("/{produtor_id}/resumo")
def resumo(
    produtor_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[object, Depends(require_admin)],
):
    # AUD6-S09-002: read-only overview; the same data the Admin already sees per section.
    try:
        return produtor_resumo_service.carregar(db, produtor_id)
    except produtor_resumo_service.ProdutorNaoEncontrado as error:
        raise HTTPException(404, str(error)) from None
