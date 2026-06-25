from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas.servico import (
    ServicoCreate,
    ServicoResponse,
)

from core.dependencies import get_current_user

router = APIRouter(
    prefix="/servicos",
    tags=["Serviços"]
)


@router.get("", response_model=list[ServicoResponse])
def listar_servicos(db: Session = Depends(get_db)):
    return db.query(models.ServicoModel).all()


@router.post("", response_model=ServicoResponse)
def criar_servico(
    servico: ServicoCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    novo = models.ServicoModel(
        **servico.model_dump()
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return novo


@router.put("/{servico_id}", response_model=ServicoResponse)
def atualizar_servico(
    servico_id: int,
    srv_atualizado: ServicoCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    servico = (
        db.query(models.ServicoModel)
        .filter(models.ServicoModel.id == servico_id)
        .first()
    )

    if not servico:
        raise HTTPException(status_code=404)

    for key, value in srv_atualizado.model_dump().items():
        setattr(servico, key, value)

    db.commit()

    db.refresh(servico)

    return servico


@router.delete("/{servico_id}")
def deletar_servico(
    servico_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    servico = (
        db.query(models.ServicoModel)
        .filter(models.ServicoModel.id == servico_id)
        .first()
    )

    if not servico:
        raise HTTPException(status_code=404)

    db.delete(servico)

    db.commit()

    return {"status": "ok"}