"""Focused finance admin contracts using only disposable SQLite data."""

import unittest

import test_bootstrap_database as isolated


SETUP = r'''
import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_db, require_admin
from database import get_db as database_dependency
from models import ClienteModel, OrcamentoModel, PropostaModel
from models.audit_log import AuditLogModel
from models.financeiro import CobrancaModel, PagamentoModel
from routers.financeiro import router as financeiro_router

settings.PUBLIC_FRONTEND_URL = 'https://mirai.example'
bootstrap(engine)
app = FastAPI()
app.include_router(financeiro_router)
def session():
    with Session(engine) as db:
        yield db
admin = SimpleNamespace(id=1, username='admin', role='admin', is_admin=True, ativo=True)
app.dependency_overrides[database_dependency] = session
app.dependency_overrides[require_admin] = lambda: admin
'''


class FinanceiroAdminTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_summary_list_detail_filters_and_safe_contract(self):
        self.run_case(r'''
with Session(engine) as db:
    cliente = ClienteModel(nome='<img src=x onerror=alert(1)>', email='cliente@example.com')
    orcamento = OrcamentoModel(nome_cliente='Cliente', email='cliente@example.com', servico='Mix')
    db.add_all([cliente, orcamento])
    db.flush()
    proposta = PropostaModel(
        orcamento_id=orcamento.id, numero='P-2026-001', status='aceita',
        cliente_snapshot={'nome': 'Snapshot', 'email': 'snapshot@example.com'},
        objeto='Mix e master', itens_json=[], pagamentos_json=[], totais_json={},
    )
    db.add(proposta)
    db.flush()
    cobranca = CobrancaModel(
        proposta_id=proposta.id, cliente_id=cliente.id, valor_total=Decimal('100.00'),
        status='parcialmente_paga', referencia_externa='11111111-1111-1111-1111-111111111111',
    )
    db.add(cobranca)
    db.flush()
    db.add_all([
        PagamentoModel(cobranca_id=cobranca.id, tipo='entrada', valor=Decimal('40.00'), status='aprovado', metodo='pix', provider='mercado_pago', provider_order_id='order-1'),
        PagamentoModel(cobranca_id=cobranca.id, tipo='saldo', valor=Decimal('60.00'), status='pendente', metodo='cartao', provider='mercado_pago', provider_order_id='order-2', reconciliation_status='conflict', reconciliation_reason='amount_mismatch'),
    ])
    db.commit()

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        summary = (await client.get('/financeiro/resumo')).json()
        assert summary == {
            'valor_a_receber': '60.00', 'valor_recebido': '40.00',
            'cobrancas_parciais': 1, 'pagamentos_em_atencao': 1, 'total_cobrancas': 1,
        }, summary
        listing = await client.get('/financeiro/cobrancas', params={'search': 'P-2026', 'reconciliation_status': 'conflict'})
        assert listing.status_code == 200, listing.text
        page = listing.json()
        assert page['total'] == 1 and page['items'][0]['saldo_pendente'] == '60.00'
        assert page['items'][0]['cliente_nome'].startswith('<img')
        detail = await client.get(f"/financeiro/cobrancas/{page['items'][0]['id']}")
        assert detail.status_code == 200, detail.text
        data = detail.json()
        assert data['checkout_url'] == 'https://mirai.example/checkout/11111111-1111-1111-1111-111111111111'
        assert [payment['id'] for payment in data['pagamentos']] == sorted([payment['id'] for payment in data['pagamentos']], reverse=True)
        serialized = detail.text
        assert 'provider_idempotency_key' not in serialized and 'provider_reference' not in serialized
        assert (await client.get('/financeiro/cobrancas', params={'date_from': '2026-09-20T12:00:00Z', 'date_to': '2026-09-19T12:00:00Z'})).status_code == 422
asyncio.run(check())
''')

    def test_reconcile_is_admin_only_and_audited(self):
        self.run_case(r'''
with Session(engine) as db:
    orcamento = OrcamentoModel(nome_cliente='Cliente', email='cliente@example.com', servico='Mix')
    db.add(orcamento)
    db.flush()
    proposta = PropostaModel(orcamento_id=orcamento.id, numero='P-2', status='aceita', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={})
    db.add(proposta)
    db.flush()
    cobranca = CobrancaModel(proposta_id=proposta.id, valor_total=Decimal('50.00'), referencia_externa='22222222-2222-2222-2222-222222222222')
    db.add(cobranca)
    db.flush()
    payment = PagamentoModel(cobranca_id=cobranca.id, tipo='integral', valor=Decimal('50.00'), status='pendente', provider='mercado_pago', provider_order_id='order-2')
    db.add(payment)
    db.commit()
    payment_id = payment.id

result = SimpleNamespace(payment_id=payment_id, previous_status='pendente', current_status='aprovado', changed=True, outcome='updated')
async def check():
    with patch('routers.financeiro.mercado_pago_service.reconcile_payment', return_value=result):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post(f'/financeiro/pagamentos/{payment_id}/reconciliar')
            assert response.status_code == 200, response.text
            assert response.json()['current_status'] == 'aprovado'
    with Session(engine) as db:
        audit = db.query(AuditLogModel).filter_by(action='payment.reconciled').one()
        assert audit.entity_id == str(payment_id)
        assert audit.metadata_json == {'old_status': 'pendente', 'new_status': 'aprovado'}
asyncio.run(check())
''')
        isolated.BootstrapTests().run_case(r'''
import asyncio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session
from database import get_db
from routers.financeiro import router
bootstrap(engine)
app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/financeiro/resumo')).status_code == 401
asyncio.run(check())
''')

    def test_producer_gets_forbidden_and_conflict_is_audited(self):
        isolated.BootstrapTests().run_case(r'''
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session
from core.dependencies import get_current_user
from database import get_db
from models.audit_log import AuditLogModel
from routers.financeiro import router
from services.mercado_pago_service import ReconciliationConflict
bootstrap(engine)
app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
producer = SimpleNamespace(id=2, role='produtor', is_admin=False, ativo=True)
app.dependency_overrides[get_current_user] = lambda: producer
async def forbidden():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/financeiro/resumo')).status_code == 403
asyncio.run(forbidden())

admin = SimpleNamespace(id=1, role='admin', is_admin=True, ativo=True)
app.dependency_overrides[get_current_user] = lambda: admin
async def conflict():
    with patch('routers.financeiro.mercado_pago_service.reconcile_payment', side_effect=ReconciliationConflict('amount_mismatch', 9)):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post('/financeiro/pagamentos/9/reconciliar')
            assert response.status_code == 409
            assert 'divergência' in response.json()['detail']
    with Session(engine) as db:
        assert db.query(AuditLogModel).filter_by(action='payment.reconciliation_conflict', entity_id='9').count() == 1
asyncio.run(conflict())
''')


if __name__ == "__main__":
    unittest.main()
