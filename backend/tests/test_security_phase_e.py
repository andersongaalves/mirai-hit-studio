"""Security contracts in disposable databases; no settings or external services."""
import unittest
import test_bootstrap_database as isolated

SETUP = '''
import os, tempfile, asyncio
from pathlib import Path
from sqlalchemy.orm import Session
from models import UsuarioModel, ConfigModel, OrcamentoModel
from core.security import create_access_token, create_refresh_token, decode_token, get_password_hash
from jose import jwt
from datetime import datetime, timezone
bootstrap(engine)
with Session(engine) as db:
    db.add_all([UsuarioModel(username='admin', password_hash=get_password_hash('password-test'), is_admin=True, role='admin'),
                UsuarioModel(username='common', password_hash='unused', is_admin=False, role='produtor')])
    db.add(ConfigModel(id=1))
    db.add(OrcamentoModel(id=1, nome_cliente='Teste', email='test@example.com', servico='Mix', valor_total=0))
    db.commit()
os.environ['RATE_LIMIT_DB'] = str(Path(config.settings.BACKUP_FOLDER) / 'limits.db')
import main
import httpx
def bearer(name):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': name})}
'''


class SecurityTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_tokens_and_permissions(self):
        self.run_case('''
async def check():
    with patch('socket.socket.connect', side_effect=AssertionError('external network')):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            assert (await client.get('/auth/me', headers=bearer('admin'))).json()['username'] == 'admin'
            valid = {'sub': 'admin', 'exp': int(datetime.now(timezone.utc).timestamp()) + 300, 'type': 'access'}
            cases = [('', None), ('bad', None), (create_refresh_token({'sub': 'admin'}), None),
                     (create_access_token({'sub': 'missing'}), None)]
            for payload in [{**valid, 'exp': 1}, {k:v for k,v in valid.items() if k != 'sub'},
                            {k:v for k,v in valid.items() if k != 'exp'}, {**valid, 'sub': ' '},
                            {**valid, 'type': 'other'}, {**valid, 'exp': None}]:
                cases.append((jwt.encode(payload, 'test-only', algorithm='HS256'), None))
            cases.append((jwt.encode(valid, 'wrong-key', algorithm='HS256'), None))
            for token, _ in cases:
                response = await client.get('/auth/me', headers={'Authorization': 'Bearer ' + token} if token else {})
                assert response.status_code == 401, response.text
            assert not decode_token(create_access_token({'sub': 'admin'}), 'refresh')
            assert decode_token(create_refresh_token({'sub': 'admin'}), 'refresh')['sub'] == 'admin'
            for url in ['/usuarios', '/orcamentos', '/producoes', '/propostas/999']:
                assert (await client.get(url)).status_code == 401, url
            assert (await client.get('/usuarios', headers=bearer('common'))).status_code == 200
            for method, url in [('put', '/config'), ('post', '/servicos'), ('post', '/projetos')]:
                assert (await client.request(method, url, json={})).status_code == 401
                assert (await client.request(method, url, json={}, headers=bearer('common'))).status_code == 403
                assert (await client.request(method, url, json={}, headers=bearer('admin'))).status_code == 422
            for url in ['/servicos', '/projetos']:
                assert (await client.get(url)).status_code == 200
            cfg = (await client.get('/config')).json()
            for discount in [0, -1, 101]:
                cfg['desconto'] = discount
                assert (await client.put('/config', json=cfg, headers=bearer('admin'))).status_code == 200
                assert (await client.get('/config')).json()['desconto'] == discount
            assert (await client.patch('/orcamentos/1/produtor', json={'produtor_id':999}, headers=bearer('common'))).status_code == 422
            result = await client.post('/auth/login', json={'username':'admin', 'password':'password-test'})
            assert result.status_code == 200, result.text
            assert decode_token(result.json()['access_token'])['sub'] == 'admin'
            with Session(engine) as db:
                user = db.query(UsuarioModel).filter_by(username='common').one()
                user.is_admin = True
                db.commit()
            assert (await client.put('/config', json={}, headers=bearer('common'))).status_code == 403
asyncio.run(check())
''')

    def test_limits_headers_cors_errors(self):
        self.run_case('''
from core.rate_limit import allow_request
from core.http_security import cors_origins
assert allow_request('boundary', 2, 60, now=100) == (True, 0)
assert allow_request('boundary', 2, 60, now=101) == (True, 0)
assert allow_request('boundary', 2, 60, now=102) == (False, 58)
assert allow_request('boundary', 2, 60, now=160) == (True, 0)
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(lambda _: allow_request('concurrent', 5, 60, now=200)[0], range(20)))
assert sum(results) == 5
for origin in ['*', 'https://*.example.com', 'https://example.com/path', 'javascript:alert(1)']:
    try: cors_origins(origin)
    except ValueError: pass
    else: raise AssertionError(origin)
async def check():
    with patch('socket.socket.connect', side_effect=AssertionError('external network')):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            for n in range(10):
                response = await client.post('/auth/login', json={'username':'admin','password':'credential-sentinel'*20})
                assert response.status_code == 422, response.text
                assert 'credential-sentinel' not in response.text
            response = await client.post('/auth/login', json={})
            assert response.status_code == 429 and int(response.headers['retry-after']) > 0
            for endpoint in ['/orcamentos', '/newsletter']:
                for n in range(5): assert (await client.post(endpoint, json={})).status_code == 422
                assert (await client.post(endpoint, json={})).status_code == 429
            response = await client.get('/health')
            assert response.status_code == 200 and response.headers['x-content-type-options'] == 'nosniff'
            assert response.headers['x-frame-options'] == 'DENY'
            assert 'strict-transport-security' not in response.headers
            assert 'strict-transport-security' in (await client.get('https://test/health')).headers
            for origin, expected in [('http://localhost', 200), ('https://evil.invalid', 400)]:
                response = await client.options('/config', headers={'Origin':origin,'Access-Control-Request-Method':'PUT','Access-Control-Request-Headers':'Authorization, Content-Type'})
                assert response.status_code == expected
                assert (response.headers.get('access-control-allow-origin') == origin) == (expected == 200)
asyncio.run(check())
''')

    def test_validation_and_newsletter_idempotency(self):
        self.run_case('''
import json
from pydantic import ValidationError
from schemas.orcamento import OrcamentoCreate
from schemas.usuario import LoginRequest
from schemas.servico_estrutura import validar_estrutura
from schemas.proposta import PropostaUpdate
from schemas.config import ConfigResponse
from core.security import verify_password
budget = dict(nome_cliente='Teste', email='test@example.com', servico='Mix', valor_total=0)
assert OrcamentoCreate(**budget).valor_total == 0
for field, value in [('nome_cliente',' '), ('servico',''), ('email','bad'), ('valor_total',float('inf')),
                     ('valor_total',-1), ('link_guia','javascript:alert(1)'), ('detalhes','x'*20001)]:
    try: OrcamentoCreate(**{**budget, field:value})
    except ValidationError: pass
    else: raise AssertionError(field)
for value in ['[]', 'null', '{"sections":[{"items":[]}]}', '{"sections":[{"title":"x","items":[1]}]}', '{"unknown":1}']:
    try: validar_estrutura(value)
    except (ValueError, ValidationError): pass
    else: raise AssertionError(value)
validar_estrutura(json.dumps({'intro':'x','sections':[{'icon':'i','title':'x','items':['y']}],'benefits':['z']}))
for value in [{'status':'aceita'}, {'numero':'forged'}, {'itens':[{'descricao':'x','quantidade':0,'valor_unitario':1}]},
              {'pagamentos':[{'tipo':'integral','url':'data:text/html,test'}]}]:
    try: PropostaUpdate(**value)
    except ValidationError: pass
    else: raise AssertionError(value)
try: LoginRequest(username='x', password='a'*73)
except ValidationError: pass
else: raise AssertionError('long password accepted')
assert not verify_password('a'*73, 'unused')
try: LoginRequest(username='x', password='\u00e9'*37)
except ValidationError: pass
else: raise AssertionError('UTF-8 byte limit missing')
cfg = {name:0 for name in ConfigResponse.model_fields}
try: ConfigResponse(**{**cfg, 'desconto':float('nan')})
except ValidationError: pass
else: raise AssertionError('nonfinite config accepted')
async def check():
    with patch('socket.socket.connect', side_effect=AssertionError('external network')), patch('services.email_service.EmailService.enviar_boas_vindas') as send:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            a = await client.post('/newsletter', json={'email':'test@example.com'})
            b = await client.post('/newsletter', json={'email':'test@example.com'})
            assert a.status_code == b.status_code == 200 and a.json() == b.json(), (a.text,b.text)
            assert send.call_count == 1
asyncio.run(check())
''')


if __name__ == '__main__':
    unittest.main()
