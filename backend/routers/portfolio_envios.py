from core.dependencies import require_admin, require_producer
from database import get_db
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from models import PortfolioEnvioModel
from pydantic import ValidationError
from schemas.portfolio_envio import (
    PortfolioEnvioCreate,
    PortfolioEnvioDados,
    PortfolioEnvioResponse,
    PortfolioEnvioRevisao,
)
from services import portfolio_envio_service
from services.storage.contracts import StorageScope
from services.storage.policies import DEFAULT_POLICIES
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


@router.post("/portal/produtor/portfolio/com-capa", response_model=PortfolioEnvioResponse, status_code=201)
async def enviar_com_capa(dados: str = Form(..., max_length=30000), imagem: UploadFile = File(...),
                         db: Session = Depends(get_db), user=Depends(require_producer)):
    try:
        payload = PortfolioEnvioDados.model_validate_json(dados)
    except ValidationError:
        raise HTTPException(422, "Revise os dados e a autorizacao do envio.") from None
    limit = DEFAULT_POLICIES[StorageScope.PUBLIC_IMAGE].max_bytes
    contents = await imagem.read(limit + 1)
    if len(contents) > limit:
        raise HTTPException(413, "A imagem excede o limite de 10 MB.")
    try:
        return await run_in_threadpool(
            portfolio_envio_service.enviar_com_capa, db, user, payload, contents, imagem.content_type or "",
        )
    except HTTPException:
        db.rollback()
        raise


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
