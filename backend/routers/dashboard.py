from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database import get_db
from schemas.dashboard import DashboardResponse
from services import dashboard_service


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
def obter_dashboard(
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return dashboard_service.carregar(db)
