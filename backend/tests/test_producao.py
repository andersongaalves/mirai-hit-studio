"""Focused production admin contracts in a disposable database."""
import unittest

import test_bootstrap_database as isolated


SETUP = '''
import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from models import OrcamentoModel, ProducaoModel, PropostaModel, UsuarioModel
from routers.producao import router, get_current_user, get_db

bootstrap(engine)
with Session(engine) as db:
    db.add(UsuarioModel(id=1, username='produtor', password_hash='unused', role='produtor'))
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
app.dependency_overrides[get_current_user] = lambda: object()
'''


class ProducaoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

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
