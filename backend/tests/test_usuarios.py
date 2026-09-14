"""Administrative user management contracts on disposable SQLite."""

import unittest

import test_bootstrap_database as isolated


SETUP = r'''
import asyncio

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.security import create_access_token, get_password_hash, verify_password
from database import get_db
from models import OrcamentoModel, ProducaoModel, UsuarioModel
from routers.auth import router as auth_router
from routers.usuarios import router as usuarios_router

bootstrap(engine)
with Session(engine) as db:
    admin = UsuarioModel(username='admin', password_hash=get_password_hash('admin-pass'), role='admin', is_admin=True, ativo=True)
    produtor = UsuarioModel(username='produtor', password_hash=get_password_hash('producer-pass'), role='produtor', is_admin=False, ativo=True)
    db.add_all([admin, produtor])
    db.flush()
    budget = OrcamentoModel(nome_cliente='Cliente', email='cliente@example.com', servico='Mix', produtor_id=produtor.id)
    db.add(budget)
    db.flush()
    db.add(ProducaoModel(titulo='Historico', cliente='Cliente', servico='Mix', produtor_id=produtor.id, orcamento_id=budget.id, etapas='[]'))
    db.commit()

app = FastAPI()
app.include_router(auth_router)
app.include_router(usuarios_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username})}
'''


class UsuarioTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_crud_permissions_passwords_and_history(self):
        self.run_case(r'''
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/usuarios')).status_code == 401
        assert (await client.get('/usuarios', headers=bearer('produtor'))).status_code == 403
        produtores = await client.get('/usuarios/produtores', headers=bearer('produtor'))
        assert produtores.status_code == 200 and len(produtores.json()) == 2
        listed = await client.get('/usuarios', headers=bearer('admin'))
        assert listed.status_code == 200 and len(listed.json()) == 2
        assert all('password' not in key for item in listed.json() for key in item)

        created = await client.post('/usuarios', headers=bearer('admin'), json={
            'username':'novo_usuario', 'password':'new-password', 'role':'produtor',
        })
        assert created.status_code == 201, created.text
        data = created.json()
        assert data['ativo'] is True and data['role'] == 'produtor' and data['is_admin'] is False
        assert all('password' not in key for key in data)
        identifier = data['id']
        with Session(engine) as db:
            saved = db.get(UsuarioModel, identifier)
            assert saved.password_hash != 'new-password'
            assert verify_password('new-password', saved.password_hash)

        assert (await client.post('/usuarios', headers=bearer('admin'), json={
            'username':'novo_usuario', 'password':'other-password', 'role':'produtor',
        })).status_code == 409
        assert (await client.post('/usuarios', headers=bearer('admin'), json={
            'username':'blocked', 'password':'short', 'role':'produtor',
        })).status_code == 422
        assert (await client.post('/usuarios', headers=bearer('admin'), json={
            'username':'blocked', 'password':'valid-password', 'role':'owner',
        })).status_code == 422
        assert (await client.patch(f'/usuarios/{identifier}', headers=bearer('admin'), json={
            'password_hash':'plain',
        })).status_code == 422

        edited = await client.patch(f'/usuarios/{identifier}', headers=bearer('admin'), json={
            'username':'usuario_editado', 'role':'admin',
        })
        assert edited.status_code == 200, edited.text
        assert edited.json()['role'] == 'admin' and edited.json()['is_admin'] is True
        by_role = await client.get('/usuarios?role=admin&ativo=true', headers=bearer('admin'))
        assert len(by_role.json()) == 2

        reset = await client.patch(f'/usuarios/{identifier}/senha', headers=bearer('admin'), json={
            'nova_senha':'reset-password',
        })
        assert reset.status_code == 200 and all('password' not in key for key in reset.json())
        assert (await client.post('/auth/login', json={'username':'usuario_editado', 'password':'new-password'})).status_code == 401
        assert (await client.post('/auth/login', json={'username':'usuario_editado', 'password':'reset-password'})).status_code == 200

        disabled = await client.patch('/usuarios/2', headers=bearer('admin'), json={'ativo':False})
        assert disabled.status_code == 200 and disabled.json()['ativo'] is False
        produtores = await client.get('/usuarios/produtores', headers=bearer('admin'))
        assert all(item['id'] != 2 for item in produtores.json())
        assert (await client.post('/auth/login', json={'username':'produtor', 'password':'producer-pass'})).status_code == 401
        assert (await client.get('/auth/me', headers=bearer('produtor'))).status_code == 401
        with Session(engine) as db:
            production = db.query(ProducaoModel).filter_by(titulo='Historico').one()
            assert production.produtor_id == 2
            assert production.produtor.username == 'produtor'
        assert (await client.patch('/usuarios/2', headers=bearer('admin'), json={'ativo':True})).status_code == 200
        assert (await client.post('/auth/login', json={'username':'produtor', 'password':'producer-pass'})).status_code == 200

        assert (await client.patch('/usuarios/1', headers=bearer('admin'), json={'ativo':False})).status_code == 409
        assert (await client.patch('/usuarios/1', headers=bearer('admin'), json={'role':'produtor'})).status_code == 409
        assert (await client.get('/usuarios/999', headers=bearer('admin'))).status_code == 404
        assert (await client.patch('/usuarios/999', headers=bearer('admin'), json={'ativo':True})).status_code == 404
asyncio.run(check())
''')

    def test_migration_backfills_existing_users_and_matches_metadata(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

config = migration_config()
head = bootstrap(engine)
assert head == 'b7d3e9a1c5f2'
command.downgrade(config, 'a4c82d91f6e3')
assert 'ativo' not in {column['name'] for column in inspect(engine).get_columns('usuarios')}
with engine.begin() as connection:
    connection.exec_driver_sql("INSERT INTO usuarios (username, password_hash, is_admin, role) VALUES ('legado', 'hash', 1, 'admin')")
command.upgrade(config, 'head')
assert 'ativo' in {column['name'] for column in inspect(engine).get_columns('usuarios')}
with engine.connect() as connection:
    assert connection.exec_driver_sql("SELECT ativo FROM usuarios WHERE username='legado'").scalar_one() in (1, True)
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
''')


if __name__ == "__main__":
    unittest.main()
