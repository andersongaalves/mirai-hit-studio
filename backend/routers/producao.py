from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db

from core.dependencies import get_current_user

from schemas.producao import (
    ProducaoCreate,
    ProducaoResponse,
    ProducaoStatusUpdate,
    ProducaoEtapasUpdate,
    ProducaoPrazoUpdate,
    ProducaoObservacoesUpdate,
)

from crud import crud_producao
from models.orcamento import OrcamentoModel
from models.producao import ProducaoModel
from models.usuario import UsuarioModel
from services import audit_service

router = APIRouter(prefix="/producoes", tags=["Produções"])


# ===========================
# CRIAR
# ===========================


@router.post("", response_model=ProducaoResponse)
def criar_producao(
    dados: ProducaoCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    if dados.produtor_id and not db.get(UsuarioModel, dados.produtor_id):
        raise HTTPException(status_code=422, detail="Produtor não encontrado")
    if dados.orcamento_id and not db.get(OrcamentoModel, dados.orcamento_id):
        raise HTTPException(status_code=422, detail="Orçamento não encontrado")
    if dados.orcamento_id and crud_producao.buscar_por_orcamento(
        db, dados.orcamento_id
    ):
        raise HTTPException(
            status_code=409,
            detail="Já existe produção para este orçamento",
        )
    try:
        producao = crud_producao.criar(db, dados.model_dump())
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Produção já vinculada; atualize a listagem",
        ) from None
    return crud_producao.buscar(db, producao.id)


# ===========================
# LISTAR
# ===========================


@router.get("", response_model=list[ProducaoResponse])
def listar_producoes(db: Session = Depends(get_db), user=Depends(get_current_user)):

    return crud_producao.listar(db)


@router.get("/{producao_id}", response_model=ProducaoResponse)
def obter_producao(
    producao_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    producao = crud_producao.buscar(db, producao_id)
    if not producao:
        raise HTTPException(status_code=404, detail="Produção não encontrada")
    return producao


# ===========================
# STATUS
# ===========================


@router.patch("/{producao_id}/status", response_model=ProducaoResponse)
def atualizar_status(
    producao_id: int,
    dados: ProducaoStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    atual = db.get(ProducaoModel, producao_id)
    old_status = atual.status if atual else None
    producao = crud_producao.atualizar_status_sem_commit(db, producao_id, dados.status)

    if not producao:

        raise HTTPException(status_code=404, detail="Produção não encontrada")

    if old_status != producao.status:
        audit_service.record(
            db,
            actor=user,
            action="production.status_changed",
            entity_type="production",
            entity_id=producao.id,
            metadata={"old_status": old_status, "new_status": producao.status},
            request_id=getattr(request.state, "request_id", None),
        )
    db.commit()

    return crud_producao.buscar(db, producao_id)


@router.patch("/{producao_id}/etapas", response_model=ProducaoResponse)
def atualizar_etapas(
    producao_id: int,
    dados: ProducaoEtapasUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    producao = crud_producao.atualizar_etapas(db, producao_id, dados.etapas)

    if not producao:

        raise HTTPException(status_code=404, detail="Produção não encontrada")

    return crud_producao.buscar(db, producao_id)


@router.patch("/{producao_id}/prazo", response_model=ProducaoResponse)
def alterar_prazo(
    producao_id: int,
    dados: ProducaoPrazoUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):

    producao = crud_producao.atualizar_prazo(db, producao_id, dados.prazo_entrega)

    if not producao:

        raise HTTPException(404, "Produção não encontrada")

    return crud_producao.buscar(db, producao_id)


@router.patch("/{producao_id}/observacoes", response_model=ProducaoResponse)
def atualizar_observacoes(
    producao_id: int,
    dados: ProducaoObservacoesUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    producao = crud_producao.atualizar_observacoes(
        db, producao_id, dados.observacoes
    )
    if not producao:
        raise HTTPException(status_code=404, detail="Produção não encontrada")
    return crud_producao.buscar(db, producao_id)
