"""Commercial classification only; financial history and providers are untouched."""

from models.cliente import ClienteModel
from models.financeiro import CobrancaModel, PagamentoModel
from models.orcamento import OrcamentoModel
from models.producao import ProducaoModel
from models.proposta import PropostaModel
from models.usuario import UsuarioModel
from services import audit_service, proposta_service
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session


def cliente_oficial():
    real = ClienteModel.orcamentos.any(OrcamentoModel.is_test.is_(False))
    return or_(real, ClienteModel.is_test.is_(False) & ~ClienteModel.orcamentos.any())


def cadeia_protegida(db: Session, budget, proposal=None, charge=None):
    if budget.id == 238 or budget.cliente_id == 94:
        return True
    if proposal is not None and proposal.id == 73:
        return True
    if charge is not None and (charge.id == 74 or charge.cliente_id == 94):
        return True
    customer_ids = {budget.cliente_id}
    if charge is not None:
        customer_ids.add(charge.cliente_id)
        if db.scalar(
            select(PagamentoModel.id).where(
                PagamentoModel.id == 85,
                PagamentoModel.cobranca_id == charge.id,
            )
        ):
            return True
    if db.scalar(
        select(ProducaoModel.id).where(
            ProducaoModel.id == 48,
            ProducaoModel.orcamento_id == budget.id,
        )
    ):
        return True
    return bool(
        db.scalar(
            select(UsuarioModel.id).where(
                UsuarioModel.cliente_id.in_([i for i in customer_ids if i is not None]),
                or_(
                    UsuarioModel.id == 48,
                    func.lower(func.trim(UsuarioModel.username)) == "yonda",
                ),
            )
        )
    )


def _context(db, proposal_id, *, lock=False):
    proposal = db.get(PropostaModel, proposal_id)
    if proposal is None:
        raise proposta_service.PropostaNaoEncontrada("Proposta nao encontrada.")
    budget_id = proposal.orcamento_id
    charge_query = select(CobrancaModel).where(CobrancaModel.proposta_id == proposal_id)
    # Provider writers hold the charge before the budget. Use the same order.
    if lock:
        charge_query = charge_query.with_for_update().execution_options(
            populate_existing=True
        )
    charge = db.scalar(charge_query)
    budget_query = select(OrcamentoModel).where(OrcamentoModel.id == budget_id)
    proposal_query = select(PropostaModel).where(PropostaModel.id == proposal_id)
    if lock:
        budget_query = budget_query.with_for_update().execution_options(
            populate_existing=True
        )
        proposal_query = proposal_query.with_for_update().execution_options(
            populate_existing=True
        )
    budget = db.scalar(budget_query)
    proposal = db.scalar(proposal_query)
    if budget is None or proposal is None or proposal.orcamento_id != budget.id:
        raise proposta_service.PropostaConflito("Vinculo comercial invalido.")
    current_charge = db.scalar(
        select(CobrancaModel).where(CobrancaModel.proposta_id == proposal.id)
    )
    if current_charge is not None and (
        charge is None or current_charge.id != charge.id
    ):
        # An acceptance created a charge while we waited. Retry with the correct lock order.
        raise proposta_service.PropostaConflito(
            "Cadeia alterada; consulte e tente novamente."
        )
    if charge is not None and charge.proposta_id != proposal.id:
        raise proposta_service.PropostaConflito("Vinculo financeiro invalido.")
    return budget, proposal, charge


def _response(db, budget, proposal, charge):
    history = bool(
        charge is not None
        and db.scalar(
            select(PagamentoModel.id)
            .where(
                PagamentoModel.cobranca_id == charge.id,
            )
            .limit(1)
        )
    )
    protected = cadeia_protegida(db, budget, proposal, charge)
    return {
        "id": proposal.id,
        "orcamento_id": budget.id,
        "is_test": budget.is_test,
        "protegida": protected,
        "historico_financeiro": history,
        "reversao_permitida": not protected and not history,
    }


def consultar(db, proposal_id):
    return _response(db, *_context(db, proposal_id))


def alterar(db, proposal_id, data, actor, request_id=None):
    try:
        budget, proposal, charge = _context(db, proposal_id, lock=True)
        response = _response(db, budget, proposal, charge)
        if response["protegida"]:
            raise proposta_service.PropostaConflito(
                "Cadeia protegida; classificacao indisponivel."
            )
        if budget.is_test == data.is_test:
            db.rollback()
            return response
        if response["historico_financeiro"] and not data.confirmar_historico_financeiro:
            raise proposta_service.PropostaConflito(
                "Confirme a preservacao do historico financeiro."
            )
        if not data.is_test and not response["reversao_permitida"]:
            raise proposta_service.PropostaConflito(
                "Historico financeiro exige conciliacao antes de tornar a operacao real."
            )
        old = budget.is_test
        budget.is_test = data.is_test
        audit_service.record(
            db,
            actor=actor,
            action="proposal.classification_changed",
            entity_type="proposal",
            entity_id=proposal.id,
            metadata={
                "orcamento_id": budget.id,
                "old_is_test": old,
                "new_is_test": data.is_test,
                "financial_history_confirmed": data.confirmar_historico_financeiro,
            },
            request_id=request_id,
        )
        db.flush()
        response = _response(db, budget, proposal, charge)
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def permitir_nova_order(db, charge):
    budget = db.scalar(
        select(OrcamentoModel)
        .join(PropostaModel)
        .where(
            PropostaModel.id == charge.proposta_id,
        )
        .execution_options(populate_existing=True)
    )
    if budget is None or budget.is_test:
        from services.financial_service import FinanceiroConflito

        raise FinanceiroConflito(
            "Operacao de teste nao permite criar pagamentos externos."
        )


def classificar_conta(db, user_id, data, actor, request_id=None):
    try:
        user = db.scalar(
            select(UsuarioModel)
            .where(UsuarioModel.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise proposta_service.PropostaNaoEncontrada("Conta nao encontrada.")
        customer = (
            db.scalar(
                select(ClienteModel)
                .where(ClienteModel.id == user.cliente_id)
                .with_for_update()
            )
            if user.cliente_id
            else None
        )
        protected = (
            user.role == "admin"
            or user.is_admin
            or user.id == 48
            or user.username.strip().lower() == "yonda"
            or user.cliente_id == 94
        )
        if customer is not None:
            for budget in db.scalars(
                select(OrcamentoModel).where(OrcamentoModel.cliente_id == customer.id)
            ):
                proposal = db.scalar(
                    select(PropostaModel).where(PropostaModel.orcamento_id == budget.id)
                )
                charge = (
                    db.scalar(
                        select(CobrancaModel).where(
                            CobrancaModel.proposta_id == proposal.id
                        )
                    )
                    if proposal
                    else None
                )
                protected |= cadeia_protegida(db, budget, proposal, charge)
        if protected or user.role not in {"cliente", "produtor"}:
            raise proposta_service.PropostaConflito(
                "Conta protegida; classificacao indisponivel."
            )
        if user.is_test == data.is_test and (
            customer is None or customer.is_test == data.is_test
        ):
            db.rollback()
            return user
        if not data.is_test:
            budgets = select(OrcamentoModel.id).where(
                OrcamentoModel.cliente_id == user.cliente_id
                if customer
                else OrcamentoModel.produtor_id == user.id,
            )
            if db.scalar(
                select(PagamentoModel.id)
                .join(CobrancaModel)
                .join(PropostaModel)
                .where(PropostaModel.orcamento_id.in_(budgets))
                .limit(1)
            ):
                raise proposta_service.PropostaConflito(
                    "Historico financeiro exige conciliacao antes da reversao da conta."
                )
        old = user.is_test
        user.is_test = data.is_test
        old_customer = customer.is_test if customer else None
        if customer:
            customer.is_test = data.is_test
        audit_service.record(
            db,
            actor=actor,
            action="user.classification_changed",
            entity_type="user",
            entity_id=user.id,
            metadata={
                "old_is_test": old,
                "new_is_test": data.is_test,
                "client_id": user.cliente_id,
                "old_client_is_test": old_customer,
            },
            request_id=request_id,
        )
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise
