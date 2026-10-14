"""Test-mode classification and backend filtering on an isolated database."""

import unittest

import test_bootstrap_database as isolated


SETUP = r"""
import asyncio
from decimal import Decimal
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from database import get_db
from models import ClienteModel, OrcamentoModel, PropostaModel, ProducaoModel
from models.financeiro import CobrancaModel, PagamentoModel
from routers.dashboard import router as dashboard_router
from routers.financeiro import router as financeiro_router
from routers.orcamentos import router as budget_router
from routers.producao import router as production_router
from routers.clientes import router as client_router
from routers.propostas import router as proposal_router
from routers.usuarios import router as user_router

bootstrap(engine)
from core.config import settings
settings.PUBLIC_FRONTEND_URL = 'http://localhost:4173'
settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
app = FastAPI()
for r in (dashboard_router, financeiro_router, budget_router, production_router, client_router, proposal_router, user_router):
    app.include_router(r)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
    id=1, username='admin', role='admin', is_admin=True, ativo=True)
"""

FIXTURE = r"""
from datetime import datetime, timezone
from models import UsuarioModel
with Session(engine) as db:
    db.add(UsuarioModel(id=1, username='synthetic-admin', password_hash='not-a-secret', role='admin', is_admin=True))
    customer = ClienteModel(id=93, nome='Mixed', email='mixed@example.com', ativo=True)
    db.add(customer)
    db.flush()
    db.add(UsuarioModel(id=46, username='synthetic-client', password_hash='not-a-secret', role='cliente', is_admin=False, cliente_id=93))
    for budget_id, proposal_id, charge_id, payment_id, production_id in ((240,72,73,84,47),(241,75,76,86,50)):
        budget = OrcamentoModel(id=budget_id, nome_cliente='Mixed', email='mixed@example.com', servico='Mix', cliente_id=93, status='aprovado')
        db.add(budget)
        db.flush()
        proposal = PropostaModel(id=proposal_id, orcamento_id=budget.id, numero=f'TEST-{proposal_id}', status='aceita',
            cliente_snapshot={'cliente':{'nome':'Mixed','email':'mixed@example.com'},'orcamento':{'id':budget_id,'servico':'Mix'}},
            itens_json=[{'descricao':'Mix','quantidade':'1','valor_unitario':'10','desconto':'0'}], pagamentos_json=[],
            totais_json={'subtotal':'10','desconto':'0','total':'10'}, enviada_em=datetime.now(timezone.utc), aprovada_em=datetime.now(timezone.utc))
        db.add(proposal)
        db.flush()
        charge = CobrancaModel(id=charge_id, proposta_id=proposal_id, cliente_id=93, valor_total=Decimal('10'), status='parcialmente_paga')
        db.add(charge)
        db.flush()
        db.add(PagamentoModel(id=payment_id, cobranca_id=charge_id, tipo='entrada', valor=Decimal('5'), status='aprovado', metodo='pix',
            provider='mercado_pago', provider_order_id=f'ORDER-{payment_id}', provider_reference=f'KEY-{payment_id}',
            provider_idempotency_key=f'KEY-{payment_id}', aprovado_em=datetime.now(timezone.utc)))
        db.add(ProducaoModel(id=production_id, titulo='Synthetic', cliente='Mixed', servico='Mix', orcamento_id=budget_id, status='em_producao', etapas='[]'))
    db.commit()
"""


class AmbienteTestesTests(unittest.TestCase):
    def test_historical_migration_preserves_mixed_and_protected_chains_and_rollback(self):
        isolated.BootstrapTests().run_case(SETUP + r"""
from alembic import command
from sqlalchemy import MetaData, select
from scripts.bootstrap_database import migration_config
config = migration_config()
command.downgrade(config, 'a7d3e5f9c210')
legacy = MetaData()
legacy.reflect(bind=engine)
with engine.begin() as conn:
    for customer_id in (90,93,94):
        conn.execute(legacy.tables['clientes'].insert().values(id=customer_id,nome='Synthetic',email=f'c{customer_id}@example.com',ativo=True,observacoes=''))
    for user_id,customer_id,name in ((999,90,'yonda'),(46,93,'synthetic-client'),(48,94,'protected')):
        conn.execute(legacy.tables['usuarios'].insert().values(id=user_id,cliente_id=customer_id,username=name,password_hash='synthetic',role='cliente',is_admin=False,ativo=True,auth_version=0))
    for budget_id,proposal_id,customer_id in ((234,67,90),(240,72,93),(998,998,93),(238,73,94)):
        conn.execute(legacy.tables['orcamentos'].insert().values(id=budget_id,cliente_id=customer_id,nome_cliente='Synthetic',email='synthetic@example.com',servico='Mix',status='aprovado',observacoes='',proposta_enviada=True))
        conn.execute(legacy.tables['propostas'].insert().values(id=proposal_id,orcamento_id=budget_id,numero=f'SYN-{proposal_id}',versao=1,status='aceita',cliente_snapshot={},objeto='Mix',descricao='',itens_json=[],pagamentos_json=[],condicoes='',totais_json={},politica_pagamento='entrada_50_50'))
    conn.execute(legacy.tables['cobrancas'].insert().values(id=73,proposta_id=72,cliente_id=93,valor_total=10,moeda='BRL',status='parcialmente_paga',referencia_externa='synthetic-only'))
    conn.execute(legacy.tables['pagamentos'].insert().values(id=84,cobranca_id=73,tipo='entrada',valor=5,status='aprovado',metodo='pix',provider='mercado_pago',provider_order_id='SYN-84'))
    financial_before = conn.execute(select(legacy.tables['pagamentos'])).all()
command.upgrade(config,'head')
with engine.connect() as conn:
    assert conn.exec_driver_sql('SELECT id,is_test FROM orcamentos ORDER BY id').all() == [(234,False),(238,False),(240,True),(998,False)]
    assert conn.exec_driver_sql('SELECT id,is_test FROM clientes ORDER BY id').all() == [(90,False),(93,False),(94,False)]
    assert conn.execute(select(legacy.tables['pagamentos'])).all() == financial_before
command.downgrade(config,'a7d3e5f9c210')
assert 'is_test' not in {c['name'] for c in inspect(engine).get_columns('usuarios')}
with engine.connect() as conn:
    assert conn.execute(select(legacy.tables['pagamentos'])).all() == financial_before
command.upgrade(config,'head')
assert 'is_test' in {c['name'] for c in inspect(engine).get_columns('usuarios')}
""")

    def test_admin_classification_confirmation_idempotency_and_financial_history(self):
        isolated.BootstrapTests().run_case(SETUP + FIXTURE + r"""
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.patch('/propostas/72/classificacao', json={'is_test': 'true'})).status_code == 422
        assert (await client.patch('/propostas/72/classificacao', json={'is_test': True})).status_code == 409
        payload = {'is_test': True, 'confirmar_historico_financeiro': True}
        for _ in range(2):
            response = await client.patch('/propostas/72/classificacao', json=payload)
            assert response.status_code == 200, response.text
            assert response.json()['is_test'] is True
        assert (await client.patch('/propostas/72/classificacao', json={'is_test': False, 'confirmar_historico_financeiro': True})).status_code == 409
        dash = (await client.get('/dashboard')).json()
        assert dash['pipeline']['propostas_aprovadas'] == 1, dash
        assert dash['metrics']['producoes_ativas'] == 1, dash
        assert dash['metrics']['clientes_ativos'] == 1, dash
        assert all('TEST-72' not in e['titulo'] for e in dash['recent_activity'])
        assert len((await client.get('/orcamentos')).json()) == 1
        assert len((await client.get('/orcamentos?ambiente=teste')).json()) == 1
        assert len((await client.get('/orcamentos?ambiente=todos')).json()) == 2
        assert len((await client.get('/producoes?ambiente=teste')).json()) == 1
        tests = (await client.get('/financeiro/cobrancas?ambiente=teste')).json()
        assert tests['total'] == 1 and tests['items'][0]['is_test']
        assert (await client.get('/financeiro/resumo?ambiente=todos')).json()['valor_recebido'] == '10.00'
        assert (await client.get('/financeiro/cobrancas/73')).json()['pagamentos'][0]['id'] == 84
        mixed = (await client.get('/clientes')).json()
        assert len(mixed) == 1 and mixed[0]['total_orcamentos'] == 1, mixed
        for role in ('cliente', 'produtor'):
            app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(id=46, role=role, is_admin=False, ativo=True)
            assert (await client.patch('/propostas/72/classificacao', json=payload)).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='admin', is_admin=True, ativo=True)
        assert (await client.patch('/propostas/99999/classificacao', json=payload)).status_code == 404
asyncio.run(check())
with Session(engine) as db:
    from models.audit_log import AuditLogModel
    assert db.query(AuditLogModel).filter_by(action='proposal.classification_changed').count() == 1
    entry = db.query(AuditLogModel).filter_by(action='proposal.classification_changed').one()
    assert entry.actor_user_id == 1 and entry.metadata_json['old_is_test'] is False
    assert entry.metadata_json['new_is_test'] is True and entry.metadata_json['financial_history_confirmed'] is True
    assert db.get(PagamentoModel, 84).status == 'aprovado'
    assert db.get(PagamentoModel, 84).valor == Decimal('5.00')
    assert db.get(CobrancaModel, 73).status == 'parcialmente_paga'
    assert db.get(ProducaoModel, 47).status == 'em_producao'
    assert db.get(ClienteModel, 93).is_test is False
""")

    def test_reversible_empty_chain_and_protected_identity_after_rekey(self):
        isolated.BootstrapTests().run_case(SETUP + FIXTURE + r"""
with Session(engine) as db:
    charge = db.get(CobrancaModel, 76)
    db.delete(charge)
    db.commit()
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        for value in (True, False):
            response = await client.patch('/propostas/75/classificacao', json={'is_test': value})
            assert response.status_code == 200 and response.json()['is_test'] == value, response.text
        with Session(engine) as db:
            user = db.get(__import__('models').UsuarioModel, 46)
            user.username = ' YONDA '
            db.commit()
        response = await client.patch('/propostas/72/classificacao', json={'is_test': True, 'confirmar_historico_financeiro': True})
        assert response.status_code == 409, response.text
        response = await client.patch('/usuarios/46/classificacao', json={'is_test': True})
        assert response.status_code == 409, response.text
asyncio.run(check())
""")

    def test_accounts_are_independent_and_protected_roles_remain_protected(self):
        isolated.BootstrapTests().run_case(SETUP + FIXTURE + r"""
from models import UsuarioModel
with Session(engine) as db:
    db.add(UsuarioModel(id=100, username='synthetic-producer', password_hash='not-a-secret', role='produtor', is_admin=False))
    db.commit()
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        for value in (True, False):
            response = await client.patch('/usuarios/100/classificacao', json={'is_test': value})
            assert response.status_code == 200 and response.json()['is_test'] == value, response.text
        assert (await client.patch('/usuarios/1/classificacao', json={'is_test': True})).status_code == 409
        assert (await client.patch('/usuarios/46/classificacao', json={'is_test': True})).status_code == 200
        assert (await client.patch('/usuarios/46/classificacao', json={'is_test': False})).status_code == 409
        assert (await client.get('/dashboard')).json()['pipeline']['propostas_aprovadas'] == 2
        assert len((await client.get('/clientes')).json()) == 1
        assert len((await client.get('/orcamentos')).json()) == 2
asyncio.run(check())
with Session(engine) as db:
    assert db.get(ClienteModel, 93).is_test is True
    assert not db.get(OrcamentoModel, 240).is_test
""")

    def test_new_test_payments_are_blocked_but_existing_reconciliation_survives(self):
        isolated.BootstrapTests().run_case(SETUP + FIXTURE + r"""
from integrations.mercado_pago import ProviderPaymentResult
from models.enums.financeiro import PagamentoStatus
from services import checkout_service, mercado_pago_service, classificacao_service
from schemas.proposta import PropostaClassificacaoUpdate
from unittest.mock import Mock
from core.config import settings
settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
with Session(engine) as db:
    classificacao_service.alterar(db, 72, PropostaClassificacaoUpdate(is_test=True, confirmar_historico_financeiro=True), db.get(__import__('models').UsuarioModel,1))
    charge = db.get(CobrancaModel, 73)
    fake = Mock()
    try:
        checkout_service._get_or_create_attempt(db, charge, tipo='saldo', metodo='pix', v2=True, cliente_id=93)
    except checkout_service.CheckoutConflito:
        pass
    else:
        raise AssertionError('test order accepted')
    fake.create_pix.assert_not_called()
    try:
        mercado_pago_service.criar_pix(db,73,tipo='saldo',payer=None,client=fake)
    except __import__('services.financial_service',fromlist=['FinanceiroConflito']).FinanceiroConflito:
        db.rollback()
    else:
        raise AssertionError('provider creation accepted for test')
    fake.create_pix.assert_not_called()
    db.get(PagamentoModel,84).status = 'pendente'
    db.get(CobrancaModel,73).status = 'pendente'
    db.commit()
    result = ProviderPaymentResult(provider_id='ORDER-84', external_reference='KEY-84', currency='BRL',
        status=PagamentoStatus.APROVADO, provider_status='processed', status_detail='accredited', method='pix', amount=Decimal('5.00'), approved_at=None)
    mercado_pago_service._apply_reconciliation(db,84,result,expected_order_id='ORDER-84')
    assert db.get(PagamentoModel,84).status == 'aprovado'
    assert db.query(PagamentoModel).count() == 2
""")

    def test_real_dashboard_and_finance_exclude_test_chains(self):
        isolated.BootstrapTests().run_case(SETUP + r"""
with Session(engine) as db:
    real = ClienteModel(nome='Real', email='real@example.com', ativo=True, is_test=False)
    test = ClienteModel(nome='Teste', email='teste@example.com', ativo=True, is_test=True)
    db.add_all([real, test])
    db.flush()
    for index, customer in enumerate((real, test)):
        budget = OrcamentoModel(nome_cliente=customer.nome, email=customer.email,
                                servico='Mix', cliente_id=customer.id, status='novo',
                                is_test=(index == 1))
        db.add(budget)
        db.flush()
        proposal = PropostaModel(orcamento_id=budget.id, numero='P-TEST-' + str(index),
                                 cliente_snapshot={}, itens_json=[], pagamentos_json=[],
                                 totais_json={}, status='aceita')
        db.add(proposal)
        db.flush()
        charge = CobrancaModel(proposta_id=proposal.id, cliente_id=customer.id,
                               valor_total=Decimal('50.00'), status='paga',
                               referencia_externa='ref-test-' + str(index))
        db.add(charge)
        db.flush()
        db.add(PagamentoModel(cobranca_id=charge.id, tipo='integral',
                            valor=Decimal('50.00'), status='aprovado'))
        db.add(ProducaoModel(titulo='Trabalho', cliente=customer.nome, servico='Mix',
                             status='em_producao', orcamento_id=budget.id, etapas='[]'))
    db.commit()

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url='http://test') as client:
        dash = (await client.get('/dashboard')).json()
        assert dash['metrics']['clientes_ativos'] == 1, dash
        assert dash['metrics']['orcamentos_abertos'] == 1, dash
        assert dash['metrics']['producoes_ativas'] == 1, dash
        assert dash['pipeline']['propostas_aprovadas'] == 1, dash

        regular = (await client.get('/financeiro/resumo')).json()
        all_data = (await client.get('/financeiro/resumo?ambiente=todos')).json()
        tests = (await client.get('/financeiro/resumo?ambiente=teste')).json()
        assert regular['valor_recebido'] == '50.00', regular
        assert all_data['valor_recebido'] == '100.00', all_data
        assert tests['valor_recebido'] == '50.00', tests
        assert regular['total_cobrancas'] == 1
        assert all_data['total_cobrancas'] == 2
        assert (await client.get('/financeiro/cobrancas')).json()['total'] == 1
        assert (await client.get('/financeiro/cobrancas?ambiente=teste')).json()['total'] == 1
        assert len((await client.get('/clientes')).json()) == 1
        assert len((await client.get('/clientes?ambiente=teste')).json()) == 1
        assert len((await client.get('/orcamentos')).json()) == 1
        assert len((await client.get('/orcamentos?ambiente=teste')).json()) == 1
        assert len((await client.get('/producoes')).json()) == 1
        assert len((await client.get('/producoes?ambiente=teste')).json()) == 1
asyncio.run(check())
""")


if __name__ == "__main__":
    unittest.main()
