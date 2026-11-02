"""Pop-ups sent by the Admin to the client and producer portals."""

import unittest

import test_bootstrap_database as isolated

SETUP = r'''
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models import AuditLogModel, ClienteModel, PortalPopupVistoModel, UsuarioModel
from routers.portal_popups import router as popups_router

bootstrap(engine)
with Session(engine) as db:
    db.add(ClienteModel(id=1, nome='Cliente', email='cliente@example.test'))
    db.flush()
    db.add_all([
        UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=2, username='produtor', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        UsuarioModel(id=3, username='cliente', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1),
    ])
    db.commit()

app = FastAPI()
app.include_router(popups_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username, 'av': 0})}
'''


class PortalPopupTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_admin_sends_popups_by_audience_and_people_close_them(self):
        self.run_case(r'''
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
        admin = bearer('admin')
        base = {'titulo': 'Feriado', 'mensagem': 'Atendimento volta na segunda.', 'publico': 'cliente'}
        assert (await api.post('/admin/popups', headers=bearer('produtor'), json=base)).status_code == 403
        for bad in ({'publico': 'todos', 'botao_rotulo': 'Abrir'}, {'publico': 'cliente', 'botao_rotulo': 'Abrir', 'botao_url': 'javascript:alert(1)'},
                    {'publico': 'cliente', 'botao_rotulo': 'Abrir', 'botao_url': '//evil.example'}, {'tema': 'rosa'}, {'titulo': '   '},
                    {'inicio': '2026-11-10T10:00:00+00:00', 'fim': '2026-11-09T10:00:00+00:00'}):
            assert (await api.post('/admin/popups', headers=admin, json={**base, **bad})).status_code == 422, bad
        client_only = await api.post('/admin/popups', headers=admin, json={**base, 'tema': 'amarelo', 'botao_rotulo': 'Ver projetos', 'botao_url': '/cliente/projetos'})
        assert client_only.status_code == 201, client_only.text
        everyone = await api.post('/admin/popups', headers=admin, json={'titulo': 'Novidade', 'mensagem': 'Linha 1\nLinha 2', 'publico': 'todos', 'frequencia': 'cada_sessao'})
        future = await api.post('/admin/popups', headers=admin, json={**base, 'titulo': 'Depois', 'inicio': (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()})
        paused = await api.post('/admin/popups', headers=admin, json={**base, 'titulo': 'Pausado', 'ativo': False})
        assert future.status_code == 201 and paused.status_code == 201
        # Each portal gets its audience, in order; the Admin sees no pop-ups.
        client_list = (await api.get('/portal/popups', headers=bearer('cliente'))).json()
        assert [item['titulo'] for item in client_list] == ['Feriado', 'Novidade']
        assert client_list[0]['botao_url'] == '/cliente/projetos' and client_list[1]['mensagem'] == 'Linha 1\nLinha 2'
        assert [item['titulo'] for item in (await api.get('/portal/popups', headers=bearer('produtor'))).json()] == ['Novidade']
        assert (await api.get('/portal/popups', headers=admin)).status_code == 403
        # Closing a "show once" pop-up keeps it closed; "each session" ones come back (the browser decides).
        close = f"/portal/popups/{client_only.json()['id']}/fechar"
        assert (await api.post(close, headers=bearer('cliente'))).status_code == 204
        assert (await api.post(close, headers=bearer('cliente'))).status_code == 204
        assert (await api.post(close, headers=bearer('produtor'))).status_code == 404
        assert (await api.post(f"/portal/popups/{paused.json()['id']}/fechar", headers=bearer('cliente'))).status_code == 404
        assert [item['titulo'] for item in (await api.get('/portal/popups', headers=bearer('cliente'))).json()] == ['Novidade']
        await api.post(f"/portal/popups/{everyone.json()['id']}/fechar", headers=bearer('cliente'))
        assert [item['titulo'] for item in (await api.get('/portal/popups', headers=bearer('cliente'))).json()] == ['Novidade']
        listed = {item['titulo']: item for item in (await api.get('/admin/popups', headers=admin)).json()}
        assert listed['Feriado']['fechamentos'] == 1 and listed['Novidade']['fechamentos'] == 1
        # Editing and deleting.
        edited = await api.put(f"/admin/popups/{paused.json()['id']}", headers=admin, json={**base, 'titulo': 'Agora vale', 'ativo': True, 'publico': 'produtor'})
        assert edited.status_code == 200 and edited.json()['titulo'] == 'Agora vale'
        assert [item['titulo'] for item in (await api.get('/portal/popups', headers=bearer('produtor'))).json()] == ['Novidade', 'Agora vale']
        assert (await api.delete(f"/admin/popups/{client_only.json()['id']}", headers=admin)).status_code == 204
        assert (await api.delete(f"/admin/popups/{client_only.json()['id']}", headers=admin)).status_code == 404
    with Session(engine) as db:
        assert db.query(PortalPopupVistoModel).filter_by(popup_id=client_only.json()['id']).count() == 0
        actions = {row.action for row in db.query(AuditLogModel).all()}
        assert {'portal_popup.created', 'portal_popup.updated', 'portal_popup.deleted'} <= actions
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
