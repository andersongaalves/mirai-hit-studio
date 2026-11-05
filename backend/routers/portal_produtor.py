from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from core.dependencies import require_producer
from crud import crud_producao
from database import get_db
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from models.orcamento import OrcamentoModel
from models.portal_produtor import ProducaoArquivoModel
from models.usuario import UsuarioModel
from schemas.portal_produtor import ProducaoProdutorResponse
from schemas.producao import ProducaoStatusUpdate
from schemas.producao_arquivo import (
    ProducaoArquivoEdicaoRequest,
    ProducaoArquivoObservacaoRequest,
    ProducaoArquivoResponse,
)
from schemas.producao_entrega import (
    ProducaoEntregaFinalResponse,
    ProducaoEntregaFinalUpdate,
)
from schemas.repasse_produtor import RepasseProdutorResponse
from schemas.usuario import (
    PerfilPaginaUpdate,
    PerfilProdutorCpfUpdate,
    PerfilProdutorResponse,
    mascarar_cpf,
)
from services import (
    audit_service,
    politica_service,
    producao_arquivo_service,
    producao_entrega_service,
    repasse_produtor_service,
)
from services.producao_arquivo_storage import MAX_FILE_SIZE
from sqlalchemy.orm import Session

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


def _delivery_error(exc):
    if isinstance(exc, producao_entrega_service.ProducaoEntregaConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, producao_entrega_service.ProducaoEntregaUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _upload_mime(upload):
    extension = (upload.filename or "").lower().rsplit(".", 1)[-1]
    aliases = {
        "mp3": "audio/mpeg", "wav": "audio/wav", "flac": "audio/flac", "m4a": "audio/mp4",
        "zip": "application/zip", "rar": "application/vnd.rar", "pdf": "application/pdf",
    }
    return aliases.get(extension, upload.content_type or "application/octet-stream")


async def _delivery_file(upload):
    if upload is None or not upload.filename:
        return None
    data = await upload.read(MAX_FILE_SIZE + 1)
    await upload.close()
    return (upload.filename, _upload_mime(upload), data)


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
    etapa_id: Annotated[int | None, Form()] = None,
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
            stage_id=etapa_id,
        )
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None


@router.get("/producoes/{producao_id}/entregas-finais", response_model=list[ProducaoEntregaFinalResponse])
def listar_entregas_finais(producao_id: int, db: Db, user: CurrentProducer):
    if not crud_producao.buscar_por_produtor(db, producao_id, user.id):
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")
    return producao_entrega_service.list_for_production(db, producao_id)


@router.post(
    "/producoes/{producao_id}/entregas-finais",
    response_model=ProducaoEntregaFinalResponse,
    status_code=201,
)
async def criar_entrega_final(
    producao_id: int,
    request: Request,
    db: Db,
    user: CurrentProducer,
    request_id: Annotated[UUID, Form()],
    categoria: Annotated[Literal["instrumental", "outro"], Form()],
    titulo: Annotated[str, Form(max_length=150)],
    arquivo_principal: Annotated[UploadFile, File()],
    bpm: Annotated[int | None, Form(ge=20, le=300)] = None,
    tonalidade: Annotated[str | None, Form(max_length=20)] = None,
    creditos_adicionais: Annotated[str | None, Form(max_length=1200)] = None,
    etapa_id: Annotated[int | None, Form()] = None,
    wav: Annotated[UploadFile | None, File()] = None,
    multitrack: Annotated[UploadFile | None, File()] = None,
    licenca: Annotated[UploadFile | None, File()] = None,
    multitrack_url: Annotated[str | None, Form(max_length=2000)] = None,
    observacao: Annotated[str | None, Form(max_length=1000)] = None,
):
    production = crud_producao.buscar_por_produtor(db, producao_id, user.id)
    if not production:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")
    if production.produtor_id != user.id:
        raise HTTPException(status_code=403, detail="Somente o produtor coordenador pode enviar a entrega final.")
    try:
        model = producao_entrega_service.create(
            db, production=production, actor=user, request_id=request_id, category=categoria,
            title=titulo, main=await _delivery_file(arquivo_principal), wav=await _delivery_file(wav),
            archive=await _delivery_file(multitrack), license_file=await _delivery_file(licenca),
            multitrack_url=multitrack_url, note=observacao,
            bpm=bpm, tonalidade=tonalidade, creditos_adicionais=creditos_adicionais,
            stage_id=etapa_id,
            request_log_id=getattr(request.state, "request_id", None),
        )
        return producao_entrega_service.response(model)
    except producao_entrega_service.ProducaoEntregaError as exc:
        raise _delivery_error(exc) from None


@router.patch("/entregas-finais/{entrega_id}", response_model=ProducaoEntregaFinalResponse)
def editar_entrega_final(
    entrega_id: int,
    payload: ProducaoEntregaFinalUpdate,
    request: Request,
    db: Db,
    user: CurrentProducer,
):
    try:
        model = producao_entrega_service.get(db, entrega_id)
        production = crud_producao.buscar_por_produtor(db, model.producao_id, user.id)
        if not production:
            raise HTTPException(status_code=404, detail="Entrega final nao encontrada.")
        model = producao_entrega_service.update(
            db, model=model, production=production, actor=user,
            changes=payload.model_dump(exclude_unset=True),
            request_log_id=getattr(request.state, "request_id", None),
        )
        return producao_entrega_service.response(model)
    except producao_entrega_service.ProducaoEntregaError as exc:
        db.rollback()
        raise _delivery_error(exc) from None


@router.delete("/entregas-finais/{entrega_id}", status_code=204)
def excluir_entrega_final(entrega_id: int, request: Request, db: Db, user: CurrentProducer):
    try:
        try:
            model = producao_entrega_service.get(db, entrega_id)
        except producao_entrega_service.ProducaoEntregaError:
            raise HTTPException(status_code=404, detail="Entrega final nao encontrada.") from None
        production = crud_producao.buscar_por_produtor(db, model.producao_id, user.id)
        if not production:
            raise HTTPException(status_code=404, detail="Entrega final nao encontrada.")
        producao_entrega_service.delete(
            db, model=model, production=production, actor=user,
            request_log_id=getattr(request.state, "request_id", None),
        )
    except producao_entrega_service.ProducaoEntregaError as exc:
        db.rollback()
        raise _delivery_error(exc) from None
    return Response(status_code=204)


@router.get("/entregas-finais/{entrega_id}/multitrack")
def abrir_multitrack_entrega(entrega_id: int, db: Db, user: CurrentProducer):
    try:
        model = producao_entrega_service.get(db, entrega_id)
        if not crud_producao.buscar_por_produtor(db, model.producao_id, user.id):
            raise HTTPException(status_code=404, detail="Entrega final nao encontrada.")
        return {"url": producao_entrega_service.external_multitrack(model)}
    except producao_entrega_service.ProducaoEntregaError as exc:
        raise _delivery_error(exc) from None


@router.patch("/arquivos/{arquivo_id}/observacao", response_model=ProducaoArquivoResponse)
def editar_observacao(
    arquivo_id: int,
    payload: ProducaoArquivoObservacaoRequest,
    request: Request,
    db: Db,
    user: CurrentProducer,
):
    try:
        model = producao_arquivo_service.get_for_producer(db, arquivo_id, user.id)
        return producao_arquivo_service.update_note(
            db,
            model=model,
            actor=user,
            note=payload.observacao,
            request_id=getattr(request.state, "request_id", None),
        )
    except producao_arquivo_service.ProducaoArquivoError as exc:
        db.rollback()
        raise _file_error(exc) from None


@router.patch("/arquivos/{arquivo_id}", response_model=ProducaoArquivoResponse)
def editar_arquivo(
    arquivo_id: int,
    payload: ProducaoArquivoEdicaoRequest,
    request: Request,
    db: Db,
    user: CurrentProducer,
):
    try:
        model = producao_arquivo_service.get_for_producer(db, arquivo_id, user.id)
        return producao_arquivo_service.update_details(
            db,
            model=model,
            actor=user,
            changes=payload.model_dump(exclude_unset=True),
            request_id=getattr(request.state, "request_id", None),
        )
    except producao_arquivo_service.ProducaoArquivoError as exc:
        db.rollback()
        raise _file_error(exc) from None


@router.delete("/arquivos/{arquivo_id}", status_code=204)
def excluir_previa(
    arquivo_id: int,
    request: Request,
    db: Db,
    user: CurrentProducer,
):
    try:
        producao_arquivo_service.delete_preview_for_producer(
            db,
            file_id=arquivo_id,
            actor=user,
            request_id=getattr(request.state, "request_id", None),
        )
    except producao_arquivo_service.ProducaoArquivoError as exc:
        db.rollback()
        raise _file_error(exc) from None
    return Response(status_code=204)


@router.get("/arquivos/{arquivo_id}/conteudo")
def baixar_arquivo(
    arquivo_id: int,
    db: Db,
    user: CurrentProducer,
    versao: Literal["original", "processada"] | None = None,
    ouvir: bool = False,
):
    try:
        model = producao_arquivo_service.get_for_producer(db, arquivo_id, user.id)
        content = producao_arquivo_service.read(model, versao=versao)
    except producao_arquivo_service.ProducaoArquivoError as exc:
        raise _file_error(exc) from None
    processada = versao == "processada"
    name = (model.nome_exibicao.rsplit(".", 1)[0] + ".mp3") if processada else model.nome_exibicao
    filename = quote(name, safe="")
    disposition = "inline" if ouvir else "attachment"
    return Response(
        content,
        media_type="audio/mpeg" if processada else model.mime_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{filename}",
            "Cache-Control": "private, no-store",
        },
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


def _perfil(user):
    especialidades = [item for item in (user.especialidades or "").split(",") if item]
    return PerfilProdutorResponse(
        especialidades=especialidades,
        beatmaker="beatmaker" in especialidades,
        cpf_cadastrado=bool(user.cpf),
        cpf_mascarado=mascarar_cpf(user.cpf),
    )


@router.get("/perfil", response_model=PerfilProdutorResponse)
def meu_perfil(user: CurrentProducer):
    return _perfil(user)


@router.put("/perfil/cpf", response_model=PerfilProdutorResponse)
def salvar_cpf(payload: PerfilProdutorCpfUpdate, request: Request, db: Db, user: CurrentProducer):
    """The producer registers or corrects their own CPF (it appears only in private beat contracts)."""
    current = db.get(UsuarioModel, user.id)
    changed = current.cpf != payload.cpf
    if changed:
        replaced = bool(current.cpf)
        current.cpf = payload.cpf
        # The audit never stores the CPF itself.
        audit_service.record(
            db, actor=user, action="user.cpf_set_by_producer", entity_type="user", entity_id=user.id,
            metadata={"replaced": replaced}, request_id=getattr(request.state, "request_id", None),
        )
        db.commit()
        db.refresh(current)
    return _perfil(current)


# Public page (/produtores/<endereço>): the producer customises it here.
IMAGE_LIMIT = 8 * 1024 * 1024


@router.get("/perfil/pagina")
def minha_pagina(db: Db, user: CurrentProducer):
    from services import produtor_perfil_service

    return produtor_perfil_service.meu(db, user)


@router.put("/perfil/pagina")
def salvar_pagina(payload: PerfilPaginaUpdate, request: Request, db: Db, user: CurrentProducer):
    from services import produtor_perfil_service

    return produtor_perfil_service.atualizar(db, user, payload, getattr(request.state, "request_id", None))


@router.post("/perfil/pagina/imagem/{tipo}")
async def enviar_imagem_pagina(
    tipo: Literal["foto", "capa"], request: Request, db: Db, user: CurrentProducer,
    arquivo: Annotated[UploadFile, File()],
):
    from services import produtor_perfil_service

    data = await arquivo.read(IMAGE_LIMIT + 1)
    content_type = arquivo.content_type or "application/octet-stream"
    await arquivo.close()
    return produtor_perfil_service.salvar_imagem(db, user, tipo, data, content_type,
                                                 getattr(request.state, "request_id", None))


@router.delete("/perfil/pagina/imagem/{tipo}")
def remover_imagem_pagina(tipo: Literal["foto", "capa"], request: Request, db: Db, user: CurrentProducer):
    from services import produtor_perfil_service

    return produtor_perfil_service.remover_imagem(db, user, tipo, getattr(request.state, "request_id", None))
