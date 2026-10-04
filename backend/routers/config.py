import models
from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends
from schemas.config import (
    ConfigResponse,
    PortfolioSegmentCatalogResponse,
    PortfolioSegmentCreate,
    PortfolioSegmentDelete,
    PortfolioSegmentOrderUpdate,
    PortfolioSegmentPublicResponse,
    PortfolioSegmentUpdate,
)
from services import portfolio_segments_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/config", tags=["Configurações"])


@router.get("", response_model=ConfigResponse)
def get_config(db: Session = Depends(get_db)):
    return db.query(models.ConfigModel).filter(models.ConfigModel.id == 1).first()


@router.put("", response_model=ConfigResponse)
def update_config(
    novo_config: ConfigResponse,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):

    config = db.query(models.ConfigModel).filter(models.ConfigModel.id == 1).first()

    for key, value in novo_config.model_dump(exclude_none=True).items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)

    return config


@router.get(
    "/portfolio-segments/public",
    response_model=list[PortfolioSegmentPublicResponse],
)
def get_public_portfolio_segments(db: Session = Depends(get_db)):
    return portfolio_segments_service.public_segments(db)


@router.get(
    "/portfolio-segments",
    response_model=PortfolioSegmentCatalogResponse,
)
def get_portfolio_segments(
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return portfolio_segments_service.catalog_response(db)


@router.post(
    "/portfolio-segments",
    response_model=PortfolioSegmentCatalogResponse,
)
def create_portfolio_segment(
    payload: PortfolioSegmentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return portfolio_segments_service.create_segment(db, payload)


@router.patch(
    "/portfolio-segments/{segment_id}",
    response_model=PortfolioSegmentCatalogResponse,
)
def update_portfolio_segment(
    segment_id: str,
    payload: PortfolioSegmentUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return portfolio_segments_service.update_segment(db, segment_id, payload)


@router.put(
    "/portfolio-segments/order",
    response_model=PortfolioSegmentCatalogResponse,
)
def reorder_portfolio_segments(
    payload: PortfolioSegmentOrderUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return portfolio_segments_service.reorder_segments(db, payload)


@router.delete(
    "/portfolio-segments/{segment_id}",
    response_model=PortfolioSegmentCatalogResponse,
)
def delete_portfolio_segment(
    segment_id: str,
    payload: PortfolioSegmentDelete,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return portfolio_segments_service.retire_segment(db, segment_id, payload)
