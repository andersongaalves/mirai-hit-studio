"""Client portal authentication and ownership contracts on disposable SQLite."""

import unittest

import test_bootstrap_database as isolated

SETUP = r'''
import asyncio
from decimal import Decimal

import httpx
from fastapi import FastAPI
from jose import jwt
from sqlalchemy.orm import Session

from core.config import settings
from core.security import create_access_token, get_password_hash
from database import get_db
from models import (
    ClienteModel,
    CobrancaModel,
    OrcamentoModel,
    PagamentoModel,
    ProducaoModel,
    PropostaModel,
    UsuarioModel,
)
from routers.auth import router as auth_router
from routers.financeiro import router as financeiro_router
from routers.portal_cliente import router as cliente_router
from routers.portal_produtor import router as produtor_router
from routers.usuarios import router as usuarios_router

bootstrap(engine)
with Session(engine) as db:
    client_a = ClienteModel(id=1, nome='Cliente A', email='a@example.test')
    client_b = ClienteModel(id=2, nome='Cliente B', email='b@example.test')
    db.add_all([client_a, client_b])
    db.flush()
    users = [
        UsuarioModel(id=1, username='admin', password_hash=get_password_hash('admin-pass'), role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=2, username='producer', password_hash=get_password_hash('producer-pass'), role='produtor', is_admin=False, ativo=True),
        UsuarioModel(id=3, username='client-a', password_hash=get_password_hash('client-a-pass'), role='cliente', is_admin=False, ativo=True, cliente_id=1),
        UsuarioModel(id=4, username='client-b', password_hash=get_password_hash('client-b-pass'), role='cliente', is_admin=False, ativo=True, cliente_id=2),
    ]
    db.add_all(users)
    db.flush()
    budgets = [
        OrcamentoModel(id=1, nome_cliente='Cliente A', email='a@example.test', servico='Mixagem', cliente_id=1, produtor_id=2),
        OrcamentoModel(id=2, nome_cliente='Cliente B', email='b@example.test', servico='Masterizacao', cliente_id=2, produtor_id=2),
        OrcamentoModel(id=3, nome_cliente='Cliente A', email='a@example.test', servico='Producao', cliente_id=1, produtor_id=2),
    ]
    db.add_all(budgets)
    db.flush()
    proposals = [
        PropostaModel(id=1, orcamento_id=1, numero='PROP-A', status='aceita', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={}),
        PropostaModel(id=2, orcamento_id=2, numero='PROP-B', status='enviada', cliente_snapshot={}, itens_json=[], pagamentos_json=[], totais_json={}),
    ]
    db.add_all(proposals)
    db.flush()
    productions = [
        ProducaoModel(id=1, titulo='Faixa A', cliente='Cliente A', servico='Mixagem', status='em_producao', produtor_id=2, orcamento_id=1, etapas='[]', observacoes='nota interna A'),
        ProducaoModel(id=2, titulo='Faixa B', cliente='Cliente B', servico='Masterizacao', status='revisao', produtor_id=2, orcamento_id=2, etapas='[]', observacoes='nota interna B'),
        ProducaoModel(id=3, titulo='Faixa A final', cliente='Cliente A', servico='Producao', status='entregue', produtor_id=2, orcamento_id=3, etapas='[]'),
    ]
    db.add_all(productions)
    charge = CobrancaModel(id=1, proposta_id=1, cliente_id=1, valor_total=Decimal('1000.00'), moeda='BRL', status='parcialmente_paga', referencia_externa='test-reference')
    db.add(charge)
    db.flush()
    db.add(PagamentoModel(id=1, cobranca_id=1, tipo='entrada', valor=Decimal('500.00'), status='aprovado', metodo='credit_card', provider='private-provider', provider_order_id='private-order'))
    db.commit()

app = FastAPI()
for router in (auth_router, usuarios_router, cliente_router, produtor_router, financeiro_router):
    app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username})}
'''


class PortalClienteTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_auth_ownership_history_and_safe_financial_projection(self):
        self.run_case(r'''
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/portal/cliente/producoes')).status_code == 401
        assert (await client.get('/portal/cliente/producoes', headers=bearer('admin'))).status_code == 403
        assert (await client.get('/portal/cliente/producoes', headers=bearer('producer'))).status_code == 403
        assert (await client.get('/portal/produtor/producoes', headers=bearer('client-a'))).status_code == 403

        login = await client.post('/auth/login', json={'username':'client-a', 'password':'client-a-pass'})
        assert login.status_code == 200, login.text
        assert login.json()['user']['cliente_id'] == 1

        listed = await client.get('/portal/cliente/producoes', headers=bearer('client-a'))
        assert listed.status_code == 200, listed.text
        assert [item['id'] for item in listed.json()] == [3, 1]
        assert set(listed.json()[0]) == {'id', 'titulo', 'servico', 'status', 'etapas', 'prazo_entrega', 'created_at', 'updated_at'}
        assert 'nota interna' not in listed.text and 'example.test' not in listed.text

        history = await client.get('/portal/cliente/producoes/historico', headers=bearer('client-a'))
        assert history.status_code == 200
        assert [item['id'] for item in history.json()] == [3]

        own = await client.get('/portal/cliente/producoes/1', headers=bearer('client-a'))
        other = await client.get('/portal/cliente/producoes/2', headers=bearer('client-a'))
        missing = await client.get('/portal/cliente/producoes/999', headers=bearer('client-a'))
        assert own.status_code == 200
        assert other.status_code == missing.status_code == 404
        assert other.json() == missing.json()

        financial = await client.get('/portal/cliente/producoes/1/financeiro', headers=bearer('client-a'))
        assert financial.status_code == 200, financial.text
        data = financial.json()
        assert data['proposta_numero'] == 'PROP-A'
        assert data['cobranca']['valor_total'] == '1000.00'
        assert data['cobranca']['valor_pago'] == '500.00'
        assert data['cobranca']['saldo_pendente'] == '500.00'
        assert data['cobranca']['pagamentos'][0]['status'] == 'aprovado'
        assert data['checkout_url'] == 'http://localhost:4173/checkout/test-reference'
        forbidden = ('provider', 'provider_order_id', 'provider_reference', 'referencia_externa', 'reconciliation', 'observacoes', 'produtor')
        assert not any(term in financial.text for term in forbidden)

        assert (await client.get('/financeiro/resumo', headers=bearer('client-a'))).status_code == 403
        assert (await client.get('/usuarios', headers=bearer('client-a'))).status_code == 403
        assert (await client.get('/portal/cliente/producoes', headers={'Authorization':'Bearer invalid'})).status_code == 401
        expired = jwt.encode({'sub':'client-a', 'exp':1, 'type':'access'}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        assert (await client.get('/portal/cliente/producoes', headers={'Authorization':'Bearer ' + expired})).status_code == 401

        with Session(engine) as db:
            db.get(UsuarioModel, 3).ativo = False
            db.commit()
        assert (await client.get('/portal/cliente/producoes', headers=bearer('client-a'))).status_code == 401
asyncio.run(check())
''')

    def test_admin_provisioning_unique_link_and_immediate_reassignment(self):
        self.run_case(r'''
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        created_client = await client.post('/usuarios', headers=bearer('admin'), json={
            'username':'blocked-client', 'password':'client-password', 'role':'cliente', 'cliente_id':1,
        })
        assert created_client.status_code == 409
        assert (await client.post('/usuarios', headers=bearer('admin'), json={
            'username':'missing-link', 'password':'client-password', 'role':'cliente',
        })).status_code == 422
        assert (await client.post('/usuarios', headers=bearer('admin'), json={
            'username':'missing-client', 'password':'client-password', 'role':'cliente', 'cliente_id':999,
        })).status_code == 422
        assert (await client.post('/usuarios', headers=bearer('client-a'), json={
            'username':'self-provisioned', 'password':'client-password', 'role':'cliente', 'cliente_id':1,
        })).status_code == 403

        released_b = await client.patch('/usuarios/4', headers=bearer('admin'), json={'role':'produtor'})
        assert released_b.status_code == 200 and released_b.json()['cliente_id'] is None
        reassigned = await client.patch('/usuarios/3', headers=bearer('admin'), json={'cliente_id':2})
        assert reassigned.status_code == 200, reassigned.text
        assert reassigned.json()['cliente_id'] == 2
        old = await client.get('/portal/cliente/producoes/1', headers=bearer('client-a'))
        new = await client.get('/portal/cliente/producoes/2', headers=bearer('client-a'))
        assert old.status_code == 404 and new.status_code == 200

        producer = await client.patch('/usuarios/3', headers=bearer('admin'), json={'role':'produtor'})
        assert producer.status_code == 200, producer.text
        assert producer.json()['cliente_id'] is None
        assert (await client.get('/portal/cliente/producoes', headers=bearer('client-a'))).status_code == 403
asyncio.run(check())
''')

    def test_migration_cycle_constraints_and_existing_accounts(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

config = migration_config()
bootstrap(engine)
command.downgrade(config, 'c1e7a4b9d302')
with engine.begin() as connection:
    connection.exec_driver_sql("INSERT INTO usuarios (id, username, password_hash, is_admin, ativo, role) VALUES (1, 'admin', 'hash', 1, 1, 'admin')")
    connection.exec_driver_sql("INSERT INTO usuarios (id, username, password_hash, is_admin, ativo, role) VALUES (2, 'producer', 'hash', 0, 1, 'produtor')")
command.upgrade(config, 'head')
assert 'cliente_id' in {column['name'] for column in inspect(engine).get_columns('usuarios')}
with engine.connect() as connection:
    assert connection.exec_driver_sql("SELECT username, cliente_id FROM usuarios ORDER BY id").all() == [('admin', None), ('producer', None)]
command.downgrade(config, 'c1e7a4b9d302')
assert 'cliente_id' not in {column['name'] for column in inspect(engine).get_columns('usuarios')}
command.upgrade(config, 'head')
with engine.begin() as connection:
    connection.exec_driver_sql("INSERT INTO clientes (id, nome, observacoes, ativo) VALUES (1, 'Client A', '', 1)")
    connection.exec_driver_sql("INSERT INTO usuarios (id, username, password_hash, is_admin, ativo, role, cliente_id) VALUES (3, 'client-a', 'hash', 0, 1, 'cliente', 1)")
try:
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO usuarios (id, username, password_hash, is_admin, ativo, role, cliente_id) VALUES (4, 'client-b', 'hash', 0, 1, 'cliente', 1)")
except IntegrityError:
    pass
else:
    raise AssertionError('duplicate client link accepted')
try:
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO usuarios (id, username, password_hash, is_admin, ativo, role, cliente_id) VALUES (5, 'invalid-client', 'hash', 0, 1, 'cliente', NULL)")
except IntegrityError:
    pass
else:
    raise AssertionError('unlinked client role accepted')
foreign_keys = inspect(engine).get_foreign_keys('usuarios')
assert any(
    item['constrained_columns'] == ['cliente_id']
    and item['referred_table'] == 'clientes'
    for item in foreign_keys
)
try:
    with engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO usuarios (id, username, password_hash, is_admin, ativo, role, cliente_id) VALUES (6, 'invalid-producer', 'hash', 0, 1, 'produtor', 1)")
except IntegrityError:
    pass
else:
    raise AssertionError('producer with client link accepted')
''')


if __name__ == '__main__':
    unittest.main()
