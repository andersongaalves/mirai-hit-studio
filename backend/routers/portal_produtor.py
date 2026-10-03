from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.dependencies import require_producer
from crud import crud_producao
from database import get_db
from models.portal_produtor import ProducaoArquivoModel
from models.usuario import UsuarioModel
from schemas.portal_produtor import ProducaoProdutorResponse
from schemas.producao import ProducaoStatusUpdate
from schemas.producao_arquivo import ProducaoArquivoResponse
from schemas.repasse_produtor import RepasseProdutorResponse
from services import audit_service, producao_arquivo_service, repasse_produtor_service
from services.producao_arquivo_storage import MAX_FILE_SIZE

router = APIRouter(prefix="/portal/produtor", tags=["Portal do Produtor"])
Db = Annotated[Session, Depends(get_db)]
CurrentProducer = Annotated[UsuarioModel, Depends(require_producer)]

PRODUCER_STATUS_TRANSITIONS = {
    "aguardando_inicio": {"em_producao"},
    "em_producao": {"revisao"},
    "revisao": {"em_producao"},
}


@router.get("/producoes", response_model=list[ProducaoProdutorResponse])
def listar_minhas_producoes(
    db: Db,
    user: CurrentProducer,
):
    return crud_producao.listar_por_produtor(db, user.id)


@router.get("/producoes/{producao_id}", response_model=ProducaoProdutorResponse)
def obter_minha_producao(
    producao_id: int,
    db: Db,
    user: CurrentProducer,
):
    producao = crud_producao.buscar_por_produtor(db, producao_id, user.id)
    if not producao:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")
    return producao


@router.patch(
    "/producoes/{producao_id}/status",
    response_model=ProducaoProdutorResponse,
)
def atualizar_andamento(
    producao_id: int,
    dados: ProducaoStatusUpdate,
    request: Request,
    db: Db,
    user: CurrentProducer,
):
    producao = crud_producao.buscar_por_produtor(db, producao_id, user.id)
    if not producao:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")

    status_anterior = producao.status
    if dados.status == status_anterior:
        return producao

    permitidos = PRODUCER_STATUS_TRANSITIONS.get(status_anterior, set())
    if dados.status not in permitidos:
        raise HTTPException(
            status_code=409,
            detail="Transicao de andamento nao permitida.",
        )

    producao.status = dados.status
    audit_service.record(
        db,
        actor=user,
        action="production.progress_changed",
        entity_type="production",
        entity_id=producao.id,
        metadata={"old_status": status_anterior, "new_status": dados.status},
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    db.refresh(producao)
    return producao


def _file_error(exc):
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, producao_arquivo_service.ProducaoArquivoUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/producoes/{producao_id}/arquivos",
    response_model=list[ProducaoArquivoResponse],
)
def listar_arquivos(
    producao_id: int,
    db: Db,
    user: CurrentProducer,
):
    try:
        return producao_arquivo_service.list_for_producer(db, producao_id, user.id)
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None


@router.post(
    "/producoes/{producao_id}/arquivos",
    response_model=ProducaoArquivoResponse,
    status_code=201,
)
async def enviar_arquivo(
    producao_id: int,
    request: Request,
    db: Db,
    user: CurrentProducer,
    arquivo: Annotated[UploadFile, File()],
    tipo: Annotated[str, Form()],
    substitui_arquivo_id: Annotated[int | None, Form()] = None,
):
    production = crud_producao.buscar_por_produtor(db, producao_id, user.id)
    if not production:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")
    if tipo not in producao_arquivo_service.PRODUCER_UPLOAD_TYPES:
        raise HTTPException(status_code=422, detail="Tipo de arquivo nao permitido ao produtor.")
    data = await arquivo.read(MAX_FILE_SIZE + 1)
    await arquivo.close()
    try:
        return producao_arquivo_service.upload(
            db,
            production=production,
            actor=user,
            file_type=tipo,
            filename=arquivo.filename or "arquivo",
            mime_type=arquivo.content_type or "application/octet-stream",
            data=data,
            visible_to_producer=True,
            visible_to_client=False,
            replaces_id=substitui_arquivo_id,
            request_id=getattr(request.state, "request_id", None),
        )
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None


@router.get("/arquivos/{arquivo_id}/conteudo")
def baixar_arquivo(
    arquivo_id: int,
    db: Db,
    user: CurrentProducer,
):
    try:
        model = producao_arquivo_service.get_for_producer(db, arquivo_id, user.id)
        content = producao_arquivo_service.read(model)
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None
    filename = quote(model.nome_exibicao, safe="")
    return Response(
        content,
        media_type=model.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/repasses", response_model=list[RepasseProdutorResponse])
def listar_repasses(db: Db, user: CurrentProducer):
    return repasse_produtor_service.list_for_producer(db, user.id)


@router.get("/repasses/{repasse_id}/comprovante")
def baixar_comprovante(
    repasse_id: int,
    db: Db,
    user: CurrentProducer,
):
    try:
        repasse = repasse_produtor_service.get_for_producer(db, repasse_id, user.id)
    except repasse_produtor_service.RepasseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    if repasse.comprovante_arquivo_id is None:
        raise HTTPException(status_code=404, detail="Comprovante nao encontrado.")
    model = db.get(ProducaoArquivoModel, repasse.comprovante_arquivo_id)
    if (
        model is None
        or model.producao_id != repasse.producao_id
        or not model.visivel_produtor
    ):
        raise HTTPException(status_code=404, detail="Comprovante nao encontrado.")
    try:
        content = producao_arquivo_service.read(model)
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None
    filename = quote(model.nome_exibicao, safe="")
    return Response(
        content,
        media_type=model.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
