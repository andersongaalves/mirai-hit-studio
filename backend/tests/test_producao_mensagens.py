"""Roadmap 3.0, 5.03: per-production message thread with replies and file links."""

import textwrap
import unittest

import test_bootstrap_database as isolated

SETUP = r'''
import os, tempfile
os.environ['RATE_LIMIT_DB'] = os.path.join(tempfile.mkdtemp(), 'limits.sqlite3')
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models import (
    ClienteModel, OrcamentoModel, ProducaoArquivoModel, ProducaoMensagemModel, ProducaoModel, UsuarioModel,
)
from routers.producao_mensagens import router

bootstrap(engine)
with Session(engine) as db:
    db.add_all([ClienteModel(id=1, nome='Cliente A', email='a@example.test'),
                ClienteModel(id=2, nome='Cliente B', email='b@example.test')])
    db.flush()
    db.add_all([
        UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=2, username='producer-a', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        UsuarioModel(id=3, username='producer-b', password_hash='unused', role='produtor', is_admin=False, ativo=True),
        UsuarioModel(id=4, username='client-a', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1),
        UsuarioModel(id=5, username='client-b', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=2),
    ])
    db.flush()
    db.add_all([
        OrcamentoModel(id=1, nome_cliente='Cliente A', email='a@example.test', servico='Mixagem', cliente_id=1, produtor_id=2),
        OrcamentoModel(id=2, nome_cliente='Cliente B', email='b@example.test', servico='Master', cliente_id=2, produtor_id=3),
    ])
    db.flush()
    db.add_all([
        ProducaoModel(id=1, titulo='Faixa A', cliente='Cliente A', servico='Mixagem', produtor_id=2, orcamento_id=1, etapas='[]'),
        ProducaoModel(id=2, titulo='Faixa B', cliente='Cliente B', servico='Master', produtor_id=3, orcamento_id=2, etapas='[]'),
    ])
    db.flush()
    def file(id, production, tipo, client, producer):
        return ProducaoArquivoModel(
            id=id, producao_id=production, remetente_usuario_id=1, tipo=tipo, nome_exibicao=f'{tipo}-{id}.wav',
            mime_type='audio/wav', tamanho_bytes=10, sha256='a' * 64, object_key=f'key-{id}',
            grupo_versao=f'group-{id}', versao=1, visivel_cliente=client, visivel_produtor=producer,
        )
    db.add_all([
        file(10, 1, 'previa', True, True),
        file(11, 1, 'referencia', False, True),
        file(12, 2, 'previa', True, True),
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


class ProducaoMensagensTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + textwrap.dedent(source))

    def test_thread_visibility_replies_files_and_ownership(self):
        self.run_case(r'''
        base_client = '/portal/cliente/producoes/1/mensagens'
        base_producer = '/portal/produtor/producoes/1/mensagens'
        base_admin = '/producoes/1/mensagens'

        first = client.post(base_client, headers=bearer('client-a'),
                            json={'texto': '  Pode subir o vocal?\r\n\x00 ', 'arquivo_id': 10})
        assert first.status_code == 201, first.text
        body = first.json()
        assert body['texto'] == 'Pode subir o vocal?'
        assert body['autor_papel'] == 'cliente' and body['audiencia'] == 'todos'
        assert body['arquivo'] == {'id': 10, 'nome_exibicao': 'previa-10.wav', 'tipo': 'previa', 'versao': 1}

        # Clients cannot create internal notes; the server forces "todos".
        forced = client.post(base_client, headers=bearer('client-a'), json={'texto': 'Obrigado', 'audiencia': 'equipe'})
        assert forced.status_code == 201 and forced.json()['audiencia'] == 'todos'

        internal = client.post(base_producer, headers=bearer('producer-a'),
                               json={'texto': 'Referencia interna', 'audiencia': 'equipe', 'arquivo_id': 11})
        assert internal.status_code == 201, internal.text
        reply = client.post(base_producer, headers=bearer('producer-a'),
                            json={'texto': 'Vocal +2 dB na v2.', 'responde_a_id': body['id']})
        assert reply.status_code == 201 and reply.json()['responde_a_id'] == body['id']
        admin_reply = client.post(base_admin, headers=bearer('admin'),
                                  json={'texto': 'Vamos revisar juntos.', 'audiencia': 'equipe', 'responde_a_id': internal.json()['id']})
        assert admin_reply.status_code == 201, admin_reply.text

        # Linking a file the client cannot see in a message to everyone is refused.
        hidden_file = client.post(base_producer, headers=bearer('producer-a'), json={'texto': 'Veja', 'arquivo_id': 11})
        assert hidden_file.status_code == 422
        # Files and replies from other productions or hidden from the author are not found.
        assert client.post(base_client, headers=bearer('client-a'), json={'texto': 'x', 'arquivo_id': 11}).status_code == 404
        assert client.post(base_client, headers=bearer('client-a'), json={'texto': 'x', 'arquivo_id': 12}).status_code == 404
        assert client.post(base_client, headers=bearer('client-a'),
                           json={'texto': 'x', 'responde_a_id': internal.json()['id']}).status_code == 404
        assert client.post(base_client, headers=bearer('client-a'), json={'texto': '   '}).status_code == 422
        assert client.post(base_client, headers=bearer('client-a'), json={'texto': 'x' * 2001}).status_code == 422
        assert client.post(base_client, headers=bearer('client-a'), json={'texto': 'x', 'extra': 1}).status_code == 422

        client_view = client.get(base_client, headers=bearer('client-a')).json()
        assert [item['texto'] for item in client_view] == ['Pode subir o vocal?', 'Obrigado', 'Vocal +2 dB na v2.']
        assert [item['enviado_por_mim'] for item in client_view] == [True, True, False]
        producer_view = client.get(base_producer, headers=bearer('producer-a')).json()
        assert len(producer_view) == 5
        assert producer_view[2]['arquivo']['id'] == 11 and producer_view[2]['audiencia'] == 'equipe'
        assert len(client.get(base_admin, headers=bearer('admin')).json()) == 5

        # Ownership: other client/producer get 404; roles are isolated.
        assert client.get(base_client, headers=bearer('client-b')).status_code == 404
        assert client.get(base_producer, headers=bearer('producer-b')).status_code == 404
        assert client.post(base_producer, headers=bearer('producer-b'), json={'texto': 'x'}).status_code == 404
        assert client.get(base_client, headers=bearer('producer-a')).status_code == 403
        assert client.get(base_admin, headers=bearer('producer-a')).status_code == 403
        assert client.get(base_client).status_code == 401
        assert client.get('/producoes/999/mensagens', headers=bearer('admin')).status_code == 404

        # A file later hidden from the client disappears from the client's view of the message.
        with Session(engine) as db:
            db.get(ProducaoArquivoModel, 10).visivel_cliente = False
            db.commit()
        assert client.get(base_client, headers=bearer('client-a')).json()[0]['arquivo'] is None
        with Session(engine) as db:
            assert db.query(ProducaoMensagemModel).count() == 5
        ''')

    def test_rate_limit_per_author(self):
        self.run_case(r'''
        for index in range(20):
            response = client.post('/portal/cliente/producoes/1/mensagens', headers=bearer('client-a'), json={'texto': f'm{index}'})
            assert response.status_code == 201, response.text
        limited = client.post('/portal/cliente/producoes/1/mensagens', headers=bearer('client-a'), json={'texto': 'excesso'})
        assert limited.status_code == 429 and 'Retry-After' in limited.headers
        assert client.post('/producoes/1/mensagens', headers=bearer('admin'), json={'texto': 'ok'}).status_code == 201
        ''')


if __name__ == "__main__":
    unittest.main()
