import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from database import get_db
from schemas.proposta import PropostaCreate, PropostaResponse, PropostaUpdate
from services import proposta_service as service
from services import proposta_documento_service as documentos
from services.documento_storage import DocumentoIndisponivel
from services import proposta_comercial_service as comercial

router = APIRouter(tags=["Propostas"], dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)
IdPath = Annotated[int, Path(gt=0)]
Db = Annotated[Session, Depends(get_db)]


def _responder(operacao, *args):
    try:
        return operacao(*args)
    except service.PropostaNaoEncontrada as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except service.PropostaInvalida as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except service.PropostaConflito as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except (DocumentoIndisponivel, comercial.EnvioIndisponivel) as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except SQLAlchemyError:
        logger.error("proposta_database_failed")
        raise HTTPException(status_code=503, detail="Persistencia de propostas indisponivel.") from None


@router.post("/orcamentos/{orcamento_id}/proposta", response_model=PropostaResponse)
def criar(orcamento_id: IdPath, db: Db, dados: PropostaCreate = Body(default=PropostaCreate())):
    return _responder(service.criar_por_orcamento, db, orcamento_id)


@router.get("/propostas/orcamento/{orcamento_id}", response_model=PropostaResponse)
def buscar_por_orcamento(orcamento_id: IdPath, db: Db):
    return _responder(service.buscar_por_orcamento, db, orcamento_id)


@router.get("/propostas/{proposta_id}", response_model=PropostaResponse)
def buscar(proposta_id: IdPath, db: Db):
    return _responder(service.buscar, db, proposta_id)


@router.patch("/propostas/{proposta_id}", response_model=PropostaResponse)
def atualizar(proposta_id: IdPath, dados: PropostaUpdate, db: Db):
    return _responder(service.atualizar, db, proposta_id, dados)


@router.get("/propostas/{proposta_id}/preview", response_class=HTMLResponse)
def preview(proposta_id: IdPath, db: Db):
    return HTMLResponse(_responder(documentos.preview, db, proposta_id), headers={"Cache-Control": "no-store"})


@router.post("/propostas/{proposta_id}/gerar-documento", response_model=PropostaResponse)
def gerar_documento(proposta_id: IdPath, db: Db):
    return _responder(documentos.gerar_documento, db, proposta_id)


@router.get("/propostas/{proposta_id}/documento")
def documento(proposta_id: IdPath, db: Db):
    data, filename = _responder(documentos.obter_documento, db, proposta_id)
    return Response(data, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff"})


@router.post("/propostas/{proposta_id}/enviar", response_model=PropostaResponse)
def enviar(proposta_id: IdPath, request: Request, db: Db, user=Depends(get_current_user)):
    return _responder(
        comercial.enviar,
        db,
        proposta_id,
        user,
        getattr(request.state, "request_id", None),
    )


@router.post("/propostas/{proposta_id}/aprovar", response_model=PropostaResponse)
def aprovar(proposta_id: IdPath, request: Request, db: Db, user=Depends(get_current_user)):
    return _responder(
        comercial.aprovar,
        db,
        proposta_id,
        user,
        getattr(request.state, "request_id", None),
    )
