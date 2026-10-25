"""Admin infrastructure usage: each provider block fails on its own and never leaks credentials."""
import unittest

import test_bootstrap_database as isolated

SETUP = r'''
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models import UsuarioModel
from routers.uso_infra import router
from services import uso_infra_service as uso

bootstrap(engine)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True),
        UsuarioModel(id=2, username='producer', password_hash='unused', role='produtor', is_admin=False, ativo=True),
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

class Reply:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status
    def json(self):
        return self.payload
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError('synthetic', request=None, response=None)
'''


class UsoInfraTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_admin_only_blocks_are_independent_and_secret_free(self):
        self.run_case(r'''
import os
os.environ['CLOUDFLARE_API_TOKEN'] = 'cf-secret-token'
os.environ['CLOUDFLARE_ACCOUNT_ID'] = 'account-1'
os.environ['CLOUDFLARE_ZONE_ID'] = 'zone-1'
uso.settings.CLOUDINARY_CLOUD_NAME = 'demo'
uso.settings.CLOUDINARY_API_KEY = 'cl-key'
uso.settings.CLOUDINARY_API_SECRET = 'cl-secret-value'

def fake_get(url, **kwargs):
    assert kwargs.get('auth') == ('cl-key', 'cl-secret-value')
    return Reply({'plan': 'Free', 'credits': {'usage': 3.5, 'limit': 25},
                  'storage': {'usage': 1048576}, 'bandwidth': {'usage': 2048}})

def fake_post(url, json=None, headers=None, **kwargs):
    assert headers['Authorization'] == 'Bearer cf-secret-token'
    if 'r2StorageAdaptiveGroups' in json['query']:
        return Reply({'data': {'viewer': {'accounts': [{'r2StorageAdaptiveGroups': [
            {'max': {'objectCount': 4, 'payloadSize': 1000, 'metadataSize': 24}, 'dimensions': {'bucketName': 'final', 'datetime': '2026-10-25T10:00:00Z'}},
            {'max': {'objectCount': 3, 'payloadSize': 900, 'metadataSize': 20}, 'dimensions': {'bucketName': 'final', 'datetime': '2026-10-24T10:00:00Z'}},
        ]}]}}})
    return Reply({'errors': [{'message': 'not authorized'}]})

with patch.object(uso.httpx, 'get', side_effect=fake_get), patch.object(uso.httpx, 'post', side_effect=fake_post), \
        patch.object(uso.recursos, 'memoria', return_value={'usada_bytes': 300, 'limite_bytes': 512}):
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get('/admin/uso')).status_code == 401
            assert (await client.get('/admin/uso', headers=bearer('producer', 2))).status_code == 403
            response = await client.get('/admin/uso?atualizar=true', headers=bearer('admin', 1))
            assert response.status_code == 200, response.text
            return response
    response = asyncio.run(check())

body = response.text
for secret in ('cf-secret-token', 'cl-secret-value', 'cl-key'):
    assert secret not in body
blocks = {block['nome']: block for block in response.json()['blocos']}
assert blocks['Servidor (Render)']['itens'][0]['usado'] == 300
assert blocks['Supabase']['status'] == 'nao_configurado'  # SQLite harness
assert blocks['Cloudinary']['itens'][0] == {'rotulo': 'Créditos do mês', 'usado': 3.5, 'limite': 25, 'unidade': 'creditos'}
cloudflare = blocks['Cloudflare']
assert cloudflare['status'] == 'ok' and cloudflare['itens'][0]['usado'] == 1024  # latest R2 sample per bucket
assert any('Tráfego do site indisponível' in aviso for aviso in cloudflare['avisos'])

uso._cache.update(at=0.0, data=None)
os.environ.pop('CLOUDFLARE_API_TOKEN')
with patch.object(uso.httpx, 'get', side_effect=RuntimeError('down')):
    data = uso.carregar(SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='sqlite'))), atualizar=True)
statuses = {block['nome']: block['status'] for block in data['blocos']}
assert statuses['Cloudinary'] == 'indisponivel' and statuses['Cloudflare'] == 'nao_configurado', statuses
assert uso.carregar(None) is data  # cached for five minutes
''')


if __name__ == "__main__":
    unittest.main()
