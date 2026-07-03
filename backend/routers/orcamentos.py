from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException

from database import get_db
from schemas.orcamento import (
    OrcamentoCreate,
    OrcamentoResponse,
    OrcamentoStatusUpdate,
    OrcamentoProdutorUpdate
)
from core.dependencies import get_current_user
from services.email_service import EmailService
import crud.crud_orcamento as crud_orcamento

import models

router = APIRouter(
    prefix="/orcamentos",
    tags=["Orçamentos"]
)


@router.post("", response_model=OrcamentoResponse)
def criar_orcamento(
    orcamento: OrcamentoCreate,
    db: Session = Depends(get_db)
):

    novo = models.OrcamentoModel(
        **orcamento.model_dump()
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    protocolo = (
        f"MHS-"
        f"{novo.data_solicitacao:%Y%m%d}-"
        f"{novo.id:06d}"
    )

    
    EmailService.enviar_confirmacao(
    novo,
    protocolo
    )

    EmailService.enviar_notificacao_admin(
        novo,
        protocolo
    )

    return novo


@router.get("", response_model=list[OrcamentoResponse])
def listar_orcamentos(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    return (
        db.query(models.OrcamentoModel)
        .order_by(models.OrcamentoModel.id.desc())
        .all()
    )

@router.delete("/{orcamento_id}")
def deletar_orcamento(
    orcamento_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    orcamento = (
        db.query(models.OrcamentoModel)
        .filter(
            models.OrcamentoModel.id == orcamento_id
        )
        .first()
    )

    if not orcamento:

        raise HTTPException(
            status_code=404,
            detail="Orçamento não encontrado"
        )

    db.delete(orcamento)

    db.commit()

    return {
        "message": "Orçamento removido com sucesso"
    }

@router.patch(
    "/{orcamento_id}/status",
    response_model=OrcamentoResponse
)
def atualizar_status(
    orcamento_id: int,
    dados: OrcamentoStatusUpdate,
    db: Session = Depends(get_db)
):

    orcamento = crud_orcamento.atualizar_status(
        db,
        orcamento_id,
        dados.status.value
    )

    if not orcamento:

        raise HTTPException(
            status_code=404,
            detail="Orçamento não encontrado."
        )

    return orcamento

@router.patch(
    "/{orcamento_id}/produtor",
    response_model=OrcamentoResponse
)
def alterar_produtor(
    orcamento_id: int,

    dados: OrcamentoProdutorUpdate,

    db: Session = Depends(get_db),

    user=Depends(get_current_user)
):


    orcamento = (
        crud_orcamento.atualizar_produtor(
            db,
            orcamento_id,
            dados.produtor_id
        )
    )


    if not orcamento:

        raise HTTPException(
            status_code=404,
            detail="Orçamento não encontrado"
        )


    return orcamento