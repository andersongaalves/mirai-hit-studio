"""Portfolio segment catalog contracts in a disposable application database."""

import textwrap
import unittest

import test_bootstrap_database as isolated

SETUP = """
import asyncio
from sqlalchemy.orm import Session
from core.security import create_access_token, get_password_hash
from models import ConfigModel, ProjetoModel, UsuarioModel
bootstrap(engine)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(username='admin', password_hash=get_password_hash('password-test'), is_admin=True, role='admin'),
        UsuarioModel(username='producer', password_hash=get_password_hash('password-test'), is_admin=False, role='produtor'),
        ConfigModel(id=1, desconto=13.0, val_extra_duracao=.2,
            portfolio_segments_json=[
                {'id':'rock','label':'Rock','active':True,'order':1,'retired':False},
            ]),
        ProjetoModel(titulo='Historico', artista='Mirai', categoria='Mixagem',
            link_audio='https://example.invalid/history.mp3',
            link_capa='https://example.invalid/history.webp', descricao='Fixture',
            vertical='artists', segmentos_json=['legacy_mix'], case_type='demo'),
        ProjetoModel(titulo='Rock atual', artista='Mirai', categoria='Mixagem',
            link_audio='https://example.invalid/rock.mp3',
            link_capa='https://example.invalid/rock.webp', descricao='Fixture',
            vertical='artists', segmentos_json=['rock'], case_type='demo'),
    ])
    db.commit()
import main
import httpx
admin = {'Authorization':'Bearer ' + create_access_token({'sub':'admin', 'av':0})}
producer = {'Authorization':'Bearer ' + create_access_token({'sub':'producer', 'av':0})}
"""


class PortfolioSegmentCatalogTests(unittest.TestCase):
    def test_catalog_mutations_history_permissions_and_project_validation(self):
        isolated.BootstrapTests().run_case(
            SETUP
            + textwrap.dedent("""
            async def check():
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=main.app), base_url='http://test'
                ) as client:
                    assert (await client.get('/config/portfolio-segments')).status_code == 401
                    assert (await client.get('/config/portfolio-segments', headers=producer)).status_code == 403
                    numeric_before = (await client.get('/config')).json()

                    catalog = (await client.get('/config/portfolio-segments', headers=admin)).json()
                    by_id = {item['id']: item for item in catalog['segments']}
                    assert by_id['rock']['active'] is True and by_id['rock']['usage_count'] == 1
                    assert by_id['legacy_mix']['active'] is False
                    assert by_id['legacy_mix']['usage_count'] == 1
                    first_revision = catalog['revision']

                    created = await client.post('/config/portfolio-segments', headers=admin, json={
                        'label':'Brazilian Phonk', 'expected_revision':first_revision})
                    assert created.status_code == 200, created.text
                    catalog = created.json()
                    assert catalog['segments'][-1]['id'] == 'brazilian_phonk'

                    stale = await client.post('/config/portfolio-segments', headers=admin, json={
                        'label':'Trap', 'expected_revision':first_revision})
                    assert stale.status_code == 409
                    duplicate = await client.post('/config/portfolio-segments', headers=admin, json={
                        'label':'Brazilian-Phonk', 'expected_revision':catalog['revision']})
                    assert duplicate.status_code == 409

                    renamed = await client.patch(
                        '/config/portfolio-segments/brazilian_phonk', headers=admin,
                        json={'label':'Brazilian Phonk / Games', 'expected_revision':catalog['revision']})
                    assert renamed.status_code == 200, renamed.text
                    catalog = renamed.json()
                    assert next(item for item in catalog['segments'] if item['id'] == 'brazilian_phonk')['label'] == 'Brazilian Phonk / Games'

                    disabled = await client.patch(
                        '/config/portfolio-segments/rock', headers=admin,
                        json={'active':False, 'expected_revision':catalog['revision']})
                    catalog = disabled.json()
                    projects = (await client.get('/projetos/admin', headers=admin)).json()
                    rock_project = next(item for item in projects if item['titulo'] == 'Rock atual')
                    same_segments = await client.put(
                        f"/projetos/{rock_project['id']}", headers=admin,
                        json={'titulo':'Rock atualizado', 'segmentos_json':['rock']})
                    assert same_segments.status_code == 200, same_segments.text
                    rejected = await client.post('/projetos', headers=admin, json={
                        'titulo':'Novo rock','artista':'Mirai','categoria':'Mixagem',
                        'link_audio':'https://example.invalid/new.mp3',
                        'link_capa':'https://example.invalid/new.webp','descricao':'Fixture',
                        'vertical':'artists','segmentos_json':['rock'],'case_type':'demo'})
                    assert rejected.status_code == 422
                    unknown = await client.put(
                        f"/projetos/{rock_project['id']}", headers=admin,
                        json={'segmentos_json':['rock','unknown_segment']})
                    assert unknown.status_code == 422

                    enabled = await client.patch(
                        '/config/portfolio-segments/brazilian_phonk', headers=admin,
                        json={'active':True, 'expected_revision':catalog['revision']})
                    catalog = enabled.json()
                    accepted = await client.post('/projetos', headers=admin, json={
                        'titulo':'Phonk novo','artista':'Mirai','categoria':'Producao',
                        'link_audio':'https://example.invalid/phonk.mp3',
                        'link_capa':'https://example.invalid/phonk.webp','descricao':'Fixture',
                        'vertical':'artists','segmentos_json':['brazilian_phonk'],'case_type':'demo'})
                    assert accepted.status_code == 200, accepted.text

                    ordered_ids = [item['id'] for item in reversed(catalog['segments'])]
                    reordered = await client.put('/config/portfolio-segments/order', headers=admin, json={
                        'segment_ids':ordered_ids, 'expected_revision':catalog['revision']})
                    assert reordered.status_code == 200, reordered.text
                    catalog = reordered.json()
                    assert [item['id'] for item in catalog['segments']] == ordered_ids

                    unused = await client.post('/config/portfolio-segments', headers=admin, json={
                        'label':'Unused Segment', 'expected_revision':catalog['revision']})
                    assert unused.status_code == 200, unused.text
                    catalog = unused.json()
                    retired = await client.request(
                        'DELETE', '/config/portfolio-segments/unused_segment', headers=admin,
                        json={'expected_revision':catalog['revision']})
                    assert retired.status_code == 200, retired.text
                    catalog = retired.json()
                    assert 'unused_segment' not in {item['id'] for item in catalog['segments']}
                    reused = await client.post('/config/portfolio-segments', headers=admin, json={
                        'label':'Unused Segment', 'expected_revision':catalog['revision']})
                    assert reused.status_code == 409
                    used_delete = await client.request(
                        'DELETE', '/config/portfolio-segments/rock', headers=admin,
                        json={'expected_revision':catalog['revision']})
                    assert used_delete.status_code == 409

                    public = (await client.get('/config/portfolio-segments/public')).json()
                    assert {'rock','legacy_mix','brazilian_phonk'} <= {item['id'] for item in public}
                    assert (await client.get('/config')).json() == numeric_before
            asyncio.run(check())
        """)
        )

    def test_migration_backfills_and_preserves_project_segments(self):
        isolated.BootstrapTests().run_case(
            textwrap.dedent("""
            from alembic import command
            import json
            bootstrap(engine)
            config = migration_config()
            command.downgrade(config, '24ef7f883a03')
            with engine.begin() as connection:
                connection.exec_driver_sql('INSERT INTO configuracoes (id) VALUES (1)')
                connection.exec_driver_sql('''
                    INSERT INTO projetos
                        (titulo, artista, categoria, link_audio, link_capa, descricao,
                         destaque, segmentos_json, show_mix_comparison_on_landing)
                    VALUES
                        ('Legacy', 'Mirai', 'Mix', 'https://example.invalid/a.mp3',
                         'https://example.invalid/a.webp', 'Fixture', 0,
                         '["legacy_mix", "trap"]', 0)
                ''')
            command.upgrade(config, 'head')
            with engine.connect() as connection:
                raw = connection.exec_driver_sql(
                    'SELECT portfolio_segments_json FROM configuracoes WHERE id=1').scalar_one()
                catalog = json.loads(raw) if isinstance(raw, str) else raw
                assert [item['id'] for item in catalog] == ['legacy_mix', 'trap']
                original = connection.exec_driver_sql(
                    'SELECT segmentos_json FROM projetos WHERE titulo="Legacy"').scalar_one()
            command.downgrade(config, '24ef7f883a03')
            with engine.connect() as connection:
                assert connection.exec_driver_sql(
                    'SELECT segmentos_json FROM projetos WHERE titulo="Legacy"').scalar_one() == original
            command.upgrade(config, 'head')
            assert 'portfolio_segments_json' in {
                column['name'] for column in inspect(engine).get_columns('configuracoes')}
        """)
        )
