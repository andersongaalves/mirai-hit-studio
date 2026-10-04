"""Portfolio A/B uploads and landing eligibility in a disposable database."""

import textwrap
import unittest

import httpx
import test_bootstrap_database as isolated
from services.portfolio_audio_storage import SupabasePortfolioAudioStorage

SETUP = """
import asyncio
from unittest.mock import patch
from sqlalchemy.orm import Session
from models import ConfigModel, UsuarioModel
from core.security import create_access_token, get_password_hash
bootstrap(engine)
with Session(engine) as db:
    db.add(ConfigModel(id=1, portfolio_segments_json=[{
        'id': 'rock', 'label': 'Rock', 'active': True, 'order': 1, 'retired': False,
    }]))
    db.add(UsuarioModel(username='admin', password_hash=get_password_hash('password-test'), is_admin=True, role='admin'))
    db.commit()
import main
import httpx
headers = {'Authorization': 'Bearer ' + create_access_token({'sub': 'admin'})}
base_payload = {
    'titulo': 'Mix test', 'artista': 'Synthetic Artist', 'categoria': 'Mixagem',
    'link_audio': 'https://example.invalid/release',
    'link_capa': 'https://example.invalid/cover.webp',
    'descricao': 'Synthetic portfolio fixture', 'destaque': False,
    'vertical': 'artists', 'segmentos_json': ['rock'], 'case_type': 'demo',
    'show_mix_comparison_on_landing': False, 'landing_order': None,
}
class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.deleted = []
        self.counter = 0
    def save(self, data, project_id, slot):
        self.counter += 1
        key = f'projects/{project_id}/{slot}-' + format(self.counter, '032x') + '.mp3'
        assert key not in self.objects and '@' not in key and 'Synthetic' not in key
        self.objects[key] = data
        return key
    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)
    def public_url(self, key):
        return 'https://project.supabase.co/storage/v1/object/public/portfolio-audio/' + key
storage = MemoryStorage()
"""


class PortfolioMixComparisonTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + textwrap.dedent(source))

    def test_upload_highlight_order_public_payload_and_remove(self):
        self.run_case("""
            async def check():
                transport = httpx.ASGITransport(app=main.app)
                with patch('routers.projetos.new_portfolio_audio_storage', return_value=storage):
                    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                        created = await client.post('/projetos', json=base_payload, headers=headers)
                        assert created.status_code == 200, created.text
                        project_id = created.json()['id']
                        assert created.json()['audio_before_url'] is None

                        before = await client.post(
                            f'/projetos/{project_id}/audio/before', headers=headers,
                            files={'audio': ('client-name.mp3', b'ID3before', 'audio/mpeg')},
                        )
                        assert before.status_code == 200, before.text
                        assert before.json()['audio_before_url'].endswith('.mp3')
                        attempted = {**base_payload, 'show_mix_comparison_on_landing': True, 'landing_order': 1}
                        missing_after = await client.put(f'/projetos/{project_id}', json=attempted, headers=headers)
                        assert missing_after.status_code == 409

                        after = await client.post(
                            f'/projetos/{project_id}/audio/after', headers=headers,
                            files={'audio': ('other.mp3', b'ID3after', 'audio/mpeg')},
                        )
                        assert after.status_code == 200, after.text
                        highlighted = await client.put(f'/projetos/{project_id}', json=attempted, headers=headers)
                        assert highlighted.status_code == 200, highlighted.text
                        assert highlighted.json()['landing_order'] == 1

                        title_only = await client.put(
                            f'/projetos/{project_id}', json={'titulo': 'Mix test editado'}, headers=headers)
                        assert title_only.status_code == 200, title_only.text
                        assert title_only.json()['show_mix_comparison_on_landing'] is True
                        assert title_only.json()['landing_order'] == 1
                        assert title_only.json()['audio_before_url'].endswith('.mp3')
                        assert title_only.json()['audio_after_url'].endswith('.mp3')

                        public = await client.get('/projetos/public/mix-comparisons')
                        assert public.status_code == 200, public.text
                        assert [item['id'] for item in public.json()] == [project_id]
                        assert set(public.json()[0]) == {
                            'id', 'titulo', 'artista', 'link_capa', 'link_audio',
                            'audio_before_url', 'audio_after_url', 'landing_order'}
                        assert not any('key' in field for field in public.json()[0])

                        removed = await client.delete(f'/projetos/{project_id}/audio/before', headers=headers)
                        assert removed.status_code == 200, removed.text
                        assert removed.json()['show_mix_comparison_on_landing'] is False
                        assert removed.json()['landing_order'] is None
                        assert (await client.get('/projetos/public/mix-comparisons')).json() == []
            asyncio.run(check())
        """)

    def test_limit_reordering_replacement_and_validation(self):
        self.run_case("""
            async def check():
                transport = httpx.ASGITransport(app=main.app)
                with patch('routers.projetos.new_portfolio_audio_storage', return_value=storage):
                    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                        ids = []
                        for number in range(5):
                            payload = {**base_payload, 'titulo': f'Mix test {number}'}
                            created = await client.post('/projetos', json=payload, headers=headers)
                            project_id = created.json()['id']
                            ids.append(project_id)
                            for slot in ('before', 'after'):
                                response = await client.post(
                                    f'/projetos/{project_id}/audio/{slot}', headers=headers,
                                    files={'audio': ('ignored.mp3', b'ID3synthetic', 'audio/mpeg')},
                                )
                                assert response.status_code == 200, response.text
                            enabled = {**payload, 'show_mix_comparison_on_landing': True, 'landing_order': min(number + 1, 4)}
                            response = await client.put(f'/projetos/{project_id}', json=enabled, headers=headers)
                            assert response.status_code == (200 if number < 4 else 409), response.text

                        moved = {**base_payload, 'titulo': 'Mix test 1', 'show_mix_comparison_on_landing': True, 'landing_order': 1}
                        assert (await client.put(f'/projetos/{ids[1]}', json=moved, headers=headers)).status_code == 200
                        public = (await client.get('/projetos/public/mix-comparisons')).json()
                        assert [item['id'] for item in public][:2] == [ids[1], ids[0]]
                        assert [item['landing_order'] for item in public] == [1, 2, 3, 4]

                        old_before = next(key for key in storage.objects if key.startswith(f'projects/{ids[0]}/before-'))
                        replaced = await client.post(
                            f'/projetos/{ids[0]}/audio/before', headers=headers,
                            files={'audio': ('replacement.mp3', b'ID3replacement', 'audio/mpeg')},
                        )
                        assert replaced.status_code == 200
                        assert old_before in storage.deleted and old_before not in storage.objects

                        invalid = await client.post(
                            f'/projetos/{ids[0]}/audio/after', headers=headers,
                            files={'audio': ('fake.mp3', b'not-audio', 'audio/mpeg')},
                        )
                        assert invalid.status_code == 422
                        wrong_mime = await client.post(
                            f'/projetos/{ids[0]}/audio/after', headers=headers,
                            files={'audio': ('fake.txt', b'ID3fake', 'text/plain')},
                        )
                        assert wrong_mime.status_code == 422
                        with patch('routers.projetos.max_audio_bytes', return_value=4):
                            too_large = await client.post(
                                f'/projetos/{ids[0]}/audio/after', headers=headers,
                                files={'audio': ('large.mp3', b'ID3too-large', 'audio/mpeg')},
                            )
                        assert too_large.status_code == 413
            asyncio.run(check())
        """)

    def test_storage_failure_preserves_old_reference(self):
        self.run_case("""
            class FailingStorage(MemoryStorage):
                def save(self, data, project_id, slot):
                    from services.portfolio_audio_storage import PortfolioAudioStorageError
                    raise PortfolioAudioStorageError('synthetic sanitized failure')
            async def check():
                transport = httpx.ASGITransport(app=main.app)
                async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
                    created = await client.post('/projetos', json=base_payload, headers=headers)
                    project_id = created.json()['id']
                    with patch('routers.projetos.new_portfolio_audio_storage', return_value=FailingStorage()):
                        failed = await client.post(
                            f'/projetos/{project_id}/audio/before', headers=headers,
                            files={'audio': ('test.mp3', b'ID3test', 'audio/mpeg')},
                        )
                        assert failed.status_code == 503
                    admin = await client.get('/projetos/admin', headers=headers)
                    assert admin.json()[0]['audio_before_url'] is None
            asyncio.run(check())
        """)

    def test_postgres_path_uses_transaction_advisory_lock(self):
        from unittest.mock import Mock

        from services.portfolio_service import lock_mix_comparisons

        db = Mock()
        db.get_bind.return_value.dialect.name = "postgresql"
        lock_mix_comparisons(db)
        statement = str(db.execute.call_args.args[0])
        self.assertIn("pg_advisory_xact_lock", statement)

    def test_migration_downgrade_and_upgrade_on_disposable_database(self):
        self.run_case("""
            from alembic import command
            from alembic.script import ScriptDirectory
            config = migration_config()
            head = ScriptDirectory.from_config(config).get_current_head()
            command.downgrade(config, 'a7d4e9c2b610')
            columns = {column['name'] for column in inspect(engine).get_columns('projetos')}
            assert 'audio_before_key' not in columns
            command.upgrade(config, 'head')
            columns = {column['name'] for column in inspect(engine).get_columns('projetos')}
            assert {'audio_before_key', 'audio_after_key', 'show_mix_comparison_on_landing', 'landing_order'} <= columns
            assert ScriptDirectory.from_config(config).get_current_head() == head
        """)


class PortfolioAudioStorageTests(unittest.TestCase):
    def test_provider_400_not_found_creates_public_bucket(self):
        state = {"exists": False}

        def handler(request):
            if request.method == "GET":
                if state["exists"]:
                    return httpx.Response(200, json={"public": True})
                return httpx.Response(400, json={"statusCode": "404", "error": "Bucket not found"})
            if request.method == "POST" and request.url.path.endswith("/bucket"):
                payload = request.read().decode()
                self.assertIn('"public":true', payload.replace(" ", ""))
                self.assertIn("audio/mpeg", payload)
                state["exists"] = True
                return httpx.Response(200)
            return httpx.Response(404)

        storage = SupabasePortfolioAudioStorage(
            base_url="https://project.supabase.co",
            service_key="server-only-secret",
            bucket="portfolio-audio",
            transport=httpx.MockTransport(handler),
        )
        storage._ensure_public_bucket()
        self.assertTrue(state["exists"])

    def test_public_bucket_upload_delete_and_opaque_key(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.method == "GET" and request.url.path.endswith("/bucket/portfolio-audio"):
                return httpx.Response(200, json={"public": True})
            if request.method == "POST" and "/object/portfolio-audio/" in request.url.path:
                self.assertEqual(request.headers["x-upsert"], "false")
                self.assertEqual(request.headers["content-type"], "audio/mpeg")
                return httpx.Response(200)
            if request.method == "DELETE" and "/object/portfolio-audio/" in request.url.path:
                return httpx.Response(200)
            return httpx.Response(404)

        storage = SupabasePortfolioAudioStorage(
            base_url="https://project.supabase.co",
            service_key="server-only-secret",
            bucket="portfolio-audio",
            transport=httpx.MockTransport(handler),
        )
        key = storage.save(b"ID3synthetic", 27, "before")
        self.assertRegex(key, r"^projects/27/before-[a-f0-9]{32}\.mp3$")
        self.assertNotIn("@", key)
        self.assertNotIn("client", key)
        self.assertEqual(
            storage.public_url(key),
            "https://project.supabase.co/storage/v1/object/public/portfolio-audio/" + key,
        )
        storage.delete(key)
        self.assertTrue(all("server-only-secret" not in str(request.url) for request in requests))


if __name__ == "__main__":
    unittest.main()
