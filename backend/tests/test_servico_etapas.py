"""Roadmap 3.0, 5.04: catalog stages with percentage weights."""

import textwrap
import unittest

import test_bootstrap_database as isolated

SETUP = r'''
from decimal import Decimal
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models import AuditLogModel, ServicoEtapaModel, ServicoModel, UsuarioModel
from routers.servicos import router

bootstrap(engine)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=2, username='producer', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        ServicoModel(id=1, nome='Plano Start', subtitulo='', valor_base=1000, categoria='Mix', aplica_desconto=False,
                     parametros='', estrutura_servico='{"intro":"","sections":[],"benefits":[]}'),
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
STAGES = [
    {'nome': 'Briefing', 'peso_percentual': '0', 'administrativa': True},
    {'nome': 'Rough Mix', 'peso_percentual': '20', 'prazo_dias': 3, 'unidade': 'faixa'},
    {'nome': 'Mixagem', 'peso_percentual': '50', 'prazo_dias': 5, 'depende_da_anterior': True, 'revisoes_incluidas': 2},
    {'nome': 'Masterização', 'peso_percentual': '30', 'prazo_dias': 2, 'depende_da_anterior': True},
]
'''


class ServicoEtapasTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + textwrap.dedent(source))

    def test_replace_validate_order_and_audit(self):
        self.run_case(r'''
        assert client.get('/servicos/1/etapas', headers=bearer('admin')).json() == []
        assert client.get('/servicos/1/etapas', headers=bearer('producer')).status_code == 403
        assert client.put('/servicos/1/etapas', headers=bearer('producer'), json={'etapas': STAGES}).status_code == 403

        saved = client.put('/servicos/1/etapas', headers=bearer('admin'), json={'etapas': STAGES})
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert [(item['ordem'], item['nome'], item['peso_percentual']) for item in body] == [
            (1, 'Briefing', '0.00'), (2, 'Rough Mix', '20.00'), (3, 'Mixagem', '50.00'), (4, 'Masterização', '30.00'),
        ]
        assert body[2]['revisoes_incluidas'] == 2 and body[2]['depende_da_anterior'] is True

        for payload, message in (
            ({'etapas': STAGES[1:3]}, 'A soma dos pesos deve ser 100%'),
            ({'etapas': [dict(STAGES[1], peso_percentual='100', depende_da_anterior=True)]}, 'A primeira etapa'),
            ({'etapas': [dict(STAGES[1], peso_percentual='100'), {'nome': 'Extra', 'peso_percentual': '0'}]}, 'Somente etapas administrativas'),
            ({'etapas': [dict(STAGES[1], peso_percentual='50'), dict(STAGES[1], nome='rough mix', peso_percentual='50')]}, 'nomes repetidos'),
            ({'etapas': [dict(STAGES[1], peso_percentual='100', extra=1)]}, 'Campo invalido'),
        ):
            response = client.put('/servicos/1/etapas', headers=bearer('admin'), json=payload)
            assert response.status_code == 422 and message in response.json()['detail'], (payload, response.text)

        # A rejected payload never changes the saved list.
        assert len(client.get('/servicos/1/etapas', headers=bearer('admin')).json()) == 4

        reordered = client.put('/servicos/1/etapas', headers=bearer('admin'), json={'etapas': [
            dict(STAGES[1], peso_percentual='40'), dict(STAGES[3], peso_percentual='60', depende_da_anterior=False),
        ]})
        assert reordered.status_code == 200, reordered.text
        assert [(item['ordem'], item['nome']) for item in reordered.json()] == [(1, 'Rough Mix'), (2, 'Masterização')]
        assert client.put('/servicos/1/etapas', headers=bearer('admin'), json={'etapas': []}).json() == []
        assert client.put('/servicos/9/etapas', headers=bearer('admin'), json={'etapas': []}).status_code == 404

        with Session(engine) as db:
            assert db.query(ServicoEtapaModel).count() == 0
            audits = db.query(AuditLogModel).order_by(AuditLogModel.id).all()
            assert [entry.metadata_json for entry in audits] == [
                {'old_stage_count': 0, 'new_stage_count': 4},
                {'old_stage_count': 4, 'new_stage_count': 2},
                {'old_stage_count': 2, 'new_stage_count': 0},
            ]
        ''')

    def test_deleting_service_removes_its_stages(self):
        self.run_case(r'''
        assert client.put('/servicos/1/etapas', headers=bearer('admin'), json={'etapas': STAGES}).status_code == 200
        assert client.delete('/servicos/1', headers=bearer('admin')).status_code == 200
        with Session(engine) as db:
            assert db.query(ServicoEtapaModel).count() == 0
        ''')


if __name__ == "__main__":
    unittest.main()
