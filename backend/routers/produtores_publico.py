"""Public producer pages: anyone can see a producer's work, metrics and beats."""
from typing import Annotated

from database import get_db
from fastapi import APIRouter, Depends, Path
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from services import produtor_perfil_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/produtores", tags=["Produtores (público)"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/{slug}")
def pagina_publica(slug: Annotated[str, Path(max_length=60)], db: Db):
    return JSONResponse(jsonable_encoder(produtor_perfil_service.publico(db, slug)),
                        headers={"Cache-Control": "public, max-age=60"})
