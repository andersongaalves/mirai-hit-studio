from typing import Annotated
from urllib.parse import quote

from core.dependencies import require_client
from database import get_db
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from integrations.mercado_pago import (
    MercadoPagoClient,
    MercadoPagoError,
    MercadoPagoNotConfigured,
)
from models.usuario import UsuarioModel
from schemas.checkout import (
    CheckoutCardRequest,
    CheckoutPaymentRequest,
    CheckoutPaymentResponse,
    CheckoutStatus,
    CheckoutSummary,
)
from schemas.portal_cliente import (
    FinanceiroClienteResponse,
    ProducaoArquivoClienteResponse,
    ProducaoClienteResponse,
    PropostaClienteAction,
    PropostaClienteResponse,
)
from services import (
    checkout_service,
    financial_service,
    portal_cliente_proposta_service,
    portal_cliente_service,
    producao_arquivo_service,
)
from services.producao_arquivo_storage import MAX_FILE_SIZE
from sqlalchemy.orm import Session

router = APIRouter(prefix="/portal/cliente", tags=["Portal do Cliente"])
Db = Annotated[Session, Depends(get_db)]
CurrentClient = Annotated[UsuarioModel, Depends(require_client)]
FINAL_STATUSES = {"finalizado", "entregue"}
_CHECKOUT_EXCEPTIONS = (
    checkout_service.CheckoutNaoEncontrado,
    checkout_service.CheckoutIndisponivel,
    checkout_service.CheckoutConflito,
    financial_service.FinanceiroInvalido,
    financial_service.FinanceiroConflito,
    MercadoPagoError,
)


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


def _proposal_error(exc):
    if isinstance(exc, portal_cliente_proposta_service.PropostaClienteNotFound):
        return HTTPException(status_code=404, detail="Proposta nao encontrada.")
    if isinstance(exc, portal_cliente_proposta_service.PropostaClienteConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, portal_cliente_proposta_service.PropostaClienteUnavailable):
        return HTTPException(status_code=503, detail="Documento indisponivel.")
    return HTTPException(status_code=422, detail="Nao foi possivel processar a proposta.")


def get_mercado_pago_client():
    return MercadoPagoClient()


def _checkout_error(exc):
    if isinstance(exc, checkout_service.CheckoutNaoEncontrado):
        return HTTPException(status_code=404, detail="Checkout nao encontrado.")
    if isinstance(exc, checkout_service.CheckoutIndisponivel):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, checkout_service.CheckoutConflito):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, financial_service.FinanceiroInvalido):
        return HTTPException(status_code=422, detail="Dados financeiros invalidos.")
    if isinstance(exc, financial_service.FinanceiroConflito):
        return HTTPException(status_code=409, detail="Situacao financeira requer conciliacao.")
    if isinstance(exc, MercadoPagoNotConfigured):
        return HTTPException(status_code=503, detail="Pagamento temporariamente indisponivel.")
    if isinstance(exc, MercadoPagoError):
        status = 429 if exc.http_status == 429 else 503
        return HTTPException(status_code=status, detail="Provider de pagamento temporariamente indisponivel.")
    return HTTPException(status_code=503, detail="Checkout temporariamente indisponivel.")


@router.get(
    "/propostas/{proposta_id}/checkout",
    response_model=CheckoutSummary,
)
def resumo_checkout_proposta(proposta_id: int, db: Db, user: CurrentClient):
    try:
        return checkout_service.resumo_proposta(db, proposta_id, user.cliente_id)
    except _CHECKOUT_EXCEPTIONS as exc:
        raise _checkout_error(exc) from None


@router.get(
    "/propostas/{proposta_id}/checkout/status",
    response_model=CheckoutStatus,
)
def status_checkout_proposta(proposta_id: int, db: Db, user: CurrentClient):
    try:
        return checkout_service.status_proposta(db, proposta_id, user.cliente_id)
    except _CHECKOUT_EXCEPTIONS as exc:
        raise _checkout_error(exc) from None


@router.get(
    "/propostas/{proposta_id}/checkout/pending-payment",
    response_model=CheckoutPaymentResponse,
)
def recuperar_checkout_proposta(
    proposta_id: int,
    request: Request,
    db: Db,
    user: CurrentClient,
    client: MercadoPagoClient = Depends(get_mercado_pago_client),
):
    try:
        return checkout_service.recuperar_proposta(
            db,
            proposta_id,
            user.cliente_id,
            client=client,
            request_id=getattr(request.state, "request_id", None),
        )
    except _CHECKOUT_EXCEPTIONS as exc:
        raise _checkout_error(exc) from None


@router.post(
    "/propostas/{proposta_id}/checkout/pix",
    response_model=CheckoutPaymentResponse,
)
def pagar_checkout_pix(
    proposta_id: int,
    data: CheckoutPaymentRequest,
    request: Request,
    db: Db,
    user: CurrentClient,
    client: MercadoPagoClient = Depends(get_mercado_pago_client),
):
    try:
        return checkout_service.criar_pix_proposta(
            db,
            proposta_id,
            user.cliente_id,
            data.payment_option,
            client=client,
            request_id=getattr(request.state, "request_id", None),
        )
    except _CHECKOUT_EXCEPTIONS as exc:
        raise _checkout_error(exc) from None


@router.post(
    "/propostas/{proposta_id}/checkout/card",
    response_model=CheckoutPaymentResponse,
)
def pagar_checkout_cartao(
    proposta_id: int,
    data: CheckoutCardRequest,
    request: Request,
    db: Db,
    user: CurrentClient,
    client: MercadoPagoClient = Depends(get_mercado_pago_client),
):
    try:
        return checkout_service.criar_cartao_proposta(
            db,
            proposta_id,
            user.cliente_id,
            data,
            client=client,
            request_id=getattr(request.state, "request_id", None),
        )
    except _CHECKOUT_EXCEPTIONS as exc:
        raise _checkout_error(exc) from None


@router.get("/propostas", response_model=list[PropostaClienteResponse])
def listar_minhas_propostas(db: Db, user: CurrentClient):
    try:
        return portal_cliente_proposta_service.list_for_client(db, user.cliente_id)
    except portal_cliente_proposta_service.PropostaClienteError as exc:
        raise _proposal_error(exc) from None


@router.get("/propostas/{proposta_id}", response_model=PropostaClienteResponse)
def obter_minha_proposta(proposta_id: int, db: Db, user: CurrentClient):
    try:
        return portal_cliente_proposta_service.get_for_client(
            db, proposta_id, user.cliente_id
        )
    except portal_cliente_proposta_service.PropostaClienteError as exc:
        raise _proposal_error(exc) from None


@router.get("/propostas/{proposta_id}/documento")
def baixar_documento_proposta(proposta_id: int, db: Db, user: CurrentClient):
    try:
        content, filename = portal_cliente_proposta_service.document_for_client(
            db, proposta_id, user.cliente_id
        )
    except portal_cliente_proposta_service.PropostaClienteError as exc:
        raise _proposal_error(exc) from None
    encoded = quote(filename, safe="")
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/propostas/{proposta_id}/aceitar", response_model=PropostaClienteResponse)
def aceitar_minha_proposta(
    proposta_id: int,
    data: PropostaClienteAction,
    request: Request,
    db: Db,
    user: CurrentClient,
):
    try:
        return portal_cliente_proposta_service.accept(
            db,
            proposta_id,
            user.cliente_id,
            data.versao,
            user,
            getattr(request.state, "request_id", None),
        )
    except portal_cliente_proposta_service.PropostaClienteError as exc:
        raise _proposal_error(exc) from None


@router.post("/propostas/{proposta_id}/recusar", response_model=PropostaClienteResponse)
def recusar_minha_proposta(
    proposta_id: int,
    data: PropostaClienteAction,
    request: Request,
    db: Db,
    user: CurrentClient,
):
    try:
        return portal_cliente_proposta_service.refuse(
            db,
            proposta_id,
            user.cliente_id,
            data.versao,
            user,
            getattr(request.state, "request_id", None),
        )
    except portal_cliente_proposta_service.PropostaClienteError as exc:
        raise _proposal_error(exc) from None


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
