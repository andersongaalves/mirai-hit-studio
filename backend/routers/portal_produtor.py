from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.dependencies import require_producer
from crud import crud_producao
from database import get_db
from models.orcamento import OrcamentoModel
from models.portal_produtor import ProducaoArquivoModel
from models.usuario import UsuarioModel
from schemas.portal_produtor import ProducaoProdutorResponse
from schemas.producao import ProducaoStatusUpdate
from schemas.producao_arquivo import ProducaoArquivoResponse
from schemas.repasse_produtor import RepasseProdutorResponse
from services import audit_service, politica_service, producao_arquivo_service, repasse_produtor_service
from services.producao_arquivo_storage import MAX_FILE_SIZE

router = APIRouter(prefix="/portal/produtor", tags=["Portal do Produtor"])
Db = Annotated[Session, Depends(get_db)]
CurrentProducer = Annotated[UsuarioModel, Depends(require_producer)]

def _com_papel(producao, user):
    data = ProducaoProdutorResponse.model_validate(producao).model_dump()
    data["coordenador"] = producao.produtor_id == user.id
    return data


def _detalhe(db, producao, user):
    """Called only after the coordinator/stage-owner scoped production lookup."""
    data = _com_papel(producao, user)
    if politica_service.vigentes(db, producao.id)["produtor_ve_contato_cliente"]:
        orcamento = db.get(OrcamentoModel, producao.orcamento_id)
        cliente = orcamento.cliente if orcamento is not None else None
        if cliente is not None and cliente.ativo:
            data["contato_cliente"] = {
                "nome": cliente.nome,
                "email": cliente.email,
                "whatsapp": cliente.telefone,
            }
    return data


PRODUCER_STATUS_TRANSITIONS = {
    "aguardando_inicio": {"em_producao"},
    "em_producao": {"revisao"},
    "revisao": {"em_producao"},
}


@router.get(
    "/producoes",
    response_model=list[ProducaoProdutorResponse],
    response_model_exclude={"__all__": {"contato_cliente"}},
)
def listar_minhas_producoes(
    db: Db,
    user: CurrentProducer,
):
    return [_com_papel(producao, user) for producao in crud_producao.listar_por_produtor(db, user.id)]


@router.get("/producoes/{producao_id}", response_model=ProducaoProdutorResponse)
def obter_minha_producao(
    producao_id: int,
    db: Db,
    user: CurrentProducer,
):
    producao = crud_producao.buscar_por_produtor(db, producao_id, user.id)
    if not producao:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")
    return _detalhe(db, producao, user)


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
    if producao.produtor_id != user.id:
        # 5.07: stage owners work on their stages; the overall progress belongs to the coordinator.
        raise HTTPException(status_code=403, detail="Somente o produtor coordenador altera o andamento geral.")

    status_anterior = producao.status
    if dados.status == status_anterior:
        return _detalhe(db, producao, user)

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
    return _detalhe(db, producao, user)


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
    observacao: Annotated[str | None, Form(max_length=1000)] = None,
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
            # 5.10: previews reach the client at once unless the contract asks for admin approval.
            visible_to_client=tipo == "previa"
            and politica_service.vigentes(db, production.id)["publicacao_previa"] == "automatica",
            replaces_id=substitui_arquivo_id,
            replacement_audience="produtor",
            note=observacao,
            enforce_quota=True,  # 5.09: contractual file quotas.
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
