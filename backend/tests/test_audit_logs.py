"""Structured audit logs on disposable SQLite."""

import unittest

import test_bootstrap_database as isolated


SETUP = r'''
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.http_security import SecurityMiddleware
from core.security import create_access_token, get_password_hash
from database import get_db
from models import AuditLogModel, ProducaoModel, UsuarioModel
from routers.audit_logs import router as audit_router
from routers.producao import router as producao_router
from routers.usuarios import router as usuarios_router

bootstrap(engine)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(username='admin', password_hash=get_password_hash('admin-password'), role='admin', is_admin=True, ativo=True),
        UsuarioModel(username='produtor', password_hash=get_password_hash('producer-password'), role='produtor', is_admin=False, ativo=True),
    ])
    db.flush()
    db.add(ProducaoModel(titulo='Auditar', cliente='Cliente', servico='Mix', produtor_id=2, etapas='[]'))
    db.commit()

app = FastAPI()
app.add_middleware(SecurityMiddleware)
app.include_router(usuarios_router)
app.include_router(producao_router)
app.include_router(audit_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username})}
'''


class AuditLogTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_actions_permissions_filters_pagination_and_redaction(self):
        self.run_case(r'''
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        headers = {**bearer('admin'), 'X-Request-ID':'request-user-create-001'}
        created = await client.post('/usuarios', headers=headers, json={
            'username':'auditado', 'password':'never-log-this', 'role':'produtor',
        })
        assert created.status_code == 201, created.text
        assert created.headers['x-request-id'] == 'request-user-create-001'
        target = created.json()['id']
        assert (await client.patch(f'/usuarios/{target}', headers=bearer('admin'), json={'role':'admin'})).status_code == 200
        assert (await client.patch(f'/usuarios/{target}/senha', headers=bearer('admin'), json={'nova_senha':'another-secret'})).status_code == 200
        assert (await client.patch(f'/usuarios/{target}', headers=bearer('admin'), json={'ativo':False})).status_code == 200
        assert (await client.patch(f'/usuarios/{target}', headers=bearer('admin'), json={'ativo':True})).status_code == 200
        assert (await client.patch('/producoes/1/status', headers=bearer('produtor'), json={'status':'em_producao'})).status_code == 200

        assert (await client.get('/audit-logs')).status_code == 401
        assert (await client.get('/audit-logs', headers=bearer('produtor'))).status_code == 403
        page = await client.get('/audit-logs?page=1&page_size=2', headers=bearer('admin'))
        assert page.status_code == 200, page.text
        body = page.json()
        assert body['total'] == 6 and body['pages'] == 3 and len(body['items']) == 2
        assert [item['id'] for item in body['items']] == sorted([item['id'] for item in body['items']], reverse=True)
        filtered = await client.get('/audit-logs?action=user.password_reset&entity_type=user', headers=bearer('admin'))
        assert filtered.status_code == 200 and filtered.json()['total'] == 1
        password_event = filtered.json()['items'][0]
        assert password_event['metadata'] == {} and password_event['actor_username'] == 'admin'
        created_event = await client.get(f'/audit-logs?action=user.created&entity_id={target}', headers=bearer('admin'))
        assert created_event.json()['items'][0]['request_id'] == 'request-user-create-001'
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        assert (await client.get('/audit-logs', params={'date_from':future}, headers=bearer('admin'))).json()['total'] == 0
        assert (await client.patch('/audit-logs/1', headers=bearer('admin'), json={})).status_code in (404, 405)
        assert (await client.delete('/audit-logs/1', headers=bearer('admin'))).status_code in (404, 405)

    with Session(engine) as db:
        from services.audit_service import record
        admin = db.get(UsuarioModel, 1)
        record(db, actor=admin, action='user.updated', entity_type='user', entity_id=2,
               metadata={'new_role':'produtor', 'password':'secret', 'token':'jwt', 'email':'private@example.com'})
        db.commit()
        entry = db.query(AuditLogModel).order_by(AuditLogModel.id.desc()).first()
        assert entry.metadata_json == {'new_role':'produtor'}
        dump = str([(row.action, row.metadata_json) for row in db.query(AuditLogModel).all()])
        assert 'never-log-this' not in dump and 'another-secret' not in dump and 'private@example.com' not in dump
asyncio.run(check())
''')

    def test_migration_upgrade_downgrade_upgrade_matches_metadata(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

config = migration_config()
assert bootstrap(engine) == 'c4f8a2d19e73'
command.downgrade(config, 'f5b82e1a7c4d')
assert 'audit_logs' not in inspect(engine).get_table_names()
command.upgrade(config, 'head')
assert 'audit_logs' in inspect(engine).get_table_names()
with engine.connect() as connection:
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
''')


if __name__ == "__main__":
    unittest.main()
