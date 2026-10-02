from typing import Annotated

from core.dependencies import require_producer
from crud import crud_producao
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.usuario import UsuarioModel
from schemas.portal_produtor import ProducaoProdutorResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/portal/produtor", tags=["Portal do Produtor"])
Db = Annotated[Session, Depends(get_db)]
CurrentProducer = Annotated[UsuarioModel, Depends(require_producer)]


@router.get("/producoes", response_model=list[ProducaoProdutorResponse])
def listar_minhas_producoes(
    db: Db,
    user: CurrentProducer,
):
    return crud_producao.listar_por_produtor(db, user.id)


@router.get("/producoes/{producao_id}", response_model=ProducaoProdutorResponse)
def obter_minha_producao(
    producao_id: int,
    db: Db,
    user: CurrentProducer,
):
    producao = crud_producao.buscar_por_produtor(db, producao_id, user.id)
    if not producao:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")
    return producao
