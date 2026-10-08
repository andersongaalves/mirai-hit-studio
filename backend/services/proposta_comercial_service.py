"""Commercial transitions; transaction ownership stays here."""
import logging
from datetime import datetime, timezone
from io import BytesIO

from core.enums import OrcamentoStatus
from crud import crud_producao, crud_proposta
from models.enums.proposta import PropostaStatus as Status
from pydantic import EmailStr, TypeAdapter, ValidationError
from pypdf import PdfReader
from services import audit_service, financial_service, producao_liberacao_service
from services import proposta_documento_service as documentos
from services import proposta_service as service
from services.documento_storage import DocumentoIndisponivel
from services.email_service import EmailService
from services.pdf_service import moeda
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class EnvioIndisponivel(Exception):
    pass


def _dados_producao(proposta):
    """Compatibility helper for historical callers and fixtures."""
    return producao_liberacao_service.dados_producao(proposta)


def _pdf_valido(data):
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        return bool(data.startswith(b"%PDF-") and not reader.is_encrypted and len(reader.pages))
    except Exception:
        return False


def _carregar(db, proposta_id):
    # Budget first matches creation's lock order. Then refresh/lock the proposal.
    found = crud_proposta.buscar_por_id(db, proposta_id)
    if found is None:
        raise service.PropostaNaoEncontrada("Proposta nao encontrada.")
    budget = crud_proposta.bloquear_orcamento(db, found.orcamento_id)
    proposta = crud_proposta.buscar_por_id(db, proposta_id, bloquear=True)
    if proposta is None or budget is None:
        raise service.PropostaNaoEncontrada("Proposta ou orcamento nao encontrado.")
    return proposta, budget


def _pdf_atual(db, model):
    if model.pdf_path and model.gerada_em and model.pdf_path.startswith(f"proposta-{model.id}-v{model.versao}-"):
        try:
            data = documentos.ler_atual(model)
        except (DocumentoIndisponivel, service.PropostaConflito):
            valido = False
        else:
            valido = _pdf_valido(data)
        if valido:
            if model.pdf_sha256:
                return data
            return documentos.persistir_bytes_sem_commit(db, model, data)
    elif model.pdf_path and model.gerada_em and model.pdf_sha256:
        try:
            data = documentos.ler_atual(model)
        except DocumentoIndisponivel:
            raise EnvioIndisponivel("PDF persistido indisponivel; o envio foi interrompido.") from None
        if _pdf_valido(data):
            return data
        raise EnvioIndisponivel("PDF persistido invalido; o envio foi interrompido.")
    return documentos.gerar_sem_commit(db, model)


def enviar(db, proposta_id, actor=None, request_id=None):
    aceito_pelo_provedor = False
    try:
        model, budget = _carregar(db, proposta_id)
        if model.status == Status.ENVIADA.value:
            response = service._resposta(model)
            db.commit()
            return response
        if model.status not in (Status.RASCUNHO.value, Status.PRONTA.value):
            raise service.PropostaConflito("Esta proposta nao permite envio.")
        old_status = model.status
        if budget.status not in (OrcamentoStatus.NOVO.value, OrcamentoStatus.EM_ANALISE.value):
            raise service.PropostaConflito("Status do orcamento incompativel com o envio.")
        response = service._resposta(model)
        try:
            TypeAdapter(EmailStr).validate_python(response.cliente_snapshot.cliente.email)
        except ValidationError:
            raise service.PropostaInvalida("Email do snapshot invalido.") from None
        data = _pdf_atual(db, model)
        try:
            result = EmailService.enviar_proposta(response, data, moeda(service.calcular_totais(response.itens).total))
            if not isinstance(result, dict) or not isinstance(result.get("id"), str) or not result["id"].strip():
                raise ValueError()
            aceito_pelo_provedor = True
        except Exception:
            raise EnvioIndisponivel("Nao foi possivel confirmar o envio. Confira o provedor antes de tentar novamente.") from None
        model.enviada_em = datetime.now(timezone.utc)
        model.status = Status.ENVIADA.value
        budget.status = OrcamentoStatus.PROPOSTA_ENVIADA.value
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action="proposal.sent",
            entity_type="proposal",
            entity_id=model.id,
            metadata={"old_status": old_status, "new_status": model.status},
            request_id=request_id,
        )
        response = service._resposta(model)
        db.commit()
        logger.info("proposal_sent")
        return response
    except Exception:
        db.rollback()
        logger.error("proposal_send_failed")
        if aceito_pelo_provedor:
            raise EnvioIndisponivel("Email aceito pelo provedor, mas registro local nao confirmado. Concilie antes de repetir.") from None
        raise


def aprovar(db, proposta_id, actor=None, request_id=None):
    try:
        model, budget = _carregar(db, proposta_id)
        pipeline_v2 = producao_liberacao_service.pipeline_v2_habilitada()
        if model.status == Status.ACEITA.value:
            if not crud_producao.buscar_por_orcamento(db, model.orcamento_id):
                if not pipeline_v2:
                    raise service.PropostaConflito(
                        "Proposta aceita sem producao; requer conciliacao."
                    )
                try:
                    financial_service.criar_para_proposta(
                        db,
                        model,
                        cliente_id=budget.cliente_id,
                    )
                except financial_service.FinanceiroInvalido as error:
                    raise service.PropostaInvalida(str(error)) from None
                except financial_service.FinanceiroConflito as error:
                    raise service.PropostaConflito(str(error)) from None
            response = service._resposta(model)
            db.commit()
            return response
        if model.status != Status.ENVIADA.value or not model.enviada_em:
            raise service.PropostaConflito("Somente proposta enviada pode ser aprovada.")
        if budget.status != OrcamentoStatus.PROPOSTA_ENVIADA.value:
            raise service.PropostaConflito("Status do orcamento incompativel com a aprovacao.")
        if crud_producao.buscar_por_orcamento(db, model.orcamento_id):
            raise service.PropostaConflito("Ja existe producao para este orcamento; requer conciliacao.")
        if not pipeline_v2:
            crud_producao.criar_sem_commit(
                db,
                _dados_producao(service._resposta(model)),
            )
        try:
            financial_service.criar_para_proposta(
                db,
                model,
                cliente_id=budget.cliente_id,
            )
        except financial_service.FinanceiroInvalido as error:
            raise service.PropostaInvalida(str(error)) from None
        except financial_service.FinanceiroConflito as error:
            raise service.PropostaConflito(str(error)) from None
        model.status = Status.ACEITA.value
        model.aprovada_em = datetime.now(timezone.utc)
        budget.status = OrcamentoStatus.APROVADO.value
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action="proposal.approved",
            entity_type="proposal",
            entity_id=model.id,
            metadata={"old_status": Status.ENVIADA.value, "new_status": model.status},
            request_id=request_id,
        )
        response = service._resposta(model)
        db.commit()
        logger.info("proposal_approved")
        return response
    except IntegrityError:
        db.rollback()
        raise service.PropostaConflito(
            "Aceite concorrente; consulte o estado atual antes de repetir."
        ) from None
    except Exception:
        db.rollback()
        raise
