"""Focused Clientes/CRM contracts on disposable SQLite."""

import unittest

import test_bootstrap_database as isolated


SETUP = r'''
import asyncio
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from database import get_db
from models import ClienteModel, OrcamentoModel, ProducaoModel, PropostaModel, UsuarioModel
from routers.clientes import router as clientes_router
from routers.orcamentos import router as orcamentos_router
from core.dependencies import get_current_user
from services.email_service import EmailService

bootstrap(engine)
with Session(engine) as db:
    db.add(UsuarioModel(id=1, username='admin', password_hash='unused', role='admin'))
    db.commit()

app = FastAPI()
app.include_router(clientes_router)
app.include_router(orcamentos_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
app.dependency_overrides[get_current_user] = lambda: object()
'''


class ClienteTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_crud_search_duplicate_and_history(self):
        self.run_case(r'''
async def check():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test'
    ) as client:
        payload = {
            'nome':'Cliente Teste', 'email':'CLIENTE@EXAMPLE.COM',
            'telefone':'+55 (11) 99999-0000', 'observacoes':'<b>texto</b>', 'ativo':True,
        }
        created = await client.post('/clientes', json=payload)
        assert created.status_code == 201, created.text
        data = created.json()
        assert data['email'] == 'cliente@example.com'
        assert data['telefone'] == '5511999990000'
        assert data['observacoes'] == '<b>texto</b>'

        duplicate = await client.post('/clientes', json={**payload, 'nome':'Outro'})
        assert duplicate.status_code == 409
        assert (await client.post('/clientes', json={'nome':'Sem contato'})).status_code == 422

        by_name = await client.get('/clientes', params={'busca':'teste'})
        assert by_name.status_code == 200 and len(by_name.json()) == 1
        by_phone = await client.get('/clientes', params={'busca':'(11) 99999-0000'})
        assert len(by_phone.json()) == 1
        assert (await client.get('/clientes', params={'ativo':False})).json() == []

        edited = await client.patch(f"/clientes/{data['id']}", json={
            'nome':'Cliente Atualizado', 'ativo':False,
        })
        assert edited.status_code == 200 and edited.json()['ativo'] is False
        assert (await client.get('/clientes', params={'ativo':False})).json()[0]['nome'] == 'Cliente Atualizado'
        assert (await client.patch(f"/clientes/{data['id']}", json={'email':None, 'telefone':None})).status_code == 422
        for invalid in ({'nome':None}, {'observacoes':None}, {'ativo':None}):
            assert (await client.patch(f"/clientes/{data['id']}", json=invalid)).status_code == 422
        assert (await client.post('/clientes', json={'nome':'Sem contato real', 'telefone':'---'})).status_code == 422
        assert (await client.get('/clientes/999')).status_code == 404

        with Session(engine) as db:
            budget = OrcamentoModel(
                nome_cliente='Snapshot', email='old@example.com', whatsapp='111',
                servico='Mixagem', valor_total=100, cliente_id=data['id'],
            )
            db.add(budget)
            db.flush()
            proposal = PropostaModel(
                orcamento_id=budget.id, numero='CRM-1', cliente_snapshot={},
                itens_json=[], pagamentos_json=[], totais_json={},
            )
            production = ProducaoModel(
                titulo='Mix', cliente='Snapshot', servico='Mixagem',
                orcamento_id=budget.id, etapas='[]', observacoes='',
            )
            db.add_all([proposal, production])
            db.commit()
        detail = await client.get(f"/clientes/{data['id']}")
        assert detail.status_code == 200, detail.text
        events = {item['evento'] for item in detail.json()['historico']}
        assert {'orcamento_criado', 'proposta_criada', 'producao_criada'} <= events
        assert detail.json()['total_orcamentos'] == 1
asyncio.run(check())
''')

    def test_public_budget_matching_snapshots_and_legacy(self):
        self.run_case(r'''
async def check():
    with patch.object(EmailService, 'enviar_confirmacao'), patch.object(EmailService, 'enviar_notificacao_admin'):
      async with httpx.AsyncClient(
          transport=httpx.ASGITransport(app=app), base_url='http://test'
      ) as client:
        first = await client.post('/orcamentos', json={
            'nome_cliente':'Nome Completo', 'email':'Lead@Example.com',
            'whatsapp':'+55 11 98888-7777', 'servico':'Master',
            'valor_total':300, 'detalhes':'Pedido original',
        })
        assert first.status_code == 200, first.text
        first_data = first.json()
        assert first_data['cliente_id']

        repeated = await client.post('/orcamentos', json={
            'nome_cliente':'Nome curto', 'email':'lead@example.com',
            'whatsapp':'5511988887777', 'servico':'Mixagem',
            'valor_total':500, 'detalhes':'Segundo pedido',
        })
        assert repeated.status_code == 200
        assert repeated.json()['cliente_id'] == first_data['cliente_id']

        other = await client.post('/orcamentos', json={
            'nome_cliente':'Nome Completo', 'email':'outro@example.com',
            'servico':'Beat', 'valor_total':200,
        })
        assert other.status_code == 200
        assert other.json()['cliente_id'] != first_data['cliente_id']

        with Session(engine) as db:
            assert db.query(ClienteModel).count() == 2
            saved = db.get(OrcamentoModel, repeated.json()['id'])
            assert saved.nome_cliente == 'Nome curto'
            assert saved.email == 'lead@example.com'
            assert saved.detalhes == 'Segundo pedido'
            live = db.get(ClienteModel, first_data['cliente_id'])
            assert live.nome == 'Nome Completo'
            legacy = OrcamentoModel(
                nome_cliente='Legado', email='legacy@example.com', servico='Mix',
                valor_total=10, cliente_id=None,
            )
            db.add(legacy)
            db.commit()
            assert legacy.cliente_id is None
asyncio.run(check())
''')

    def test_conflicting_identifiers_and_transaction_rollback(self):
        self.run_case(r'''
from schemas.orcamento import OrcamentoCreate
from services import orcamento_service
from crud import crud_orcamento

with Session(engine) as db:
    db.add_all([
        ClienteModel(nome='Email', email='email@example.com', telefone='111'),
        ClienteModel(nome='Telefone', email='phone@example.com', telefone='222'),
    ])
    db.commit()
    data = OrcamentoCreate(
        nome_cliente='Conflito', email='email@example.com', whatsapp='222',
        servico='Mix', valor_total=100,
    )
    budget = orcamento_service.criar(db, data)
    assert budget.cliente_id is None
    assert db.query(ClienteModel).count() == 2

with Session(engine) as db:
    before = db.query(ClienteModel).count()
    data = OrcamentoCreate(
        nome_cliente='Rollback', email='rollback@example.com',
        servico='Mix', valor_total=100,
    )
    with patch.object(crud_orcamento, 'criar_sem_commit', side_effect=RuntimeError('fail')):
        try:
            orcamento_service.criar(db, data)
        except RuntimeError:
            pass
        else:
            raise AssertionError('failure hidden')
    assert db.query(ClienteModel).count() == before
''')

    def test_endpoints_require_authentication(self):
        isolated.BootstrapTests().run_case(r'''
import asyncio
import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session
from database import get_db
from routers.clientes import router
bootstrap(engine)
app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/clientes')).status_code == 401
        assert (await client.post('/clientes', json={'nome':'Teste', 'email':'x@example.com'})).status_code == 401
asyncio.run(check())
''')

    def test_migration_upgrade_downgrade_upgrade(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

config = migration_config()
head = bootstrap(engine)
assert head == 'd9e4b7a1c2f6'
command.downgrade(config, 'e7a42c6b913f')
inspector = inspect(engine)
assert 'clientes' not in inspector.get_table_names()
assert 'cliente_id' not in {column['name'] for column in inspector.get_columns('orcamentos')}
with engine.begin() as connection:
    connection.exec_driver_sql("""
        INSERT INTO orcamentos
            (nome_cliente, email, servico, valor_total, status, observacoes, proposta_enviada)
        VALUES
            ('Legado', 'legado@example.com', 'Mixagem', 100, 'novo', '', 0)
    """)
command.upgrade(config, 'head')
inspector = inspect(engine)
assert 'clientes' in inspector.get_table_names()
cliente_id = next(column for column in inspector.get_columns('orcamentos') if column['name'] == 'cliente_id')
assert cliente_id['nullable'] is True
assert any(fk['referred_table'] == 'clientes' for fk in inspector.get_foreign_keys('orcamentos'))
with engine.connect() as connection:
    assert connection.exec_driver_sql('SELECT nome_cliente, cliente_id FROM orcamentos').all() == [('Legado', None)]
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
assert ScriptDirectory.from_config(config).get_current_head() == head
with engine.connect() as connection:
    assert connection.exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one() == head
''')


if __name__ == "__main__":
    unittest.main()
