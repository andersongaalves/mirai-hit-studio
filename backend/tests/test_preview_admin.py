"""Admin preview: a client or producer portal seen as that account, read-only."""

import textwrap
import unittest

import test_bootstrap_database as isolated


class PreviewAdminTests(unittest.TestCase):
    def run_case(self, code):
        isolated.BootstrapTests().run_case(textwrap.dedent(code))

    def test_read_only_session_for_clients_and_producers(self):
        self.run_case("""
        bootstrap(engine)
        from datetime import datetime, timezone
        from fastapi import APIRouter, Depends, FastAPI
        from fastapi.testclient import TestClient
        from sqlalchemy.orm import Session
        from core.dependencies import get_current_user
        from core.security import create_access_token, create_refresh_token
        from models import AuditLogModel, ClienteModel, UsuarioModel
        from routers.auth import router as auth_router
        from routers.marketing import router as marketing_router
        from routers.preview_admin import router as preview_router
        with Session(engine) as db:
            db.add(ClienteModel(id=1, nome='Ana Cliente'))
            db.flush()
            db.add_all([
                UsuarioModel(id=1, username='admin', password_hash='x', role='admin', is_admin=True, ativo=True),
                UsuarioModel(id=2, username='ana', password_hash='x', role='cliente', is_admin=False, ativo=True, cliente_id=1),
                UsuarioModel(id=3, username='beto', nome_exibicao='Beto Beats', password_hash='x', role='produtor', is_admin=False, ativo=True),
                UsuarioModel(id=4, username='inativo', password_hash='x', role='produtor', is_admin=False, ativo=False),
                UsuarioModel(id=5, username='outro-admin', password_hash='x', role='admin', is_admin=True, ativo=True),
            ])
            db.commit()
        app = FastAPI()
        for router in (auth_router, marketing_router, preview_router):
            app.include_router(router)
        writes = APIRouter()
        @writes.post('/portal/escrever')
        def escrever(user=Depends(get_current_user)): return {'ok': True}
        @writes.get('/portal/ler')
        def ler(user=Depends(get_current_user)): return {'id': user.id}
        app.include_router(writes)
        client = TestClient(app)
        def bearer(token): return {'Authorization': f'Bearer {token}'}
        admin = bearer(create_access_token({'sub': 'admin', 'av': 0, 'uid': 1}))
        cliente = bearer(create_access_token({'sub': 'ana', 'av': 0, 'uid': 2}))

        # Only admins list accounts and open sessions.
        assert client.get('/admin/preview/contas', headers=cliente).status_code == 403
        assert client.post('/admin/preview/sessao', headers=cliente, json={'usuario_id': 3}).status_code == 403
        listed = client.get('/admin/preview/contas', headers=admin).json()
        assert {item['login'] for item in listed} == {'ana', 'beto'}, listed
        assert {item['nome'] for item in listed} == {'Ana Cliente', 'Beto Beats'}
        assert [item['login'] for item in client.get('/admin/preview/contas', headers=admin, params={'portal': 'produtor'}).json()] == ['beto']
        assert [item['login'] for item in client.get('/admin/preview/contas', headers=admin, params={'busca': 'CLIENTE'}).json()] == ['ana']
        for target in (1, 4, 5, 999):
            assert client.post('/admin/preview/sessao', headers=admin, json={'usuario_id': target}).status_code == 404, target

        opened = client.post('/admin/preview/sessao', headers=admin, json={'usuario_id': 2})
        assert opened.status_code == 201, opened.text
        body = opened.json()
        assert body['portal'] == 'cliente' and body['inicio'] == '/cliente' and body['minutos'] == 30
        assert body['conta']['nome'] == 'Ana Cliente'
        preview = bearer(body['token'])
        # Reads work as the account; writes are refused before the route runs.
        me = client.get('/auth/me', headers=preview)
        assert me.status_code == 200 and me.json()['id'] == 2 and me.json()['role'] == 'cliente', me.text
        assert client.get('/portal/ler', headers=preview).json() == {'id': 2}
        refused = client.post('/portal/escrever', headers=preview)
        assert refused.status_code == 403 and 'visualização' in refused.json()['detail'], refused.text
        # It never reaches admin areas, and it is not a normal session.
        assert client.get('/admin/marketing', headers=preview).status_code == 403
        assert client.post('/admin/preview/sessao', headers=preview, json={'usuario_id': 3}).status_code == 403
        with Session(engine) as db:
            logs = db.query(AuditLogModel).filter_by(action='admin.preview_started').all()
            assert [(row.actor_user_id, row.entity_id, row.metadata_json) for row in logs] == [(1, '2', {'portal': 'cliente'})]

        # Producer preview too.
        producer = bearer(client.post('/admin/preview/sessao', headers=admin, json={'usuario_id': 3}).json()['token'])
        assert client.get('/auth/me', headers=producer).json()['role'] == 'produtor'

        # Signing the admin out everywhere (or demoting them) ends their preview sessions.
        with Session(engine) as db:
            db.get(UsuarioModel, 1).auth_version = 1
            db.commit()
        assert client.get('/auth/me', headers=preview).status_code == 401
        # A target signed out everywhere also ends it.
        admin = bearer(create_access_token({'sub': 'admin', 'av': 1, 'uid': 1}))
        again = bearer(client.post('/admin/preview/sessao', headers=admin, json={'usuario_id': 3}).json()['token'])
        with Session(engine) as db:
            db.get(UsuarioModel, 3).auth_version = 2
            db.commit()
        assert client.get('/auth/me', headers=again).status_code == 401
        # Refresh tokens never pass as access or preview.
        assert client.get('/auth/me', headers=bearer(create_refresh_token({'sub': 'ana', 'av': 0, 'uid': 2}))).status_code == 401
        """)


if __name__ == "__main__":
    unittest.main()
