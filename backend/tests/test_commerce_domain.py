"""Focused payment-policy and production-release domain tests."""

import unittest

import test_bootstrap_database as isolated
from test_financeiro import FINANCE_SETUP

DOMAIN_SETUP = FINANCE_SETUP + r'''
from integrations.mercado_pago import ProviderPaymentResult
from models.enums.financeiro import PagamentoStatus
from services import mercado_pago_service as mp_service

def accepted(db, budget_id, policy='entrada_50_50'):
    proposal = service.criar_por_orcamento(db, budget_id)
    model = db.get(PropostaModel, proposal.id)
    model.status = 'enviada'
    model.enviada_em = datetime.now(timezone.utc)
    model.politica_pagamento = policy
    db.get(OrcamentoModel, budget_id).status = 'proposta_enviada'
    db.commit()
    commercial.aprovar(db, model.id)
    return db.get(PropostaModel, model.id), finance.buscar_por_proposta(db, model.id)

def provider_result(payment, status=PagamentoStatus.APROVADO):
    return ProviderPaymentResult(
        provider_id='ORDER-' + str(payment.id),
        external_reference=payment.provider_reference,
        currency='BRL',
        status=status,
        provider_status='processed' if status == PagamentoStatus.APROVADO else 'refunded',
        status_detail='accredited' if status == PagamentoStatus.APROVADO else 'refunded',
        method='pix',
        amount=Decimal(str(payment.valor)),
        approved_at=datetime.now(timezone.utc),
    )
'''


class CommerceDomainTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(DOMAIN_SETUP + source)

    def test_acceptance_creates_only_one_charge_and_no_production(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal, charge = accepted(db, 1)
    assert proposal.status == 'aceita'
    assert db.get(OrcamentoModel, 1).status == 'aprovado'
    assert charge is not None and charge.status == 'pendente'
    assert crud_producao.buscar_por_orcamento(db, 1) is None
    commercial.aprovar(db, proposal.id)
    assert db.scalar(select(func.count()).select_from(CobrancaModel)) == 1
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 0
''')

    def test_integral_policy_requires_the_full_approved_total(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal, charge = accepted(db, 1, 'integral')
    finance.registrar_pagamento(
        db, charge.id, tipo='entrada', valor='75.12', status='aprovado'
    )
    assert release.avaliar_liberacao_producao(db, charge.id) is None
    finance.registrar_pagamento(
        db, charge.id, tipo='saldo', valor='75.13', status='aprovado'
    )
    production = release.avaliar_liberacao_producao(db, charge.id)
    db.commit()
    assert production.orcamento_id == proposal.orcamento_id
    assert release.avaliar_liberacao_producao(db, charge.id).id == production.id
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1
''')

    def test_entry_policy_uses_the_authoritative_odd_cent_split(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal, charge = accepted(db, 1)
    assert finance.dividir_50_50(charge.valor_total) == (
        Decimal('75.12'), Decimal('75.13')
    )
    finance.registrar_pagamento(
        db, charge.id, tipo='entrada', valor='75.11', status='aprovado'
    )
    finance.registrar_pagamento(
        db, charge.id, tipo='saldo', valor='0.01', status='pendente'
    )
    finance.registrar_pagamento(
        db, charge.id, tipo='integral', valor='0.01', status='recusado'
    )
    assert release.avaliar_liberacao_producao(db, charge.id) is None
    pending = next(item for item in charge.pagamentos if item.status == 'pendente')
    pending.status = 'aprovado'
    pending.aprovado_em = datetime.now(timezone.utc)
    finance.sincronizar_status(charge)
    production = release.avaliar_liberacao_producao(db, charge.id)
    db.commit()
    assert production is not None
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1
''')

    def test_cancelled_states_never_release_and_history_is_preserved(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal, charge = accepted(db, 1)
    charge.status = 'cancelada'
    db.add(PagamentoModel(
        cobranca=charge, tipo='entrada', valor=Decimal('75.12'), status='aprovado'
    ))
    db.flush()
    assert release.avaliar_liberacao_producao(db, charge.id) is None

    second, second_charge = accepted(db, 2)
    second.status = 'cancelada'
    db.add(PagamentoModel(
        cobranca=second_charge, tipo='entrada', valor=Decimal('75.12'), status='aprovado'
    ))
    db.flush()
    assert release.avaliar_liberacao_producao(db, second_charge.id) is None

    third, third_charge = accepted(db, 3)
    finance.registrar_pagamento(
        db, third_charge.id, tipo='entrada', valor='75.12', status='aprovado'
    )
    production = release.avaliar_liberacao_producao(db, third_charge.id)
    db.commit()
    approved = third_charge.pagamentos[0]
    approved.status = 'reembolsado'
    approved.reembolsado_em = datetime.now(timezone.utc)
    finance.sincronizar_status(third_charge)
    assert release.avaliar_liberacao_producao(db, third_charge.id).id == production.id
    db.commit()
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1
''')

    def test_provider_result_and_failure_share_the_same_transaction(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal, charge = accepted(db, 1)
    payment = mp_service.criar_tentativa(
        db, charge.id, tipo='entrada', metodo='pix'
    )
    result = provider_result(payment)
    with patch.object(
        crud_producao,
        'criar_sem_commit',
        side_effect=SQLAlchemyError('synthetic production failure'),
    ):
        try:
            mp_service._persistir_resultado(db, payment.id, result)
        except SQLAlchemyError:
            pass
        else:
            raise AssertionError('production failure was hidden')
    db.expire_all()
    assert db.get(PagamentoModel, payment.id).status == 'pendente'
    assert crud_producao.buscar_por_orcamento(db, proposal.orcamento_id) is None
    mp_service._persistir_resultado(db, payment.id, result)
    assert crud_producao.buscar_por_orcamento(db, proposal.orcamento_id) is not None
    mp_service._persistir_resultado(db, payment.id, result)
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1
''')


if __name__ == "__main__":
    unittest.main()
