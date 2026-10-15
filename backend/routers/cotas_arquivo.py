"""File quotas per contract (Roadmap 3.0, 5.09)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from core.dependencies import require_admin, require_client, require_producer
from database import get_db
from schemas.cota_arquivo import CotaArquivo, CotasProducaoResponse, CotasUpdate
from services import cota_arquivo_service as service
from services import producao_arquivo_service
from services import producao_etapa_service as producoes

router = APIRouter(tags=["Cotas de arquivos"])
Db = Annotated[Session, Depends(get_db)]
IdPath = Annotated[int, Path(gt=0)]


def _request_id(request: Request):
    return getattr(request.state, "request_id", None)


def _producao(db, papel, producao_id, user):
    try:
        return producoes.producao_para(db, papel, producao_id, user)
    except producoes.EtapaError:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.") from None


@router.get("/servicos/{servico_id}/cotas-arquivos", response_model=list[CotaArquivo])
def service_quotas(servico_id: IdPath, db: Db, user=Depends(require_admin)):
    try:
        return service.cotas_servico(db, servico_id)
    except service.CotaNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.put("/servicos/{servico_id}/cotas-arquivos", response_model=list[CotaArquivo])
def replace_service_quotas(servico_id: IdPath, dados: CotasUpdate, request: Request, db: Db,
                           user=Depends(require_admin)):
    try:
        return service.substituir_servico(db, servico_id, dados.cotas, actor=user, request_id=_request_id(request))
    except service.CotaNaoEncontrada as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.get("/producoes/{producao_id}/cotas-arquivos", response_model=CotasProducaoResponse)
def production_quotas(producao_id: IdPath, db: Db, user=Depends(require_admin)):
    return service.listar_producao(db, _producao(db, "admin", producao_id, user))


@router.put("/producoes/{producao_id}/cotas-arquivos", response_model=CotasProducaoResponse)
def replace_production_quotas(producao_id: IdPath, dados: CotasUpdate, request: Request, db: Db,
                              user=Depends(require_admin)):
    producao = _producao(db, "admin", producao_id, user)
    return service.substituir_producao(db, producao, dados.cotas, actor=user, request_id=_request_id(request))


@router.get("/portal/cliente/producoes/{producao_id}/cotas-arquivos", response_model=CotasProducaoResponse)
def client_quotas(producao_id: IdPath, db: Db, user=Depends(require_client)):
    producao = _producao(db, "cliente", producao_id, user)
    return service.listar_producao(db, producao, tipos=tuple(producao_arquivo_service.CLIENT_UPLOAD_TYPES))


@router.get("/portal/produtor/producoes/{producao_id}/cotas-arquivos", response_model=CotasProducaoResponse)
def producer_quotas(producao_id: IdPath, db: Db, user=Depends(require_producer)):
    producao = _producao(db, "produtor", producao_id, user)
    return service.listar_producao(db, producao, tipos=tuple(producao_arquivo_service.PRODUCER_UPLOAD_TYPES))
