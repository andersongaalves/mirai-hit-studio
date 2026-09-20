from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas.projeto import (
    ProjetoCreate,
    ProjetoResponse,
)

from core.dependencies import require_admin

router = APIRouter(prefix="/projetos", tags=["Projetos"])

PUBLIC_VERTICALS = ("artists", "creators", "media_games")
PUBLIC_CASE_TYPES = ("client_case", "demo", "concept_project", "study")


@router.get("", response_model=list[ProjetoResponse])
def listar_projetos(db: Session = Depends(get_db)):
    return (
        db.query(models.ProjetoModel)
        .filter(
            models.ProjetoModel.vertical.in_(PUBLIC_VERTICALS),
            models.ProjetoModel.case_type.in_(PUBLIC_CASE_TYPES),
        )
        .all()
    )


@router.get("/admin", response_model=list[ProjetoResponse])
def listar_projetos_admin(
    db: Session = Depends(get_db), user=Depends(require_admin)
):
    return db.query(models.ProjetoModel).all()


@router.post("", response_model=ProjetoResponse)
def criar_projeto(
    proj: ProjetoCreate, db: Session = Depends(get_db), user=Depends(require_admin)
):

    novo = models.ProjetoModel(**proj.model_dump())

    db.add(novo)

    db.commit()

    db.refresh(novo)

    return novo


@router.put("/{id}", response_model=ProjetoResponse)
def atualizar_projeto(
    id: int,
    proj_atualizado: ProjetoCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):

    projeto = db.query(models.ProjetoModel).filter(models.ProjetoModel.id == id).first()

    if not projeto:
        raise HTTPException(status_code=404)

    for key, value in proj_atualizado.model_dump().items():
        setattr(projeto, key, value)

    db.commit()

    db.refresh(projeto)

    return projeto


@router.delete("/{id}")
def deletar_projeto(
    id: int, db: Session = Depends(get_db), user=Depends(require_admin)
):

    projeto = db.query(models.ProjetoModel).filter(models.ProjetoModel.id == id).first()

    if not projeto:
        raise HTTPException(status_code=404)

    db.delete(projeto)

    db.commit()

    return {"status": "ok"}
