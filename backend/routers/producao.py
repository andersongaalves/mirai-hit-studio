from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from database import get_db

from core.dependencies import get_current_user

from schemas.producao import (
    ProducaoCreate,
    ProducaoResponse,
    ProducaoStatusUpdate
)

from crud import crud_producao


router = APIRouter(
    prefix="/producoes",
    tags=["Produções"]
)


# ===========================
# CRIAR
# ===========================

@router.post(
    "",
    response_model=ProducaoResponse
)
def criar_producao(
    dados: ProducaoCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    return crud_producao.criar(

        db,

        dados.model_dump()

    )


# ===========================
# LISTAR
# ===========================

@router.get(
    "",
    response_model=list[ProducaoResponse]
)
def listar_producoes(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    return crud_producao.listar(
        db
    )


# ===========================
# STATUS
# ===========================

@router.patch(
    "/{producao_id}/status",
    response_model=ProducaoResponse
)
def atualizar_status(

    producao_id: int,

    dados: ProducaoStatusUpdate,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)

):

    producao = (
        crud_producao.atualizar_status(

            db,

            producao_id,

            dados.status

        )
    )


    if not producao:

        raise HTTPException(
            status_code=404,
            detail="Produção não encontrada"
        )


    return producao