from typing import Annotated
from urllib.parse import quote

from core.dependencies import require_admin, require_producer
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from models import ProducaoArquivoModel, RepasseEtapaModel, RepasseEtapaPagamentoModel
from schemas.repasse_etapa import RepasseEtapaPagamento, RepasseEtapaResponse
from services import (
    credito_alocacao_service,
    financial_service,
    producao_arquivo_service,
    repasse_etapa_service,
    repasse_produtor_service,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(tags=["Repasses por etapa"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[object, Depends(require_admin)]
Producer = Annotated[object, Depends(require_producer)]


def _executar(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except (repasse_etapa_service.RepasseEtapaConflito, repasse_produtor_service.RepasseError,
            credito_alocacao_service.AlocacaoConflito, financial_service.FinanceiroConflito,
            financial_service.FinanceiroInvalido) as error:
        raise HTTPException(409, str(error)) from None


@router.get("/producoes/{producao_id}/repasses-etapas", response_model=list[RepasseEtapaResponse])
def listar(producao_id: int, response: Response, db: Db, user: Admin):
    response.headers["Cache-Control"] = "private, no-store"
    return _executar(repasse_etapa_service.listar, db, producao_id)


@router.post("/producoes/{producao_id}/repasses-etapas", response_model=list[RepasseEtapaResponse])
def emitir(producao_id: int, request: Request, db: Db, user: Admin):
    return _executar(repasse_etapa_service.emitir, db, producao_id, actor=user,
        request_id=getattr(request.state, "request_id", None))


@router.post("/producoes/{producao_id}/repasses-etapas/{repasse_id}/pagamento", response_model=list[RepasseEtapaResponse])
def pagar(producao_id: int, repasse_id: int, dados: RepasseEtapaPagamento, request: Request, db: Db, user: Admin):
    return _executar(repasse_etapa_service.pagar, db, producao_id, repasse_id, dados, actor=user,
        request_id=getattr(request.state, "request_id", None))


@router.get("/portal/produtor/repasses-etapas", response_model=list[RepasseEtapaResponse])
def listar_produtor(response: Response, db: Db, user: Producer):
    response.headers["Cache-Control"] = "private, no-store"
    return _executar(repasse_etapa_service.listar_produtor, db, user.id)


@router.get("/portal/produtor/repasses-etapas/{repasse_id}/comprovante")
def comprovante(repasse_id: int, db: Db, user: Producer):
    row = db.execute(select(RepasseEtapaModel, RepasseEtapaPagamentoModel).join(
        RepasseEtapaPagamentoModel, RepasseEtapaPagamentoModel.repasse_id == RepasseEtapaModel.id).where(
        RepasseEtapaModel.id == repasse_id, RepasseEtapaModel.produtor_id == user.id)).first()
    if row is None or row[1].comprovante_arquivo_id is None:
        raise HTTPException(404, "Comprovante nao encontrado.")
    payout, payment = row
    file = db.get(ProducaoArquivoModel, payment.comprovante_arquivo_id)
    if file is None or file.producao_id != payout.producao_id or file.tipo != "comprovante":
        raise HTTPException(404, "Comprovante nao encontrado.")
    try:
        contents = producao_arquivo_service.read(file)
    except producao_arquivo_service.ProducaoArquivoError:
        raise HTTPException(503, "Comprovante temporariamente indisponivel.") from None
    return Response(contents, media_type=file.mime_type, headers={"Cache-Control": "private, no-store",
        "Content-Disposition": "attachment; filename*=UTF-8''" + quote(file.nome_exibicao, safe="")})
