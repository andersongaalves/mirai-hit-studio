from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.dependencies import require_client
from database import get_db
from models.usuario import UsuarioModel
from schemas.portal_cliente import (
    FinanceiroClienteResponse,
    ProducaoArquivoClienteResponse,
    ProducaoClienteResponse,
)
from services import financial_service, portal_cliente_service, producao_arquivo_service
from services.producao_arquivo_storage import MAX_FILE_SIZE

router = APIRouter(prefix="/portal/cliente", tags=["Portal do Cliente"])
Db = Annotated[Session, Depends(get_db)]
CurrentClient = Annotated[UsuarioModel, Depends(require_client)]
FINAL_STATUSES = {"finalizado", "entregue"}


def _file_error(exc):
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _client_file(model, user_id):
    return {
        "id": model.id,
        "producao_id": model.producao_id,
        "tipo": model.tipo,
        "nome_exibicao": model.nome_exibicao,
        "mime_type": model.mime_type,
        "tamanho_bytes": model.tamanho_bytes,
        "sha256": model.sha256,
        "grupo_versao": model.grupo_versao,
        "versao": model.versao,
        "substitui_arquivo_id": model.substitui_arquivo_id,
        "enviado_por_mim": model.remetente_usuario_id == user_id,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


@router.get("/producoes", response_model=list[ProducaoClienteResponse])
def listar_minhas_producoes(db: Db, user: CurrentClient):
    return portal_cliente_service.listar_producoes(db, user.cliente_id)


@router.get("/producoes/historico", response_model=list[ProducaoClienteResponse])
def listar_meu_historico(db: Db, user: CurrentClient):
    return portal_cliente_service.listar_historico(db, user.cliente_id)


@router.get("/producoes/{producao_id}", response_model=ProducaoClienteResponse)
def obter_minha_producao(producao_id: int, db: Db, user: CurrentClient):
    try:
        return portal_cliente_service.buscar_producao(db, producao_id, user.cliente_id)
    except portal_cliente_service.ProducaoClienteNaoEncontrada:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.") from None


@router.get(
    "/producoes/{producao_id}/financeiro",
    response_model=FinanceiroClienteResponse,
)
def obter_meu_financeiro(producao_id: int, db: Db, user: CurrentClient):
    try:
        return portal_cliente_service.buscar_financeiro(db, producao_id, user.cliente_id)
    except portal_cliente_service.ProducaoClienteNaoEncontrada:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.") from None
    except financial_service.FinanceiroConflito:
        raise HTTPException(status_code=409, detail="Situacao financeira inconsistente.") from None


@router.get(
    "/producoes/{producao_id}/arquivos",
    response_model=list[ProducaoArquivoClienteResponse],
)
def listar_meus_arquivos(producao_id: int, db: Db, user: CurrentClient):
    try:
        return [
            _client_file(model, user.id)
            for model in producao_arquivo_service.list_for_client(
                db,
                producao_id,
                user.cliente_id,
            )
        ]
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None


@router.post(
    "/producoes/{producao_id}/arquivos",
    response_model=ProducaoArquivoClienteResponse,
    status_code=201,
)
async def enviar_material(
    producao_id: int,
    request: Request,
    db: Db,
    user: CurrentClient,
    arquivo: Annotated[UploadFile, File()],
    tipo: Annotated[str, Form()],
    substitui_arquivo_id: Annotated[int | None, Form()] = None,
):
    try:
        production = portal_cliente_service.buscar_producao(db, producao_id, user.cliente_id)
    except portal_cliente_service.ProducaoClienteNaoEncontrada:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.") from None
    if production.status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Esta producao nao aceita novos materiais.")
    if tipo not in producao_arquivo_service.CLIENT_UPLOAD_TYPES:
        raise HTTPException(status_code=422, detail="Tipo de arquivo nao permitido ao cliente.")
    data = await arquivo.read(MAX_FILE_SIZE + 1)
    await arquivo.close()
    try:
        model = producao_arquivo_service.upload(
            db,
            production=production,
            actor=user,
            file_type=tipo,
            filename=arquivo.filename or "arquivo",
            mime_type=arquivo.content_type or "application/octet-stream",
            data=data,
            visible_to_producer=True,
            visible_to_client=True,
            replaces_id=substitui_arquivo_id,
            replacement_actor_id=user.id,
            request_id=getattr(request.state, "request_id", None),
        )
        return _client_file(model, user.id)
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None


@router.get("/arquivos/{arquivo_id}/conteudo")
def baixar_meu_arquivo(arquivo_id: int, db: Db, user: CurrentClient):
    try:
        model = producao_arquivo_service.get_for_client(db, arquivo_id, user.cliente_id)
        content = producao_arquivo_service.read(model)
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None
    filename = quote(model.nome_exibicao, safe="")
    return Response(
        content,
        media_type=model.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Cache-Control": "private, no-store",
        },
    )
