"""Commercial transitions; transaction ownership stays here."""
import logging
from datetime import datetime, timezone
from io import BytesIO

from core.enums import OrcamentoStatus
from crud import crud_producao, crud_proposta
from fastapi import HTTPException
from models.enums.proposta import PropostaStatus as Status
from pydantic import EmailStr, TypeAdapter, ValidationError
from pypdf import PdfReader
from services import (
    audit_service,
    cota_arquivo_service,
    financial_service,
    politica_service,
    producao_etapa_service,
    producao_liberacao_service,
)
from services import proposta_documento_service as documentos
from services import proposta_service as service
from services import proposta_snapshot_service as snapshots
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
    budget_id = found.orcamento_id
    budget = crud_proposta.bloquear_orcamento(db, budget_id)
    proposta = crud_proposta.buscar_por_id(db, proposta_id, bloquear=True)
    if proposta is None or budget is None:
        raise service.PropostaNaoEncontrada("Proposta ou orcamento nao encontrado.")
    if proposta.orcamento_id != budget.id:
        raise service.PropostaConflito(
            "A vinculacao comercial mudou durante a operacao. Tente novamente."
        )
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
        # 5.05: freeze negotiated values and stage weights before anything leaves the system.
        snapshots.congelar(db, model, origem="envio", estrito=True)
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
        from services import portal_notificacao_service

        portal_notificacao_service.proposta_enviada(db, model)
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


def _aprovar_carregada(db, model, budget, actor, request_id, *, audit_action):
    pipeline_v2 = producao_liberacao_service.pipeline_v2_habilitada()
    if getattr(model, "finalidade", "producao") == "creditos" and not pipeline_v2:
        raise service.PropostaConflito("Compra de creditos indisponivel sem a pipeline comercial V2.")
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
        return service._resposta(model)
    if model.status != Status.ENVIADA.value or not model.enviada_em:
        raise service.PropostaConflito("Somente proposta enviada pode ser aprovada.")
    if budget.status != OrcamentoStatus.PROPOSTA_ENVIADA.value:
        raise service.PropostaConflito("Status do orcamento incompativel com a aprovacao.")
    if crud_producao.buscar_por_orcamento(db, model.orcamento_id):
        raise service.PropostaConflito(
            "Ja existe producao para este orcamento; requer conciliacao."
        )
    # Proposals sent before 5.05 get their snapshot at acceptance, without blocking it.
    snapshots.congelar(db, model, origem="aceite", estrito=False)
    if not pipeline_v2:
        producao = crud_producao.criar_sem_commit(
            db,
            _dados_producao(service._resposta(model)),
        )
        producao_etapa_service.instanciar(db, producao, model)
        cota_arquivo_service.instanciar(db, producao, model)  # 5.09
        politica_service.instanciar(db, producao, model)  # 5.10
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
    from services import beat_service
    try:
        beat_service.reserve_for_proposal(db, model, budget.cliente_id)
    except HTTPException as error:
        raise service.PropostaConflito(str(error.detail)) from None
    model.status = Status.ACEITA.value
    model.aprovada_em = datetime.now(timezone.utc)
    budget.status = OrcamentoStatus.APROVADO.value
    db.flush()
    if getattr(model, "finalidade", "producao") == "creditos":
        charge = financial_service.buscar_por_proposta(db, model.id)
        try:
            producao_liberacao_service.avaliar_liberacao_producao(db, charge.id, actor=actor, request_id=request_id)
        except (financial_service.FinanceiroConflito, financial_service.FinanceiroInvalido) as error:
            raise service.PropostaConflito(str(error)) from None
    audit_service.record(
        db,
        actor=actor,
        action=audit_action,
        entity_type="proposal",
        entity_id=model.id,
        metadata={"old_status": Status.ENVIADA.value, "new_status": model.status},
        request_id=request_id,
    )
    return service._resposta(model)


def aprovar(db, proposta_id, actor=None, request_id=None):
    try:
        model, budget = _carregar(db, proposta_id)
        response = _aprovar_carregada(
            db,
            model,
            budget,
            actor,
            request_id,
            audit_action="proposal.approved",
        )
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


def _validar_cliente(model, budget, *, cliente_id, versao):
    if budget.cliente_id != cliente_id:
        raise service.PropostaNaoEncontrada("Proposta nao encontrada.")
    if model.versao != versao:
        raise service.PropostaConflito(
            "A proposta foi atualizada. Revise a versao atual antes de continuar."
        )


def aceitar_cliente(db, proposta_id, *, cliente_id, versao, actor, request_id=None):
    if not producao_liberacao_service.pipeline_v2_habilitada():
        raise service.PropostaNaoEncontrada("Proposta nao encontrada.")
    try:
        model, budget = _carregar(db, proposta_id)
        _validar_cliente(model, budget, cliente_id=cliente_id, versao=versao)
        response = _aprovar_carregada(
            db,
            model,
            budget,
            actor,
            request_id,
            audit_action="proposal.accepted_by_client",
        )
        db.commit()
        logger.info("proposal_accepted_by_client")
        return response
    except IntegrityError:
        db.rollback()
        raise service.PropostaConflito(
            "Aceite concorrente; consulte o estado atual antes de repetir."
        ) from None
    except Exception:
        db.rollback()
        raise


def aceitar_compra_catalogo(db, proposta_id, *, cliente_id, actor, request_id=None):
    """Accept a single-beat catalog order without sending it through manual review."""
    if not producao_liberacao_service.pipeline_v2_habilitada():
        raise service.PropostaNaoEncontrada("Compra de beat indisponivel.")
    try:
        model, budget = _carregar(db, proposta_id)
        if budget.cliente_id != cliente_id:
            raise service.PropostaNaoEncontrada("Compra de beat nao encontrada.")
        items = model.itens_json or []
        if (
            len(items) != 1
            or not items[0].get("beat_id")
            or not items[0].get("licenca_beat")
            or model.politica_pagamento != "integral"
        ):
            raise service.PropostaConflito("Compra de beat invalida para checkout direto.")
        if model.status in (Status.RASCUNHO.value, Status.PRONTA.value):
            if budget.status not in (OrcamentoStatus.NOVO.value, OrcamentoStatus.EM_ANALISE.value):
                raise service.PropostaConflito("Status da compra incompativel com o checkout.")
            snapshots.congelar(db, model, origem="aceite", estrito=True)
            model.enviada_em = datetime.now(timezone.utc)
            model.status = Status.ENVIADA.value
            budget.status = OrcamentoStatus.PROPOSTA_ENVIADA.value
            db.flush()
        response = _aprovar_carregada(
            db,
            model,
            budget,
            actor,
            request_id,
            audit_action="beat.checkout_created",
        )
        db.commit()
        return response
    except IntegrityError:
        db.rollback()
        raise service.PropostaConflito(
            "Compra concorrente; consulte o checkout antes de repetir."
        ) from None
    except Exception:
        db.rollback()
        raise


def recusar_cliente(db, proposta_id, *, cliente_id, versao, actor, request_id=None):
    if not producao_liberacao_service.pipeline_v2_habilitada():
        raise service.PropostaNaoEncontrada("Proposta nao encontrada.")
    try:
        model, budget = _carregar(db, proposta_id)
        _validar_cliente(model, budget, cliente_id=cliente_id, versao=versao)
        if model.status == Status.RECUSADA.value:
            response = service._resposta(model)
            db.commit()
            return response
        if model.status != Status.ENVIADA.value or not model.enviada_em:
            raise service.PropostaConflito("Somente proposta enviada pode ser recusada.")
        if budget.status != OrcamentoStatus.PROPOSTA_ENVIADA.value:
            raise service.PropostaConflito("Status do orcamento incompativel com a recusa.")
        if (
            financial_service.buscar_por_proposta(db, model.id) is not None
            or crud_producao.buscar_por_orcamento(db, model.orcamento_id) is not None
        ):
            raise service.PropostaConflito(
                "Esta proposta possui operacoes comerciais e requer conciliacao."
            )
        model.status = Status.RECUSADA.value
        budget.status = OrcamentoStatus.RECUSADO.value
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action="proposal.refused_by_client",
            entity_type="proposal",
            entity_id=model.id,
            metadata={"old_status": Status.ENVIADA.value, "new_status": model.status},
            request_id=request_id,
        )
        response = service._resposta(model)
        db.commit()
        logger.info("proposal_refused_by_client")
        return response
    except Exception:
        db.rollback()
        raise
