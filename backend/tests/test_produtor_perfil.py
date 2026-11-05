"""Public producer pages: address, metrics, portfolio, beats and what the producer edits."""

import textwrap
import unittest

import test_bootstrap_database as isolated

SETUP = """
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from sqlalchemy.orm import Session
from core.security import create_access_token
from models import ProducaoModel, ProdutorPerfilModel, ProjetoCreditoModel, ProjetoModel, UsuarioModel, AuditLogModel
bootstrap(engine)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(id=2, username='ana-login', nome_exibicao='Ána Beats', password_hash='x', is_admin=False,
                     role='produtor', ativo=True, especialidades='beatmaker,mixagem', cpf='12345678909',
                     email='ana@example.com'),
        UsuarioModel(id=3, username='qa', password_hash='x', is_admin=False, role='produtor', ativo=True, is_test=True),
        UsuarioModel(id=4, username='bia', nome_exibicao='Bia', password_hash='x', is_admin=False, role='produtor', ativo=True),
        UsuarioModel(id=5, username='inativo', password_hash='x', is_admin=False, role='produtor', ativo=False),
    ])
    base = dict(categoria='Mixagem', link_audio='https://example.com/a.mp3', link_capa='https://example.com/a.webp',
                vertical='artists', segmentos_json=[], case_type='client_case')
    db.add_all([
        ProjetoModel(id=10, titulo='Hit', artista='Yonda', destaque=True, **base),
        ProjetoModel(id=11, titulo='Outro', artista='Fulano', **base),
        ProjetoModel(id=12, titulo='Rascunho', artista='X', **{**base, 'vertical': None}),
    ])
    db.flush()
    db.add_all([
        ProjetoCreditoModel(projeto_id=10, ordem=1, funcao='mixagem', nome='Ana', usuario_id=2),
        ProjetoCreditoModel(projeto_id=10, ordem=2, funcao='outra', funcao_outra='Direção vocal', nome='Ana', usuario_id=2),
        ProjetoCreditoModel(projeto_id=11, ordem=1, funcao='producao', nome='Ana', usuario_id=2),
        ProjetoCreditoModel(projeto_id=12, ordem=1, funcao='producao', nome='Ana', usuario_id=2),
        ProjetoCreditoModel(projeto_id=11, ordem=2, funcao='beat', nome='Bia', usuario_id=4),
    ])
    db.add_all([
        ProducaoModel(titulo='P1', cliente='C', servico='Mix', status='entregue', produtor_id=2),
        ProducaoModel(titulo='P2', cliente='C', servico='Mix', status='finalizado', produtor_id=2),
        ProducaoModel(titulo='P3', cliente='C', servico='Mix', status='em_andamento', produtor_id=2),
    ])
    db.commit()
import main
ana = {'Authorization': 'Bearer ' + create_access_token({'sub': 'ana-login', 'av': 0, 'uid': 2})}
bia = {'Authorization': 'Bearer ' + create_access_token({'sub': 'bia', 'av': 0, 'uid': 4})}
"""


class ProdutorPerfilTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + textwrap.dedent(source))

    def test_public_page_metrics_portfolio_and_privacy(self):
        self.run_case("""
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as api:
                # Every producer has an address from the start: name + id.
                page = await api.get('/produtores/ana-beats-2')
                assert page.status_code == 200, page.text
                data = page.json()
                assert data['slug'] == 'ana-beats-2' and data['nome'] == 'Ána Beats'
                assert data['especialidades'] == ['beatmaker', 'mixagem']
                assert data['metricas'] == {'portfolio': 2, 'mirai': 2, 'beats': 0, 'total': 4}, data['metricas']
                assert [item['titulo'] for item in data['portfolio']] == ['Hit', 'Outro']
                assert data['portfolio'][0]['funcoes'] == ['Mixagem', 'Direção vocal']
                assert data['beats'] == [] and data['aba_inicial'] == 'portfolio' and data['cor'] == '#00d5ed'
                assert page.headers['cache-control'] == 'public, max-age=60'
                # Nothing private leaks.
                text = page.text
                for secret in ('ana-login', 'ana@example.com', '12345678909'):
                    assert secret not in text, secret
                # Wrong names, test, inactive and unknown producers have no page.
                for slug in ('outro-nome-2', 'qa-3', 'inativo-5', 'ninguem', 'x-999999'):
                    assert (await api.get(f'/produtores/{slug}')).status_code == 404, slug
        asyncio.run(check())
        """)

    def test_producer_edits_page_address_links_and_images(self):
        self.run_case("""
        class FakeStorage:
            def __init__(self): self.saved, self.deleted = [], []
            def save(self, data, content_type):
                ref = f'memory://imgs/{len(self.saved) + 1}'
                self.saved.append(ref)
                return SimpleNamespace(reference=ref, public_url=f'https://img.example.com/{len(self.saved)}.webp')
            def get_public_url(self, ref): return 'https://img.example.com/x.webp'
            def delete(self, ref): self.deleted.append(ref)
        storage = FakeStorage()
        PNG = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a4a10000000049454e44ae426082')
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as api:
                assert (await api.get('/portal/produtor/perfil/pagina')).status_code == 401
                mine = (await api.get('/portal/produtor/perfil/pagina', headers=ana)).json()
                assert mine['slug'] == 'ana-beats-2' and mine['slug_padrao'] == 'ana-beats-2'
                assert '#cb32e6' in mine['cores'] and 'instagram' in mine['redes']
                saved = await api.put('/portal/produtor/perfil/pagina', headers=ana, json={
                    'slug': 'ana', 'headline': '  Beats   e mix  ', 'bio': 'Produtora de SP.\\nTrap e R&B.',
                    'cidade': 'São Paulo', 'cor': '#CB32E6', 'aba_inicial': 'beats',
                    'links': {'instagram': 'https://www.instagram.com/ana', 'site': 'https://ana.example.com', 'youtube': ''},
                })
                assert saved.status_code == 200, saved.text
                body = saved.json()
                assert body['slug'] == 'ana' and body['headline'] == 'Beats e mix' and body['cor'] == '#cb32e6'
                assert body['links'] == {'instagram': 'https://www.instagram.com/ana', 'site': 'https://ana.example.com'}
                # The chosen address and the original both open the page.
                assert (await api.get('/produtores/ana')).json()['aba_inicial'] == 'beats'
                assert (await api.get('/produtores/ana-beats-2')).json()['slug'] == 'ana'
                # Invalid input is refused.
                for payload in ({'slug': 'bia-4'}, {'slug': 'admin'}, {'slug': 'A B'}, {'slug': 'ab'},
                                {'cor': '#123456'}, {'aba_inicial': 'loja'}, {'links': {'instagram': 'http://instagram.com/x'}},
                                {'links': {'instagram': 'https://evil.example.com/ana'}}, {'links': {'myspace': 'https://myspace.com/a'}},
                                {'bio': 'x' * 1501}, {'outro': 1}):
                    response = await api.put('/portal/produtor/perfil/pagina', headers=ana, json=payload)
                    assert response.status_code == 422, (payload, response.text)
                # Two producers cannot share an address.
                taken = await api.put('/portal/produtor/perfil/pagina', headers=bia, json={'slug': 'ana'})
                assert taken.status_code == 422 and 'outro produtor' in taken.json()['detail']
                # Photo and cover: replacing one deletes the previous file.
                with patch('services.produtor_perfil_service.storage_for', return_value=storage):
                    files = {'arquivo': ('foto.png', PNG, 'image/png')}
                    first = await api.post('/portal/produtor/perfil/pagina/imagem/foto', headers=ana, files=files)
                    assert first.status_code == 200, first.text
                    second = await api.post('/portal/produtor/perfil/pagina/imagem/foto', headers=ana, files=files)
                    assert second.json()['foto_url'] == 'https://img.example.com/2.webp'
                    assert storage.deleted == ['memory://imgs/1']
                    bad = await api.post('/portal/produtor/perfil/pagina/imagem/capa', headers=ana,
                                         files={'arquivo': ('x.txt', b'not an image', 'text/plain')})
                    assert bad.status_code == 422, bad.text
                    assert (await api.post('/portal/produtor/perfil/pagina/imagem/outra', headers=ana, files=files)).status_code == 422
                    removed = await api.delete('/portal/produtor/perfil/pagina/imagem/foto', headers=ana)
                    assert removed.json()['foto_url'] is None and storage.deleted[-1] == 'memory://imgs/2'
            with Session(engine) as db:
                actions = {row.action for row in db.query(AuditLogModel).filter_by(entity_id='2')}
                assert {'producer.profile_updated', 'producer.profile_image_updated', 'producer.profile_image_removed'} <= actions
        asyncio.run(check())
        """)


if __name__ == "__main__":
    unittest.main()
