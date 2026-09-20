"""Focused F3.1 tests using disposable SQLite only."""

import unittest

import test_bootstrap_database as isolated
from test_proposta_service import SETUP


FINANCE_SETUP = SETUP + r'''
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError
from models import ClienteModel, CobrancaModel, PagamentoModel
from models.enums.financeiro import CobrancaStatus
from services import financial_service as finance
from services import proposta_comercial_service as commercial
from crud import crud_producao
'''


class FinanceiroTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(FINANCE_SETUP + source)

    def test_decimal_precision_and_split(self):
        self.run_case(r'''
for source, expected in [('0.01', '0.01'), ('0.10', '0.10'), ('99.90', '99.90'),
                         ('100.00', '100.00'), ('198.00', '198.00')]:
    assert finance.normalizar_valor(source) == Decimal(expected)
assert finance.dividir_50_50('198.00') == (Decimal('99.00'), Decimal('99.00'))
assert finance.dividir_50_50('199.99') == (Decimal('99.99'), Decimal('100.00'))
for invalid in ['NaN', 'Infinity', '-0.01', '0']:
    try:
        finance.normalizar_valor(invalid)
    except finance.FinanceiroInvalido:
        pass
    else:
        raise AssertionError(f'invalid money accepted: {invalid}')
''')

    def test_receivable_payments_status_and_constraints(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal = service.criar_por_orcamento(db, 1)
    model = db.get(PropostaModel, proposal.id)
    try:
        finance.criar_para_proposta(db, model)
    except finance.FinanceiroConflito:
        pass
    else:
        raise AssertionError('draft proposal created a receivable')
    model.status = 'enviada'
    db.commit()
    charge = finance.criar_para_proposta(db, model)
    assert charge.valor_total == Decimal('150.25')
    assert charge.moeda == 'BRL' and charge.cliente_id is None
    assert finance.criar_para_proposta(db, model).id == charge.id
    assert db.scalar(select(func.count()).select_from(CobrancaModel)) == 1

    finance.registrar_pagamento(db, charge.id, tipo='integral', valor='150.25', status='recusado')
    finance.registrar_pagamento(db, charge.id, tipo='entrada', valor='75.12', status='aprovado')
    assert charge.status == CobrancaStatus.PARCIALMENTE_PAGA.value
    assert finance.valor_pago(charge) == Decimal('75.12')
    finance.registrar_pagamento(db, charge.id, tipo='saldo', valor='75.13', status='aprovado')
    assert charge.status == CobrancaStatus.PAGA.value
    assert finance.valor_pago(charge) == Decimal('150.25')
    try:
        finance.registrar_pagamento(db, charge.id, tipo='saldo', valor='0.01', status='aprovado')
    except finance.FinanceiroConflito:
        pass
    else:
        raise AssertionError('overpayment accepted')
    db.commit()

    provider_id = 'provider-payment-unique'
    finance.registrar_pagamento(db, charge.id, tipo='integral', valor='1.00',
                                status='cancelado', provider_payment_id=provider_id)
    db.commit()
    try:
        finance.registrar_pagamento(db, charge.id, tipo='integral', valor='1.00',
                                    status='recusado', provider_payment_id=provider_id)
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError('duplicate provider id accepted')

with Session(engine) as db:
    proposal = service.criar_por_orcamento(db, 2)
    model = db.get(PropostaModel, proposal.id)
    model.status = 'enviada'
    db.commit()
    charge = finance.criar_para_proposta(db, model)
    finance.registrar_pagamento(db, charge.id, tipo='entrada', valor='50.00', status='reembolsado')
    finance.registrar_pagamento(db, charge.id, tipo='entrada', valor='50.00', status='cancelado')
    assert charge.status == CobrancaStatus.PENDENTE.value
    assert finance.valor_pago(charge) == Decimal('0.00')
''')

    def test_approval_is_atomic_idempotent_and_preserves_legacy(self):
        self.run_case(r'''
def sent_proposal(db, budget_id):
    response = service.criar_por_orcamento(db, budget_id)
    model = db.get(PropostaModel, response.id)
    model.status = 'enviada'
    model.enviada_em = datetime.now(timezone.utc)
    db.get(OrcamentoModel, budget_id).status = 'proposta_enviada'
    db.commit()
    return model

with Session(engine) as db:
    client = ClienteModel(nome='Cliente Financeiro', email='financeiro@example.com')
    db.add(client)
    db.flush()
    db.get(OrcamentoModel, 1).cliente_id = client.id
    db.commit()
    model = sent_proposal(db, 1)
    db.get(OrcamentoModel, 1).valor_total = 1
    db.commit()
    approved = commercial.aprovar(db, model.id)
    charge = finance.buscar_por_proposta(db, model.id)
    assert approved.status == 'aceita'
    assert charge.valor_total == Decimal('150.25') and charge.cliente_id == client.id
    assert crud_producao.buscar_por_orcamento(db, 1) is not None
    commercial.aprovar(db, model.id)
    assert db.scalar(select(func.count()).select_from(CobrancaModel)) == 1
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1

    failing = sent_proposal(db, 2)
    with patch.object(commercial.financial_service, 'criar_para_proposta',
                      side_effect=finance.FinanceiroInvalido('synthetic failure')):
        try:
            commercial.aprovar(db, failing.id)
        except service.PropostaInvalida:
            pass
        else:
            raise AssertionError('financial failure hidden')
    assert db.get(PropostaModel, failing.id).status == 'enviada'
    assert db.get(OrcamentoModel, 2).status == 'proposta_enviada'
    assert crud_producao.buscar_por_orcamento(db, 2) is None
    assert finance.buscar_por_proposta(db, failing.id) is None

    legacy = sent_proposal(db, 3)
    crud_producao.criar_sem_commit(db, commercial._dados_producao(service._resposta(legacy)))
    legacy.status = 'aceita'
    legacy.aprovada_em = datetime.now(timezone.utc)
    db.get(OrcamentoModel, 3).status = 'aprovado'
    db.commit()
    assert commercial.aprovar(db, legacy.id).status == 'aceita'
    assert finance.buscar_por_proposta(db, legacy.id) is None
''')

    def test_migration_upgrade_downgrade_upgrade_matches_metadata(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

config = migration_config()
head = bootstrap(engine)
assert head == 'c4f8a2d19e73'
command.downgrade(config, 'b7d3e9a1c5f2')
assert 'cobrancas' not in inspect(engine).get_table_names()
assert 'pagamentos' not in inspect(engine).get_table_names()
command.upgrade(config, 'head')
assert {'cobrancas', 'pagamentos'} <= set(inspect(engine).get_table_names())
with engine.connect() as connection:
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
assert ScriptDirectory.from_config(config).get_current_head() == head
''')


if __name__ == "__main__":
    unittest.main()
