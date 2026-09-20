"""Portfolio taxonomy and public/admin visibility in a disposable database."""

import test_bootstrap_database as isolated
import textwrap
import unittest


SETUP = """
import asyncio
from unittest.mock import patch
from sqlalchemy.orm import Session
from models import ProjetoModel, UsuarioModel
from core.security import create_access_token, get_password_hash
bootstrap(engine)
with Session(engine) as db:
    db.add(UsuarioModel(username='admin', password_hash=get_password_hash('password-test'), is_admin=True, role='admin'))
    db.add(ProjetoModel(titulo='Legado', artista='Interno', categoria='Mixagem', link_audio='https://example.com/legacy.mp3', link_capa='https://example.com/legacy.webp', descricao='Nao classificado', destaque=False))
    db.commit()
import main
import httpx
headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'admin'})}
"""


class PortfolioTaxonomyTests(unittest.TestCase):
    def test_public_visibility_admin_backfill_and_validation(self):
        isolated.BootstrapTests().run_case(SETUP + textwrap.dedent("""
            async def check():
                transport = httpx.ASGITransport(app=main.app)
                with patch('socket.socket.connect', side_effect=AssertionError('external network')):
                    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                        assert (await client.get('/projetos')).json() == []
                        assert (await client.get('/projetos/admin')).status_code == 401
                        admin_list = await client.get('/projetos/admin', headers=headers)
                        assert admin_list.status_code == 200
                        assert admin_list.json()[0]['vertical'] is None
                        assert admin_list.json()[0]['segmentos_json'] == []

                        payload = {
                            'titulo': 'Demo sonora', 'artista': 'Mirai Hit Studio',
                            'categoria': 'Sound design',
                            'link_audio': 'https://example.com/demo.mp3',
                            'link_capa': 'https://example.com/demo.webp',
                            'descricao': 'Demonstracao identificada', 'destaque': True,
                            'vertical': 'media_games', 'segmentos_json': ['games', 'animation'],
                            'case_type': 'demo',
                        }
                        created = await client.post('/projetos', json=payload, headers=headers)
                        assert created.status_code == 200, created.text
                        assert created.json()['case_type'] == 'demo'
                        public = await client.get('/projetos')
                        assert public.status_code == 200
                        assert [item['titulo'] for item in public.json()] == ['Demo sonora']

                        for field, value in [
                            ('vertical', 'unknown'),
                            ('case_type', 'fake_client'),
                            ('segmentos_json', ['bad segment']),
                            ('segmentos_json', ['games', 'games']),
                        ]:
                            invalid = {**payload, field: value}
                            assert (await client.post('/projetos', json=invalid, headers=headers)).status_code == 422
            asyncio.run(check())
        """))
