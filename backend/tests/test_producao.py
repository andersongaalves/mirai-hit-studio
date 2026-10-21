"""Focused production admin contracts in a disposable database."""
import unittest

import test_bootstrap_database as isolated


SETUP = '''
import asyncio
import types
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from models import OrcamentoModel, ProducaoModel, PropostaModel, UsuarioModel
from core.dependencies import get_current_user
from routers.producao import router, get_db

bootstrap(engine)
with Session(engine) as db:
    db.add(UsuarioModel(id=1, username='produtor', password_hash='unused', role='produtor'))
    db.add(UsuarioModel(
        id=99, username='admin', password_hash='unused', role='admin', is_admin=True,
    ))
    db.add(OrcamentoModel(
        id=1, nome_cliente='Cliente Teste', email='cliente@example.com',
        servico='Mixagem', valor_total=500,
    ))
    db.flush()
    db.add(PropostaModel(
        id=1, orcamento_id=1, numero='PROP-TESTE', cliente_snapshot={},
        itens_json=[], pagamentos_json=[], totais_json={},
    ))
    db.add(ProducaoModel(
        id=1, titulo='Single Teste', cliente='Cliente Teste', servico='Mixagem',
        status='aguardando_inicio', produtor_id=1, orcamento_id=1,
        etapas='[]', observacoes='',
    ))
    db.commit()

app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(
    id=99, username='admin', role='admin', is_admin=True, ativo=True)
'''


class ProducaoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_direct_combo_selection_is_validated_and_keeps_components(self):
        self.run_case('''
from models.cliente import ClienteModel
from models.combo import ComboItemModel, ComboModel
from models.servico import ServicoModel
with Session(engine) as db:
    db.add(ClienteModel(id=50, nome='Cliente combo', email='combo@example.invalid'))
    db.add_all([ServicoModel(id=50, nome='Mix', valor_base=100), ServicoModel(id=51, nome='Master', valor_base=50)])
    db.add(ComboModel(id=50, nome='Mix + Master', preco_base=120, ativo=True))
    db.add(ComboModel(id=51, nome='Inativo', preco_base=120, ativo=False))
    db.flush()
    db.add_all([ComboItemModel(combo_id=50, servico_id=50, ordem=1), ComboItemModel(combo_id=50, servico_id=51, ordem=2)])
    db.commit()
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        payload = {'request_id':'d2258ffc-0925-4323-ab80-3b2dbef79669', 'cliente_id':50,
                   'combo_id':50, 'titulo':'Single combo'}
        for invalid in ({'combo_id':999}, {'combo_id':51}, {'servico_id':50}):
            result = await client.post('/producoes/direta', json={**payload, **invalid})
            assert result.status_code == 422, result.text
        missing = {key:value for key,value in payload.items() if key != 'combo_id'}
        assert (await client.post('/producoes/direta', json=missing)).status_code == 422
        result = await client.post('/producoes/direta', json=payload)
        assert result.status_code == 201, result.text
        assert result.json()['servico'] == 'Mix + Master'
        repeated = await client.post('/producoes/direta', json=payload)
        assert repeated.json()['id'] == result.json()['id']
        with Session(engine) as db:
            budget = db.get(OrcamentoModel, result.json()['orcamento_id'])
            assert 'Combo #50' in budget.detalhes and 'Mix, Master' in budget.detalhes
asyncio.run(check())
''')

    def test_direct_creation_ownership_idempotency_and_admin_only(self):
        self.run_case('''
from models.cliente import ClienteModel
from models.servico import ServicoModel
from services import portal_cliente_service
with Session(engine) as db:
    db.add_all([
        ClienteModel(id=50, nome='Cliente direto', email='direto@example.invalid', is_test=True),
        ClienteModel(id=51, nome='Outro cliente', email='outro@example.invalid'),
        ServicoModel(id=50, nome='Mix direta', valor_base=100),
    ])
    db.commit()
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        payload = {'request_id':'8c29dbcd-7cc3-4c23-854e-b5083b77fce1', 'cliente_id':50,
                   'servico_id':50, 'titulo':'Single direto', 'produtor_id':1}
        response = await client.post('/producoes/direta', json=payload)
        assert response.status_code == 201, response.text
        item = response.json()
        assert item['cliente'] == 'Cliente direto' and item['proposta_id'] is None
        repeated = await client.post('/producoes/direta', json=payload)
        assert repeated.status_code == 201 and repeated.json()['id'] == item['id']
        assert (await client.post('/producoes/direta', json={**payload, 'titulo':'Outro'})).status_code == 409
        with Session(engine) as db:
            production = portal_cliente_service.buscar_producao(db, item['id'], 50)
            assert production.produtor_id == 1
            assert db.get(OrcamentoModel, production.orcamento_id).is_test
            try:
                portal_cliente_service.buscar_producao(db, item['id'], 51)
                raise AssertionError('cross-client access')
            except portal_cliente_service.ProducaoClienteNaoEncontrada:
                pass
            assert db.query(ProducaoModel).count() == 2
            assert db.query(PropostaModel).count() == 1
        new = {**payload, 'request_id':'83da9c3d-c106-420c-a827-26ed3aff8120'}
        assert (await client.post('/producoes/direta', json={**new, 'cliente_id':999})).status_code == 422
        assert (await client.post('/producoes/direta', json={**new, 'produtor_id':99})).status_code == 422
        assert (await client.post('/producoes/direta', json={**new, 'servico_id':999})).status_code == 422
        app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(
            id=1, username='produtor', role='produtor', is_admin=False, ativo=True)
        assert (await client.post('/producoes/direta', json=new)).status_code == 403
asyncio.run(check())
''')

    def test_list_detail_and_updates(self):
        self.run_case('''
async def check():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test'
    ) as client:
        listed = await client.get('/producoes')
        assert listed.status_code == 200, listed.text
        item = listed.json()[0]
        assert item['produtor_nome'] == 'produtor'
        assert item['cliente_email'] == 'cliente@example.com'
        assert item['proposta_id'] == 1
        assert item['proposta_numero'] == 'PROP-TESTE'

        detail = await client.get('/producoes/1')
        assert detail.status_code == 200 and detail.json() == item

        status = await client.patch('/producoes/1/status', json={'status':'em_producao'})
        assert status.status_code == 200, status.text
        assert status.json()['status'] == 'em_producao'
        assert status.json()['produtor_nome'] == 'produtor'

        etapas = [{'nome':'Briefing recebido','feito':True}, {'nome':'Mix','feito':False}]
        updated = await client.patch('/producoes/1/etapas', json={'etapas':__import__('json').dumps(etapas)})
        assert updated.status_code == 200, updated.text
        assert __import__('json').loads(updated.json()['etapas']) == etapas

        notes = await client.patch('/producoes/1/observacoes', json={'observacoes':'Nota segura'})
        assert notes.status_code == 200 and notes.json()['observacoes'] == 'Nota segura'

        deadline = await client.patch('/producoes/1/prazo', json={'prazo_entrega':'2030-01-01T12:00:00Z'})
        assert deadline.status_code == 200 and deadline.json()['prazo_entrega']
        cleared = await client.patch('/producoes/1/prazo', json={'prazo_entrega':None})
        assert cleared.status_code == 200 and cleared.json()['prazo_entrega'] is None
asyncio.run(check())
''')

    def test_invalid_missing_and_protected_fields(self):
        self.run_case('''
async def check():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url='http://test'
    ) as client:
        assert (await client.get('/producoes/999')).status_code == 404
        for suffix, payload in [
            ('status', {'status':'invalido'}),
            ('status', {'status':'revisao', 'cliente':'forjado'}),
            ('etapas', {'etapas':'not-json'}),
            ('etapas', {'etapas':'[{"nome":"", "feito":true}]'}),
            ('observacoes', {'observacoes':'x' * 20001}),
        ]:
            response = await client.patch('/producoes/1/' + suffix, json=payload)
            assert response.status_code == 422, (suffix, response.text)
        for suffix, payload in [
            ('status', {'status':'revisao'}),
            ('etapas', {'etapas':'[]'}),
            ('prazo', {'prazo_entrega':None}),
            ('observacoes', {'observacoes':''}),
        ]:
            assert (await client.patch('/producoes/999/' + suffix, json=payload)).status_code == 404

        create = {
            'titulo':'Nova', 'cliente':'Cliente', 'servico':'Master',
            'produtor_id':999, 'etapas':'[]',
        }
        assert (await client.post('/producoes', json=create)).status_code == 422
        duplicate = {**create, 'produtor_id':1, 'orcamento_id':1}
        assert (await client.post('/producoes', json=duplicate)).status_code == 409
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
