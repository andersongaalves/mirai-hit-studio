"""Commercial transitions; transaction ownership stays here."""
from datetime import datetime, timezone
from io import BytesIO
import logging

from pydantic import TypeAdapter, EmailStr, ValidationError
from pypdf import PdfReader
from sqlalchemy.exc import IntegrityError

from crud import crud_proposta, crud_producao
from models.enums.proposta import PropostaStatus as Status
from core.enums import OrcamentoStatus
from services import proposta_service as service, proposta_documento_service as documentos
from services.documento_storage import LocalDocumentoStorage
from services.email_service import EmailService
from services.pdf_service import moeda

logger = logging.getLogger(__name__)


class EnvioIndisponivel(Exception):
    pass


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
            data = LocalDocumentoStorage().ler(model.pdf_path)
            reader = PdfReader(BytesIO(data), strict=True)
            if data.startswith(b"%PDF-") and not reader.is_encrypted and len(reader.pages):
                return data
        except Exception:
            pass  # Missing/corrupt document must be regenerated before sending.
    return documentos.gerar_sem_commit(db, model)


def enviar(db, proposta_id):
    aceito_pelo_provedor = False
    try:
        model, budget = _carregar(db, proposta_id)
        if model.status == Status.ENVIADA.value:
            response = service._resposta(model)
            db.commit()
            return response
        if model.status not in (Status.RASCUNHO.value, Status.PRONTA.value):
            raise service.PropostaConflito("Esta proposta nao permite envio.")
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


def _dados_producao(proposta):
    cliente = proposta.cliente_snapshot.cliente.nome
    servico = proposta.cliente_snapshot.orcamento.servico
    titulo = proposta.objeto or f"Proposta {proposta.numero}"
    if len(cliente) > 120 or len(servico) > 100:
        raise service.PropostaInvalida("Nome/servico do snapshot excede o limite da producao.")
    totals = service.calcular_totais(proposta.itens)
    itens = "\n".join(f"- {i.descricao}: {i.quantidade} x {moeda(i.valor_unitario)}; desconto {moeda(i.desconto)}"
                      for i in proposta.itens)
    notes = f"Proposta {proposta.numero} | versao {proposta.versao}\n{proposta.objeto}\n{proposta.descricao}\n{itens}\nTotal: {moeda(totals.total)}\n{proposta.condicoes}"
    return {"titulo": titulo[:150], "cliente": cliente, "servico": servico,
            "produtor_id": proposta.produtor_id, "orcamento_id": proposta.orcamento_id,
            "observacoes": notes, "status": "aguardando_inicio", "etapas": "[]"}


def aprovar(db, proposta_id):
    try:
        model, budget = _carregar(db, proposta_id)
        if model.status == Status.ACEITA.value:
            if not crud_producao.buscar_por_orcamento(db, model.orcamento_id):
                raise service.PropostaConflito("Proposta aceita sem producao; requer conciliacao.")
            response = service._resposta(model)
            db.commit()
            return response
        if model.status != Status.ENVIADA.value or not model.enviada_em:
            raise service.PropostaConflito("Somente proposta enviada pode ser aprovada.")
        if budget.status != OrcamentoStatus.PROPOSTA_ENVIADA.value:
            raise service.PropostaConflito("Status do orcamento incompativel com a aprovacao.")
        if crud_producao.buscar_por_orcamento(db, model.orcamento_id):
            raise service.PropostaConflito("Ja existe producao para este orcamento; requer conciliacao.")
        crud_producao.criar_sem_commit(db, _dados_producao(service._resposta(model)))
        model.status = Status.ACEITA.value
        model.aprovada_em = datetime.now(timezone.utc)
        budget.status = OrcamentoStatus.APROVADO.value
        db.flush()
        response = service._resposta(model)
        db.commit()
        logger.info("proposal_approved")
        logger.info("production_created")
        return response
    except IntegrityError:
        db.rollback()
        # UNIQUE(orcamento_id) also protects writers outside this service.
        raise service.PropostaConflito("Producao ja vinculada; consulte o estado atual antes de repetir.") from None
    except Exception:
        db.rollback()
        raise
