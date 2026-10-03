from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database import get_db
from models.producao import ProducaoModel
from models.usuario import UsuarioModel
from schemas.producao_arquivo import (
    ProducaoArquivoResponse,
    ProducaoArquivoVisibilidadeRequest,
)
from schemas.repasse_produtor import (
    RepasseCorrecaoRequest,
    RepasseDefinirRequest,
    RepassePagamentoRequest,
    RepasseProdutorResponse,
)
from services import producao_arquivo_service, repasse_produtor_service
from services.producao_arquivo_storage import MAX_FILE_SIZE

router = APIRouter(prefix="/producoes", tags=["Operacao do Produtor"])
Db = Annotated[Session, Depends(get_db)]
CurrentAdmin = Annotated[UsuarioModel, Depends(require_admin)]


def _production(db, production_id):
    model = db.get(ProducaoModel, production_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")
    return model


def _file_error(exc):
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _payout_error(exc):
    status = 404 if isinstance(exc, repasse_produtor_service.RepasseNotFound) else 409
    return HTTPException(status_code=status, detail=str(exc))


async def _contents(file):
    data = await file.read(MAX_FILE_SIZE + 1)
    await file.close()
    return data


@router.get(
    "/{producao_id}/arquivos",
    response_model=list[ProducaoArquivoResponse],
)
def list_files(producao_id: int, db: Db, user: CurrentAdmin):
    _production(db, producao_id)
    return producao_arquivo_service.list_for_admin(db, producao_id)


@router.post(
    "/{producao_id}/arquivos",
    response_model=ProducaoArquivoResponse,
    status_code=201,
)
async def upload_file(
    producao_id: int,
    request: Request,
    db: Db,
    user: CurrentAdmin,
    arquivo: Annotated[UploadFile, File()],
    tipo: Annotated[str, Form()],
    visivel_produtor: Annotated[bool, Form()] = False,
    visivel_cliente: Annotated[bool, Form()] = False,
    substitui_arquivo_id: Annotated[int | None, Form()] = None,
):
    production = _production(db, producao_id)
    try:
        return producao_arquivo_service.upload(
            db,
            production=production,
            actor=user,
            file_type=tipo,
            filename=arquivo.filename or "arquivo",
            mime_type=arquivo.content_type or "application/octet-stream",
            data=await _contents(arquivo),
            visible_to_producer=visivel_produtor,
            visible_to_client=visivel_cliente,
            replaces_id=substitui_arquivo_id,
            request_id=getattr(request.state, "request_id", None),
        )
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None


@router.patch(
    "/{producao_id}/arquivos/{arquivo_id}/visibilidade",
    response_model=ProducaoArquivoResponse,
)
def update_file_visibility(
    producao_id: int,
    arquivo_id: int,
    payload: ProducaoArquivoVisibilidadeRequest,
    request: Request,
    db: Db,
    user: CurrentAdmin,
):
    try:
        model = producao_arquivo_service.get_for_admin(db, producao_id, arquivo_id)
        return producao_arquivo_service.update_visibility(
            db,
            model=model,
            actor=user,
            producer=payload.visivel_produtor,
            client=payload.visivel_cliente,
            request_id=getattr(request.state, "request_id", None),
        )
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None


@router.get("/{producao_id}/arquivos/{arquivo_id}/conteudo")
def download_file(
    producao_id: int,
    arquivo_id: int,
    db: Db,
    user: CurrentAdmin,
):
    try:
        model = producao_arquivo_service.get_for_admin(db, producao_id, arquivo_id)
        content = producao_arquivo_service.read(model)
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None
    filename = quote(model.nome_exibicao, safe="")
    return Response(
        content,
        media_type=model.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get(
    "/{producao_id}/repasse",
    response_model=RepasseProdutorResponse | None,
)
def get_payout(producao_id: int, db: Db, user: CurrentAdmin):
    _production(db, producao_id)
    return repasse_produtor_service.get_admin(db, producao_id)


@router.put("/{producao_id}/repasse", response_model=RepasseProdutorResponse)
def define_payout(
    producao_id: int,
    payload: RepasseDefinirRequest,
    request: Request,
    db: Db,
    user: CurrentAdmin,
):
    try:
        return repasse_produtor_service.define(
            db,
            production_id=producao_id,
            amount=payload.valor_combinado,
            actor=user,
            request_id=getattr(request.state, "request_id", None),
        )
    except repasse_produtor_service.RepasseError as exc:
        raise _payout_error(exc) from None


@router.post(
    "/{producao_id}/repasse/liberar",
    response_model=RepasseProdutorResponse,
)
def release_payout(
    producao_id: int,
    request: Request,
    db: Db,
    user: CurrentAdmin,
):
    try:
        return repasse_produtor_service.release(
            db,
            production_id=producao_id,
            actor=user,
            request_id=getattr(request.state, "request_id", None),
        )
    except repasse_produtor_service.RepasseError as exc:
        raise _payout_error(exc) from None


@router.post(
    "/{producao_id}/repasse/pagar",
    response_model=RepasseProdutorResponse,
)
def pay_payout(
    producao_id: int,
    payload: RepassePagamentoRequest,
    request: Request,
    db: Db,
    user: CurrentAdmin,
):
    try:
        return repasse_produtor_service.mark_paid(
            db,
            production_id=producao_id,
            actor=user,
            reference=payload.referencia_pagamento,
            receipt_id=payload.comprovante_arquivo_id,
            request_id=getattr(request.state, "request_id", None),
        )
    except repasse_produtor_service.RepasseError as exc:
        raise _payout_error(exc) from None


@router.patch(
    "/{producao_id}/repasse/correcao",
    response_model=RepasseProdutorResponse,
)
def correct_payout(
    producao_id: int,
    payload: RepasseCorrecaoRequest,
    request: Request,
    db: Db,
    user: CurrentAdmin,
):
    try:
        return repasse_produtor_service.correct(
            db,
            production_id=producao_id,
            actor=user,
            fields=payload.model_dump(exclude_unset=True),
            request_id=getattr(request.state, "request_id", None),
        )
    except repasse_produtor_service.RepasseError as exc:
        raise _payout_error(exc) from None
