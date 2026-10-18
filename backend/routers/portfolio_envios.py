from core.dependencies import require_admin, require_producer
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import PortfolioEnvioModel
from schemas.portfolio_envio import (
    PortfolioEnvioCreate,
    PortfolioEnvioResponse,
    PortfolioEnvioRevisao,
)
from services import portfolio_envio_service
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Envios ao portfolio"])


@router.get("/portal/produtor/portfolio", response_model=list[PortfolioEnvioResponse])
def meus_envios(db: Session = Depends(get_db), user=Depends(require_producer)):
    return db.scalars(select(PortfolioEnvioModel).where(
        PortfolioEnvioModel.produtor_id == user.id,
    ).order_by(PortfolioEnvioModel.id.desc())).all()


@router.post("/portal/produtor/portfolio", response_model=PortfolioEnvioResponse, status_code=201)
def enviar(payload: PortfolioEnvioCreate, db: Session = Depends(get_db), user=Depends(require_producer)):
    return portfolio_envio_service.enviar(db, user, payload)


@router.get("/projetos/envios/admin", response_model=list[PortfolioEnvioResponse])
def envios_admin(db: Session = Depends(get_db), user=Depends(require_admin)):
    return db.scalars(select(PortfolioEnvioModel).order_by(PortfolioEnvioModel.id.desc())).all()


@router.post("/projetos/envios/{envio_id}/revisao", response_model=PortfolioEnvioResponse)
def revisar(envio_id: int, payload: PortfolioEnvioRevisao,
            db: Session = Depends(get_db), user=Depends(require_admin)):
    try:
        return portfolio_envio_service.revisar(db, user, envio_id, payload)
    except HTTPException:
        db.rollback()
        raise
