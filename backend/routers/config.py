from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas.config import ConfigResponse

from core.dependencies import get_current_user

router = APIRouter(
    prefix="/config",
    tags=["Configurações"]
)


@router.get("", response_model=ConfigResponse)
def get_config(db: Session = Depends(get_db)):
    return (
        db.query(models.ConfigModel)
        .filter(models.ConfigModel.id == 1)
        .first()
    )


@router.put("", response_model=ConfigResponse)
def update_config(
    novo_config: ConfigResponse,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    config = (
        db.query(models.ConfigModel)
        .filter(models.ConfigModel.id == 1)
        .first()
    )

    for key, value in novo_config.model_dump(exclude_none=True).items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)

    return config