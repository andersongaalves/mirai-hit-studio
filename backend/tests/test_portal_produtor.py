"""Producer portal ownership contracts on disposable SQLite."""

import unittest

import test_bootstrap_database as isolated

SETUP = r'''
import asyncio
import httpx
from fastapi import FastAPI
from jose import jwt
from sqlalchemy.orm import Session

from core.config import settings
from core.security import create_access_token
from database import get_db
from models import ClienteModel, OrcamentoModel, ProducaoModel, UsuarioModel
from routers.portal_produtor import router as portal_router
from routers.producao import router as producao_router

bootstrap(engine)
with Session(engine) as db:
    admin = UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True)
    producer_a = UsuarioModel(id=2, username='producer-a', password_hash='unused', role='produtor', is_admin=False, ativo=True)
    producer_b = UsuarioModel(id=3, username='producer-b', password_hash='unused', role='produtor', is_admin=False, ativo=True)
    client_a = ClienteModel(id=1, nome='Cliente A', email='a@example.test')
    client_b = ClienteModel(id=2, nome='Cliente B', email='b@example.test')
    db.add_all([admin, producer_a, producer_b, client_a, client_b])
    db.flush()
    budget_a = OrcamentoModel(id=1, nome_cliente='Cliente A', email='a@example.test', servico='Mixagem', cliente_id=1, produtor_id=2)
    budget_b = OrcamentoModel(id=2, nome_cliente='Cliente B', email='b@example.test', servico='Masterizacao', cliente_id=2, produtor_id=3)
    db.add_all([budget_a, budget_b])
    db.flush()
    db.add_all([
        ProducaoModel(id=1, titulo='Faixa A', cliente='Cliente A', servico='Mixagem', produtor_id=2, orcamento_id=1, etapas='[]', observacoes='nota administrativa'),
        ProducaoModel(id=2, titulo='Faixa B', cliente='Cliente B', servico='Masterizacao', produtor_id=3, orcamento_id=2, etapas='[]'),
    ])
    db.commit()

app = FastAPI()
app.include_router(portal_router)
app.include_router(producao_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username})}
'''


class PortalProdutorTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_auth_ownership_projection_and_reassignment(self):
        self.run_case(r'''
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/portal/produtor/producoes')).status_code == 401
        assert (await client.get('/portal/produtor/producoes', headers=bearer('admin'))).status_code == 403

        listed = await client.get('/portal/produtor/producoes', headers=bearer('producer-a'))
        assert listed.status_code == 200, listed.text
        assert [item['id'] for item in listed.json()] == [1]
        assert set(listed.json()[0]) == {'id', 'titulo', 'cliente', 'servico', 'status', 'etapas', 'prazo_entrega', 'created_at', 'updated_at'}
        assert 'observacoes' not in listed.text and 'a@example.test' not in listed.text

        own = await client.get('/portal/produtor/producoes/1', headers=bearer('producer-a'))
        other = await client.get('/portal/produtor/producoes/2', headers=bearer('producer-a'))
        missing = await client.get('/portal/produtor/producoes/999', headers=bearer('producer-a'))
        assert own.status_code == 200
        assert other.status_code == missing.status_code == 404
        assert other.json() == missing.json()

        assert (await client.get('/producoes', headers=bearer('producer-a'))).status_code == 403
        assert (await client.get('/producoes', headers=bearer('admin'))).status_code == 200

        with Session(engine) as db:
            production = db.get(ProducaoModel, 1)
            production.produtor_id = 3
            db.commit()

        assert (await client.get('/portal/produtor/producoes/1', headers=bearer('producer-a'))).status_code == 404
        assert (await client.get('/portal/produtor/producoes/1', headers=bearer('producer-b'))).status_code == 200

        assert (await client.get('/portal/produtor/producoes', headers={'Authorization': 'Bearer invalid'})).status_code == 401
        expired = jwt.encode({'sub': 'producer-a', 'exp': 1, 'type': 'access'}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        assert (await client.get('/portal/produtor/producoes', headers={'Authorization': 'Bearer ' + expired})).status_code == 401
asyncio.run(check())
''')


if __name__ == '__main__':
    unittest.main()
