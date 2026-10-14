"""Roadmap 3.0, 5.01: typed, versioned and audited portal settings."""

import textwrap
import unittest

import test_bootstrap_database as isolated

SETUP = r'''
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models import AuditLogModel, ClienteModel, PortalConfiguracaoModel, UsuarioModel
from routers.portal_config import router

bootstrap(engine)
with Session(engine) as db:
    db.add(ClienteModel(id=1, nome='Cliente A', email='a@example.test'))
    db.flush()
    db.add_all([
        UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=2, username='producer', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        UsuarioModel(id=3, username='client', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1),
    ])
    db.commit()

app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
client = TestClient(app)
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username, 'av': 0})}
'''


class PortalConfigTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + textwrap.dedent(source))

    def test_defaults_publish_validation_concurrency_restore_and_audit(self):
        self.run_case(r'''
        # Built-in defaults until an admin publishes.
        initial = client.get('/portal/cliente/configuracao', headers=bearer('client'))
        assert initial.status_code == 200, initial.text
        assert initial.json()['versao'] == 0
        assert initial.json()['config']['indicadores'] == ['andamento', 'concluidos', 'avaliacao', 'pagamentos']
        assert initial.json()['config']['areas']['propostas'] is True

        # Role isolation: portals read only their own settings; only admins write.
        assert client.get('/portal/produtor/configuracao', headers=bearer('client')).status_code == 403
        assert client.get('/portal/cliente/configuracao', headers=bearer('producer')).status_code == 403
        assert client.get('/portal/cliente/configuracao').status_code == 401
        denied = client.put('/admin/portais/cliente/configuracao', headers=bearer('producer'),
                            json={'base_versao': 0, 'config': {}})
        assert denied.status_code == 403

        admin = client.get('/admin/portais/cliente/configuracao', headers=bearer('admin')).json()
        config = admin['padrao']
        config['aviso'] = {'ativo': True, 'nivel': 'atencao', 'texto': '  Recesso de 20 a 27/12\x00  '}
        config['textos']['titulo_dashboard'] = 'Seu estúdio'
        config['indicadores'] = ['pagamentos', 'andamento']
        config['filtros'] = {'situacao_padrao': 'ativos', 'ordenacao_padrao': 'prazo'}
        config['areas'] = {'propostas': False}
        published = client.put('/admin/portais/cliente/configuracao', headers=bearer('admin'),
                               json={'base_versao': 0, 'config': config})
        assert published.status_code == 200, published.text
        assert published.json()['versao'] == 1
        assert published.json()['config']['aviso']['texto'] == 'Recesso de 20 a 27/12'

        seen = client.get('/portal/cliente/configuracao', headers=bearer('client')).json()
        assert seen['versao'] == 1 and seen['config']['indicadores'] == ['pagamentos', 'andamento']
        assert seen['config']['areas']['propostas'] is False

        # Stale base version is a conflict; nothing is written.
        stale = client.put('/admin/portais/cliente/configuracao', headers=bearer('admin'),
                           json={'base_versao': 0, 'config': config})
        assert stale.status_code == 409

        # Identical content does not create a new version.
        same = client.put('/admin/portais/cliente/configuracao', headers=bearer('admin'),
                          json={'base_versao': 1, 'config': config})
        assert same.status_code == 200 and same.json()['versao'] == 1

        # Typed validation: unknown keys, unknown indicators, duplicates and long text.
        for broken in (
            {**config, 'auth_disabled': True},
            {**config, 'indicadores': ['receita']},
            {**config, 'indicadores': ['andamento', 'andamento']},
            {**config, 'indicadores': []},
            {**config, 'aviso': {'ativo': True, 'nivel': 'info', 'texto': 'x' * 281}},
            {**config, 'filtros': {'situacao_padrao': 'tudo', 'ordenacao_padrao': 'prazo'}},
        ):
            response = client.put('/admin/portais/cliente/configuracao', headers=bearer('admin'),
                                  json={'base_versao': 1, 'config': broken})
            assert response.status_code == 422, (broken, response.text)

        second = dict(config, areas={'propostas': True})
        assert client.put('/admin/portais/cliente/configuracao', headers=bearer('admin'),
                          json={'base_versao': 1, 'config': second}).json()['versao'] == 2

        versions = client.get('/admin/portais/cliente/configuracao/versoes', headers=bearer('admin')).json()
        assert [item['versao'] for item in versions] == [2, 1]

        restored = client.post('/admin/portais/cliente/configuracao/versoes/1/restaurar',
                               headers=bearer('admin'), json={'base_versao': 2})
        assert restored.status_code == 200, restored.text
        assert restored.json()['versao'] == 3 and restored.json()['config']['areas']['propostas'] is False
        missing = client.post('/admin/portais/cliente/configuracao/versoes/99/restaurar',
                              headers=bearer('admin'), json={'base_versao': 3})
        assert missing.status_code == 404

        # The producer portal is versioned independently.
        producer = client.get('/portal/produtor/configuracao', headers=bearer('producer')).json()
        assert producer['versao'] == 0 and producer['config']['filtros']['ordenacao_padrao'] == 'prazo'
        assert client.get('/admin/portais/financeiro/configuracao', headers=bearer('admin')).status_code == 422

        with Session(engine) as db:
            rows = db.scalars(select(PortalConfiguracaoModel).order_by(PortalConfiguracaoModel.versao)).all()
            assert [(row.portal, row.versao, row.restaurada_de_versao, row.autor_usuario_id) for row in rows] == [
                ('cliente', 1, None, 1), ('cliente', 2, None, 1), ('cliente', 3, 1, 1),
            ]
            audits = db.scalars(select(AuditLogModel).order_by(AuditLogModel.id)).all()
            assert [entry.action for entry in audits] == [
                'portal.config_published', 'portal.config_published', 'portal.config_restored',
            ]
            assert audits[-1].metadata_json == {
                'portal': 'cliente', 'old_version': 2, 'new_version': 3, 'restored_from_version': 1,
            }
        ''')

    def test_invalid_stored_version_falls_back_to_defaults(self):
        self.run_case(r'''
        with Session(engine) as db:
            db.add(PortalConfiguracaoModel(portal='produtor', versao=1, dados={'removido': True}))
            db.commit()
        response = client.get('/portal/produtor/configuracao', headers=bearer('producer'))
        assert response.status_code == 200, response.text
        assert response.json()['versao'] == 1
        assert response.json()['config']['indicadores'] == ['ativas', 'revisao', 'vencidos', 'a_receber', 'pago']
        ''')


if __name__ == "__main__":
    unittest.main()
