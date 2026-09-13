"""HTTP/ASGI checks without network, production settings or external services."""
import unittest
import test_bootstrap_database as isolated
import test_proposta_service as persistence


class PropostaRouterTests(unittest.TestCase):
    def test_http_contract_and_isolation(self):
        isolated.BootstrapTests().run_case(persistence.SETUP + '''
import asyncio
import json
import time
from jose import jwt
from core.config import settings
from services.email_service import EmailService
from sqlalchemy.dialects import postgresql

class Recorder:
    def scalar(self, query):
        self.query = query
recorder = Recorder()
crud_proposta.bloquear_orcamento(recorder, 1)
assert 'FOR UPDATE' in str(recorder.query.compile(dialect=postgresql.dialect()))
crud_proposta.buscar_por_id(recorder, 1, bloquear=True)
assert 'FOR UPDATE' in str(recorder.query.compile(dialect=postgresql.dialect()))

async def check():
    with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')), \\
         patch.object(EmailService, 'enviar', side_effect=AssertionError('email forbidden')), \\
         patch.object(Base.metadata, 'create_all', side_effect=AssertionError('schema forbidden')):
        event.listen(engine, 'before_cursor_execute', reject_ddl)
        import main
        token = jwt.encode({'sub': 'test-admin', 'type': 'access', 'exp': int(time.time()) + 300},
                           settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        async def request(method, path, data=None, authenticated=True):
            body = json.dumps(data).encode() if data is not None else b''
            headers = [(b'content-type', b'application/json')]
            if authenticated:
                headers.append((b'authorization', f'Bearer {token}'.encode()))
            scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                     'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
                     'query_string': b'', 'root_path': '', 'headers': headers,
                     'client': ('127.0.0.1', 1234), 'server': ('test', 80)}
            messages = []
            async def receive():
                return {'type': 'http.request', 'body': body, 'more_body': False}
            async def send(message):
                messages.append(message)
            await main.app(scope, receive, send)
            status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
            content = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
            return status, json.loads(content) if content else None

        paths = [('POST', '/orcamentos/1/proposta'), ('GET', '/propostas/1'),
                 ('GET', '/propostas/orcamento/1'), ('PATCH', '/propostas/1')]
        for method, path in paths:
            status, _ = await request(method, path, {}, authenticated=False)
            assert status in (401, 403), (method, path, status)
        status, _ = await request('GET', '/propostas/orcamento/1')
        assert status == 404
        status, created = await request('POST', '/orcamentos/1/proposta', {})
        assert status == 200 and created['numero'] == 'MHS-000001'
        assert created['totais']['total'] == '150.25'
        assert created['cliente_snapshot']['cliente']['nome'] == 'Cliente Teste'
        assert not any(key.endswith('_json') for key in created)
        identifier = created['id']
        status, repeated = await request('POST', '/orcamentos/1/proposta')
        assert status == 200 and repeated == created
        for path in [f'/propostas/{identifier}', '/propostas/orcamento/1']:
            status, loaded = await request('GET', path)
            assert status == 200 and loaded == created
        for field in ['id', 'orcamento_id', 'numero', 'status', 'versao', 'cliente_snapshot',
                      'pdf_path', 'totais', 'created_at', 'updated_at', 'gerada_em', 'enviada_em', 'aprovada_em']:
            for method, path in [('POST', '/orcamentos/2/proposta'), ('PATCH', f'/propostas/{identifier}')]:
                status, _ = await request(method, path, {field: None})
                assert status == 422, (method, field, status)
        for payload in [{'itens': None}, {'itens': [{'descricao': 'A', 'quantidade': 0, 'valor_unitario': 1}]},
                        {'pagamentos': [{'tipo': 'integral', 'titulo': 'Pagamento', 'url': 'javascript:alert(1)'}]}]:
            status, _ = await request('PATCH', f'/propostas/{identifier}', payload)
            assert status == 422
        status, _ = await request('PATCH', f'/propostas/{identifier}', {'produtor_id': 999})
        assert status == 422
        status, edited = await request('PATCH', f'/propostas/{identifier}', {'descricao': 'Salvo via HTTP'})
        assert status == 200 and edited['versao'] == 2
        assert edited['cliente_snapshot'] == created['cliente_snapshot']
        status, loaded = await request('GET', f'/propostas/{identifier}')
        assert loaded['descricao'] == 'Salvo via HTTP'
        for method, path in [('GET', '/propostas/999'), ('PATCH', '/propostas/999'),
                             ('POST', '/orcamentos/999/proposta')]:
            status, _ = await request(method, path, {})
            assert status == 404
        status, _ = await request('GET', '/propostas/0')
        assert status == 422
        with Session(engine) as db:
            model = db.get(PropostaModel, identifier)
            model.status = 'enviada'
            db.commit()
        status, _ = await request('PATCH', f'/propostas/{identifier}', {'descricao': 'Forbidden'})
        assert status == 409
        with patch.object(crud_proposta, 'buscar_por_id', side_effect=SQLAlchemyError('credential-sentinel')):
            status, failure = await request('GET', f'/propostas/{identifier}')
            assert status == 503 and 'credential-sentinel' not in str(failure)
        with Session(engine) as db:
            assert db.scalar(select(func.count()).select_from(PropostaModel)) == 1
            assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 0
            assert db.get(OrcamentoModel, 1).detalhes == 'Pedido original'
        openapi = main.app.openapi()['paths']
        assert 'post' in openapi['/orcamentos/{orcamento_id}/proposta']
        assert 'patch' in openapi['/propostas/{proposta_id}']
        assert 'post' in openapi['/propostas/{proposta_id}/gerar-documento']
        assert 'post' in openapi['/propostas/{proposta_id}/aprovar']
asyncio.run(check())
''')


if __name__ == '__main__':
    unittest.main()
