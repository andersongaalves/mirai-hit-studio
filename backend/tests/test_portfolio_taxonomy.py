"""Portfolio taxonomy and public/admin visibility in a disposable database."""

import textwrap
import unittest

import test_bootstrap_database as isolated

SETUP = """
import asyncio
from unittest.mock import patch
from sqlalchemy.orm import Session
from models import ConfigModel, ProjetoModel, UsuarioModel
from core.security import create_access_token, get_password_hash
bootstrap(engine)
with Session(engine) as db:
    db.add(UsuarioModel(username='admin', password_hash=get_password_hash('password-test'), is_admin=True, role='admin'))
    db.add(ConfigModel(id=1, portfolio_segments_json=[
        {'id':'rock','label':'Rock','active':True,'order':1,'retired':False},
        {'id':'pop','label':'Pop','active':True,'order':2,'retired':False},
        {'id':'games','label':'Games','active':True,'order':3,'retired':False},
        {'id':'animation','label':'Animation','active':True,'order':4,'retired':False},
    ]))
    db.add(ProjetoModel(titulo='Legado', artista='Interno', categoria='Mixagem', link_audio='https://example.com/legacy.mp3', link_capa='https://example.com/legacy.webp', descricao='Nao classificado', destaque=False))
    db.commit()
import main
import httpx
headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'admin', 'av': 0})}
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
                        legacy_id = admin_list.json()[0]['id']

                        title_only = await client.put(
                            f'/projetos/{legacy_id}', json={'titulo': 'Legado editado'}, headers=headers)
                        assert title_only.status_code == 200, title_only.text
                        assert title_only.json()['titulo'] == 'Legado editado'
                        assert title_only.json()['artista'] == 'Interno'
                        assert title_only.json()['vertical'] is None
                        assert title_only.json()['segmentos_json'] == []
                        assert title_only.json()['show_mix_comparison_on_landing'] is False

                        description_only = await client.put(
                            f'/projetos/{legacy_id}', json={'descricao': 'Descricao atualizada'}, headers=headers)
                        assert description_only.status_code == 200, description_only.text
                        assert description_only.json()['titulo'] == 'Legado editado'
                        assert description_only.json()['descricao'] == 'Descricao atualizada'

                        urls_only = await client.put(
                            f'/projetos/{legacy_id}',
                            json={
                                'link_audio': 'https://example.com/legacy-v2.mp3',
                                'link_capa': 'https://example.com/legacy-v2.webp',
                            },
                            headers=headers,
                        )
                        assert urls_only.status_code == 200, urls_only.text
                        assert urls_only.json()['link_audio'].endswith('legacy-v2.mp3')
                        assert urls_only.json()['link_capa'].endswith('legacy-v2.webp')

                        classification = await client.put(
                            f'/projetos/{legacy_id}',
                            json={
                                'categoria': 'Masterizacao',
                                'vertical': 'artists',
                                'segmentos_json': ['rock', 'pop'],
                                'case_type': 'client_case',
                            },
                            headers=headers,
                        )
                        assert classification.status_code == 200, classification.text
                        assert classification.json()['categoria'] == 'Masterizacao'
                        assert classification.json()['segmentos_json'] == ['rock', 'pop']

                        invalid = await client.put(
                            f'/projetos/{legacy_id}', json={'titulo': 'x'}, headers=headers)
                        assert invalid.status_code == 422
                        assert {tuple(item['loc']) for item in invalid.json()['detail']} == {('body', 'titulo')}

                        multiple_invalid = await client.put(
                            f'/projetos/{legacy_id}',
                            json={
                                'titulo': 'x',
                                'vertical': 'unknown',
                                'segmentos_json': ['bad segment'],
                            },
                            headers=headers,
                        )
                        assert multiple_invalid.status_code == 422
                        assert {item['loc'][-1] for item in multiple_invalid.json()['detail']} == {
                            'titulo', 'vertical', 'segmentos_json'}

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
                        assert {item['titulo'] for item in public.json()} == {
                            'Legado editado', 'Demo sonora'}

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
