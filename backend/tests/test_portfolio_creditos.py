"""Roadmap 3.0, 5.19: producer credits on portfolio projects."""

import textwrap
import unittest

import test_bootstrap_database as isolated

SETUP = """
import asyncio
from unittest.mock import patch
from sqlalchemy.orm import Session
from models import ConfigModel, ProjetoCreditoModel, ProjetoModel, UsuarioModel
from core.security import create_access_token, get_password_hash
bootstrap(engine)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(id=1, username='admin', password_hash=get_password_hash('password-test'), is_admin=True, role='admin'),
        UsuarioModel(id=2, username='beatmaker', password_hash='unused', is_admin=False, role='produtor', ativo=True),
        UsuarioModel(id=3, username='antigo', password_hash='unused', is_admin=False, role='produtor', ativo=False),
    ])
    db.add(ConfigModel(id=1, portfolio_segments_json=[
        {'id':'rock','label':'Rock','active':True,'order':1,'retired':False},
    ]))
    db.commit()
import main
import httpx
headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'admin', 'av': 0})}
PAYLOAD = {
    'titulo': 'Melhor Sad', 'artista': 'Yonda', 'categoria': 'Mixagem',
    'link_audio': 'https://example.com/a.mp3', 'link_capa': 'https://example.com/a.webp',
    'descricao': 'Case', 'destaque': False, 'vertical': 'artists', 'segmentos_json': ['rock'],
    'case_type': 'client_case',
}
"""


class PortfolioCreditosTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + textwrap.dedent(source))

    def test_credits_crud_order_public_view_and_validation(self):
        self.run_case("""
            async def check():
                transport = httpx.ASGITransport(app=main.app)
                with patch('socket.socket.connect', side_effect=AssertionError('external network')):
                    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                        creditos = [
                            {'funcao': 'mixagem', 'nome': '  Beat   Maker ', 'usuario_id': 2},
                            {'funcao': 'composicao', 'nome': 'Fulana Externa'},
                            {'funcao': 'outra', 'funcao_outra': 'Direcao vocal', 'nome': 'Ciclano'},
                        ]
                        created = await client.post('/projetos', json={**PAYLOAD, 'creditos': creditos},
                                                    headers=headers)
                        assert created.status_code == 200, created.text
                        project = created.json()
                        assert project['creditos'] == [
                            {'funcao': 'mixagem', 'funcao_outra': None, 'nome': 'beatmaker', 'usuario_id': 2},
                            {'funcao': 'composicao', 'funcao_outra': None, 'nome': 'Fulana Externa', 'usuario_id': None},
                            {'funcao': 'outra', 'funcao_outra': 'Direcao vocal', 'nome': 'Ciclano', 'usuario_id': None},
                        ]

                        # Public list: name and role only, never the account link.
                        public = (await client.get('/projetos')).json()
                        assert public[0]['creditos'] == [
                            {'funcao': 'mixagem', 'funcao_outra': None, 'nome': 'beatmaker'},
                            {'funcao': 'composicao', 'funcao_outra': None, 'nome': 'Fulana Externa'},
                            {'funcao': 'outra', 'funcao_outra': 'Direcao vocal', 'nome': 'Ciclano'},
                        ]
                        assert all('usuario_id' not in item for item in public[0]['creditos'])

                        # Editing other fields keeps credits; a new list replaces them in the new order.
                        path = f"/projetos/{project['id']}"
                        kept = await client.put(path, json={'titulo': 'Melhor Sad (remix)'}, headers=headers)
                        assert kept.status_code == 200 and len(kept.json()['creditos']) == 3, kept.text
                        reordered = await client.put(path, json={'creditos': [creditos[2], creditos[0]]},
                                                     headers=headers)
                        assert reordered.status_code == 200, reordered.text
                        assert [item['nome'] for item in reordered.json()['creditos']] == ['Ciclano', 'beatmaker']
                        with Session(engine) as db:
                            rows = db.query(ProjetoCreditoModel).order_by(ProjetoCreditoModel.ordem).all()
                            assert [(row.ordem, row.nome) for row in rows] == [(1, 'Ciclano'), (2, 'beatmaker')]

                        # Validation: fixed roles, other role text, names, linked accounts and limits.
                        bad_lists = [
                            [{'funcao': 'dj', 'nome': 'X'}],
                            [{'funcao': 'outra', 'nome': 'X'}],
                            [{'funcao': 'beat', 'nome': '   '}],
                            [{'funcao': 'beat', 'nome': 'X', 'extra': 1}],
                            [{'funcao': 'beat', 'nome': 'X'}] * 21,
                        ]
                        for bad in bad_lists:
                            response = await client.put(path, json={'creditos': bad}, headers=headers)
                            assert response.status_code == 422, (bad, response.text)
                        assert (await client.put(path, json={'creditos': None}, headers=headers)).status_code == 422
                        for usuario_id in (3, 1, 999):  # inactive producer, admin, missing
                            response = await client.put(
                                path, json={'creditos': [{'funcao': 'beat', 'nome': 'X', 'usuario_id': usuario_id}]},
                                headers=headers)
                            assert response.status_code == 422, (usuario_id, response.text)
                        unchanged = (await client.get('/projetos/admin', headers=headers)).json()[0]
                        assert [item['nome'] for item in unchanged['creditos']] == ['Ciclano', 'beatmaker']

                        # Role text is dropped for fixed roles; empty list clears credits.
                        normalized = await client.put(path, json={'creditos': [
                            {'funcao': 'beat', 'funcao_outra': 'ignorado', 'nome': 'Solo'}]}, headers=headers)
                        assert normalized.json()['creditos'] == [
                            {'funcao': 'beat', 'funcao_outra': None, 'nome': 'Solo', 'usuario_id': None}]
                        cleared = await client.put(path, json={'creditos': []}, headers=headers)
                        assert cleared.status_code == 200 and cleared.json()['creditos'] == []

                        # Only the admin edits credits.
                        assert (await client.put(path, json={'creditos': []})).status_code == 401

                        # Deleting the project removes its credits.
                        await client.put(path, json={'creditos': [creditos[0]]}, headers=headers)
                        assert (await client.delete(path, headers=headers)).status_code in (200, 204)
                        with Session(engine) as db:
                            assert db.query(ProjetoCreditoModel).count() == 0
            asyncio.run(check())
        """)

    def test_display_name_is_independent_and_feeds_credits(self):
        self.run_case("""
            async def check():
                transport = httpx.ASGITransport(app=main.app)
                with patch('socket.socket.connect', side_effect=AssertionError('external network')):
                    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                        # Display name is optional, trimmed, limited and separate from the login.
                        created = await client.post('/usuarios', headers=headers, json={
                            'username': 'novo-produtor', 'password': 'senha-segura-1', 'role': 'produtor',
                            'nome_exibicao': '  Novo   Produtor  '})
                        assert created.status_code in (200, 201), created.text
                        assert created.json()['nome_exibicao'] == 'Novo Produtor'
                        assert created.json()['username'] == 'novo-produtor'
                        too_long = await client.patch('/usuarios/2', headers=headers, json={'nome_exibicao': 'x' * 81})
                        assert too_long.status_code == 422

                        project = (await client.post('/projetos', headers=headers, json={**PAYLOAD, 'creditos': [
                            {'funcao': 'mixagem', 'nome': 'beatmaker', 'usuario_id': 2},
                            {'funcao': 'beat', 'nome': 'Externo'}]})).json()

                        renamed = await client.patch('/usuarios/2', headers=headers, json={'nome_exibicao': 'DJ Beat'})
                        assert renamed.status_code == 200, renamed.text
                        assert renamed.json()['nome_exibicao'] == 'DJ Beat' and renamed.json()['username'] == 'beatmaker'
                        public = (await client.get('/projetos')).json()[0]['creditos']
                        assert [item['nome'] for item in public] == ['DJ Beat', 'Externo']
                        admin = (await client.get('/projetos/admin', headers=headers)).json()[0]['creditos']
                        assert admin[0] == {'funcao': 'mixagem', 'funcao_outra': None, 'nome': 'DJ Beat', 'usuario_id': 2}
                        with Session(engine) as db:
                            stored = db.query(ProjetoCreditoModel).order_by(ProjetoCreditoModel.ordem).all()
                            assert [row.nome for row in stored] == ['DJ Beat', 'Externo']  # Fallback kept current.

                        # Saving with a linked producer always credits the account display name.
                        saved = await client.put(f"/projetos/{project['id']}", headers=headers, json={'creditos': [
                            {'funcao': 'producao', 'nome': 'qualquer coisa', 'usuario_id': 2}]})
                        assert saved.json()['creditos'][0]['nome'] == 'DJ Beat'

                        # Clearing the display name falls back to the username; login stays unchanged.
                        cleared = await client.patch('/usuarios/2', headers=headers, json={'nome_exibicao': '   '})
                        assert cleared.status_code == 200 and cleared.json()['nome_exibicao'] is None
                        assert (await client.get('/projetos')).json()[0]['creditos'][0]['nome'] == 'beatmaker'
                        listed = (await client.get('/usuarios/produtores', headers=headers)).json()
                        assert {item['username']: item['nome_exibicao'] for item in listed} == {
                            'beatmaker': None, 'novo-produtor': 'Novo Produtor'}
                        # With no display name, a linked account ignores a supplied alias.
                        saved = await client.put(f"/projetos/{project['id']}", headers=headers, json={'creditos': [
                            {'funcao': 'producao', 'nome': 'nome-nao-autoritativo', 'usuario_id': 2}]})
                        assert saved.status_code == 200 and saved.json()['creditos'][0]['nome'] == 'beatmaker'
                        login_change = await client.patch('/usuarios/2', headers=headers, json={'username': 'beatmaker-novo'})
                        assert login_change.status_code == 200, login_change.text
                        assert (await client.get('/projetos')).json()[0]['creditos'][0]['nome'] == 'beatmaker-novo'
                        with Session(engine) as db:
                            assert db.query(ProjetoCreditoModel).filter_by(usuario_id=2).one().nome == 'beatmaker-novo'
            asyncio.run(check())
        """)

    def test_additive_migration_roundtrip(self):
        isolated.BootstrapTests().run_case('''
from alembic import command
from sqlalchemy import inspect
assert bootstrap(engine) == 'b3d5f7a9c014'
assert 'projeto_creditos' in inspect(engine).get_table_names()
command.downgrade(migration_config(), 'f3b5d7a9c124')
assert 'projeto_creditos' not in inspect(engine).get_table_names()
assert 'projetos' in inspect(engine).get_table_names()
command.upgrade(migration_config(), 'a2c4e6f8b135')
assert 'projeto_creditos' in inspect(engine).get_table_names()
''')


if __name__ == "__main__":
    unittest.main()
