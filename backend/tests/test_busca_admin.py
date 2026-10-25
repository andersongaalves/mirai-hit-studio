"""AUD6-S09-006: Admin global search is Admin-only, grouped, escaped and skips test chains."""
import unittest

import test_bootstrap_database as isolated

SETUP = r'''
import asyncio

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models import ClienteModel, OrcamentoModel, UsuarioModel
from routers.busca_admin import router

bootstrap(engine)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=2, username='ana.produtora', nome_exibicao='Ana Beats', password_hash='unused',
                     role='produtor', is_admin=False, ativo=True),
        ClienteModel(id=1, nome='Ana Souza', email='ana@example.test'),
        ClienteModel(id=2, nome='Ana Teste', email='teste@example.test', is_test=True),
        ClienteModel(id=3, nome='100% Rock', email='rock@example.test'),
    ])
    db.flush()
    db.add_all([
        OrcamentoModel(id=7, nome_cliente='Ana Souza', email='ana@example.test', servico='Mixagem', valor_total=0),
        OrcamentoModel(id=8, nome_cliente='Ana Teste', email='teste@example.test', servico='Mixagem', valor_total=0, is_test=True),
    ])
    db.commit()
app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(name, uid):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': name, 'av': 0, 'uid': uid})}
'''


class BuscaAdminTests(unittest.TestCase):
    def test_grouped_admin_only_search(self):
        isolated.BootstrapTests().run_case(SETUP + r'''
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/admin/busca?q=ana')).status_code == 401
        assert (await client.get('/admin/busca?q=ana', headers=bearer('ana.produtora', 2))).status_code == 403
        assert (await client.get('/admin/busca?q=a', headers=bearer('admin', 1))).status_code == 422
        found = (await client.get('/admin/busca?q=  ana ', headers=bearer('admin', 1))).json()
        groups = {group['tipo']: group for group in found['grupos']}
        assert found['termo'] == 'ana'
        assert [item['titulo'] for item in groups['clientes']['itens']] == ['Ana Souza']  # test client stays out
        assert groups['clientes']['secao'] == 'section-clientes'
        assert [item['id'] for item in groups['orcamentos']['itens']] == [7]
        assert groups['orcamentos']['itens'][0]['filtro'] == 'Ana Souza'
        assert groups['usuarios']['itens'][0] == {'id': 2, 'titulo': 'Ana Beats', 'detalhe': 'ana.produtora · produtor', 'filtro': 'ana.produtora'}
        by_number = (await client.get('/admin/busca?q=%237', headers=bearer('admin', 1))).json()
        assert [item['id'] for item in {g['tipo']: g for g in by_number['grupos']}['orcamentos']['itens']] == [7]
        literal = (await client.get('/admin/busca?q=0%25', headers=bearer('admin', 1))).json()
        assert [item['titulo'] for item in literal['grupos'][0]['itens']] == ['100% Rock']  # % is literal
        wildcard = (await client.get('/admin/busca?q=%25%25', headers=bearer('admin', 1))).json()
        assert wildcard['grupos'] == []
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
