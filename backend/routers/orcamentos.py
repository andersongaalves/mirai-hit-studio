from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from core.dependencies import get_current_user
from schemas.orcamento import (
    OrcamentoCreate,
    OrcamentoResponse,
    OrcamentoStatusUpdate,
    OrcamentoProdutorUpdate,
    OrcamentoObservacoesUpdate,
)

from services.email_service import EmailService
from models import UsuarioModel

import crud.crud_orcamento as crud_orcamento
from services import orcamento_service

router = APIRouter(
    prefix="/orcamentos",
    tags=["Orçamentos"],
)

@router.post(
    "",
    response_model=OrcamentoResponse,
)
def criar_orcamento(
    orcamento: OrcamentoCreate,
    db: Session = Depends(get_db),
):

    novo = orcamento_service.criar(db, orcamento)

    protocolo = (
        f"MHS-"
        f"{novo.data_solicitacao:%Y%m%d}-"
        f"{novo.id:06d}"
    )

    EmailService.enviar_confirmacao(
        novo,
        protocolo,
    )

    EmailService.enviar_notificacao_admin(
        novo,
        protocolo,
    )

    return novo

@router.get(
    "",
    response_model=list[OrcamentoResponse],
)
def listar_orcamentos(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    return crud_orcamento.listar(db)

@router.delete("/{orcamento_id}")
def deletar_orcamento(
    orcamento_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    orcamento = crud_orcamento.buscar_por_id(
        db,
        orcamento_id,
    )

    if not orcamento:
        raise HTTPException(
            status_code=404,
            detail="Orçamento não encontrado",
        )

    db.delete(orcamento)
    db.commit()

    return {
        "message": "Orçamento removido"
    }


@router.patch(
    "/{orcamento_id}/status",
    response_model=OrcamentoResponse,
)
def atualizar_status(
    orcamento_id: int,
    dados: OrcamentoStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    try:
        orcamento = crud_orcamento.atualizar_status(db, orcamento_id, dados.status)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from None

    if not orcamento:
        raise HTTPException(
            status_code=404,
            detail="Orçamento não encontrado",
        )

    return orcamento


@router.post(
    "/{orcamento_id}/enviar-proposta",
    response_model=OrcamentoResponse,
)
def enviar_proposta(
    orcamento_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    raise HTTPException(status_code=409, detail="Use o envio real pelo editor de propostas.")

@router.patch(
    "/{orcamento_id}/produtor",
    response_model=OrcamentoResponse,
)
def alterar_produtor(
    orcamento_id: int,
    dados: OrcamentoProdutorUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    if dados.produtor_id is not None and db.get(UsuarioModel, dados.produtor_id) is None:
        raise HTTPException(status_code=422, detail="Produtor nao encontrado.")
    orcamento = crud_orcamento.atualizar_produtor(
        db,
        orcamento_id,
        dados.produtor_id,
    )

    if not orcamento:
        raise HTTPException(
            status_code=404,
            detail="Orçamento não encontrado",
        )

    return orcamento


@router.patch(
    "/{orcamento_id}/observacoes",
    response_model=OrcamentoResponse,
)
def alterar_observacoes(
    orcamento_id: int,
    dados: OrcamentoObservacoesUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    orcamento = crud_orcamento.atualizar_observacoes(
        db,
        orcamento_id,
        dados.observacoes,
    )

    if not orcamento:
        raise HTTPException(
            status_code=404,
            detail="Orçamento não encontrado",
        )

    return orcamento
