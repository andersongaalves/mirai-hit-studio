from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas.projeto import (
    ProjetoCreate,
    ProjetoResponse,
)

from core.dependencies import get_current_user

router = APIRouter(
    prefix="/projetos",
    tags=["Projetos"]
)


@router.get("", response_model=list[ProjetoResponse])
def listar_projetos(db: Session = Depends(get_db)):
    return db.query(models.ProjetoModel).all()


@router.post("", response_model=ProjetoResponse)
def criar_projeto(
    proj: ProjetoCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    novo = models.ProjetoModel(
        **proj.model_dump()
    )

    db.add(novo)

    db.commit()

    db.refresh(novo)

    return novo


@router.put("/{id}", response_model=ProjetoResponse)
def atualizar_projeto(
    id: int,
    proj_atualizado: ProjetoCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    projeto = (
        db.query(models.ProjetoModel)
        .filter(models.ProjetoModel.id == id)
        .first()
    )

    if not projeto:
        raise HTTPException(status_code=404)

    for key, value in proj_atualizado.model_dump().items():
        setattr(projeto, key, value)

    db.commit()

    db.refresh(projeto)

    return projeto


@router.delete("/{id}")
def deletar_projeto(
    id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    projeto = (
        db.query(models.ProjetoModel)
        .filter(models.ProjetoModel.id == id)
        .first()
    )

    if not projeto:
        raise HTTPException(status_code=404)

    db.delete(projeto)

    db.commit()

    return {"status": "ok"}