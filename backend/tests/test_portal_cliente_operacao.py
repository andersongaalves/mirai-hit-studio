"""Client portal files integrated with Admin and Producer ownership."""

import unittest

import test_bootstrap_database as isolated
from test_portal_produtor_operacao import SETUP as PRODUCER_SETUP

SETUP = PRODUCER_SETUP + r'''
from routers.portal_cliente import router as client_router

app.include_router(client_router)
with Session(engine) as db:
    db.add_all([
        UsuarioModel(id=4, username='client-a', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1),
        UsuarioModel(id=5, username='client-b', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=2),
    ])
    db.commit()
'''


class PortalClientOperationTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_files_versions_visibility_and_cross_portal_ownership(self):
        self.run_case(r'''
async def check():
    storage = MemoryStorage()
    with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            async def admin_upload(production_id, name, content, kind, client_visible):
                return await client.post(
                    f'/producoes/{production_id}/arquivos',
                    headers=bearer('admin'),
                    data={
                        'tipo': kind,
                        'visivel_produtor': 'true',
                        'visivel_cliente': str(client_visible).lower(),
                    },
                    files={'arquivo': (name, content, 'audio/mpeg')},
                )

            preview = await admin_upload(1, 'preview.mp3', b'preview-a', 'previa', True)
            internal = await admin_upload(1, 'internal.mp3', b'internal-a', 'referencia', False)
            team_material = await admin_upload(1, 'team-material.mp3', b'team-material', 'material', True)
            delivery = await admin_upload(1, 'delivery.mp3', b'delivery-a', 'entrega', True)
            other = await admin_upload(2, 'preview-b.mp3', b'preview-b', 'previa', True)
            proof = await admin_upload(1, 'receipt.mp3', b'private-receipt', 'comprovante', False)
            assert all(response.status_code == 201 for response in (preview, internal, team_material, delivery, other, proof))
            exposed_proof = await admin_upload(1, 'exposed-receipt.mp3', b'forbidden', 'comprovante', True)
            assert exposed_proof.status_code == 422

            unauthenticated = await client.get('/portal/cliente/producoes/1/arquivos')
            assert unauthenticated.status_code == 401
            listed = await client.get('/portal/cliente/producoes/1/arquivos', headers=bearer('client-a'))
            assert listed.status_code == 200, listed.text
            files = listed.json()
            assert {item['id'] for item in files} == {
                preview.json()['id'], team_material.json()['id'], delivery.json()['id'],
            }
            assert all('object_key' not in item and 'remetente_usuario_id' not in item for item in files)
            assert all('visivel_produtor' not in item and 'visivel_cliente' not in item for item in files)
            assert all(item['enviado_por_mim'] is False for item in files)

            alien = await client.get('/portal/cliente/producoes/1/arquivos', headers=bearer('client-b'))
            missing = await client.get('/portal/cliente/producoes/999/arquivos', headers=bearer('client-b'))
            assert alien.status_code == missing.status_code == 404
            assert alien.json() == missing.json()

            hidden = await client.get(
                f"/portal/cliente/arquivos/{internal.json()['id']}/conteudo",
                headers=bearer('client-a'),
            )
            cross_client = await client.get(
                f"/portal/cliente/arquivos/{other.json()['id']}/conteudo",
                headers=bearer('client-a'),
            )
            assert hidden.status_code == cross_client.status_code == 404
            assert (await client.patch(
                f"/producoes/1/arquivos/{proof.json()['id']}/visibilidade",
                headers=bearer('admin'),
                json={'visivel_produtor': True, 'visivel_cliente': True},
            )).status_code == 409

            playable = await client.get(
                f"/portal/cliente/arquivos/{preview.json()['id']}/conteudo",
                headers=bearer('client-a'),
            )
            assert playable.status_code == 200 and playable.content == b'preview-a'
            assert playable.headers['cache-control'] == 'private, no-store'
            final_file = await client.get(
                f"/portal/cliente/arquivos/{delivery.json()['id']}/conteudo",
                headers=bearer('client-a'),
            )
            assert final_file.status_code == 200 and final_file.content == b'delivery-a'

            material = await client.post(
                '/portal/cliente/producoes/1/arquivos',
                headers=bearer('client-a'),
                data={'tipo': 'material'},
                files={'arquivo': ('voice.wav', b'RIFF-client-a', 'audio/wav')},
            )
            assert material.status_code == 201, material.text
            assert material.json()['versao'] == 1 and material.json()['tipo'] == 'material'
            assert material.json()['enviado_por_mim'] is True
            assert 'object_key' not in material.json()

            second_version = await client.post(
                '/portal/cliente/producoes/1/arquivos',
                headers=bearer('client-a'),
                data={'tipo': 'material', 'substitui_arquivo_id': material.json()['id']},
                files={'arquivo': ('voice-v2.wav', b'RIFF-client-a-v2', 'audio/wav')},
            )
            assert second_version.status_code == 201
            assert second_version.json()['versao'] == 2
            assert second_version.json()['grupo_versao'] == material.json()['grupo_versao']

            replace_team_file = await client.post(
                '/portal/cliente/producoes/1/arquivos',
                headers=bearer('client-a'),
                data={'tipo': 'material', 'substitui_arquivo_id': team_material.json()['id']},
                files={'arquivo': ('forged.wav', b'RIFF-forged', 'audio/wav')},
            )
            assert replace_team_file.status_code == 404
            invalid_type = await client.post(
                '/portal/cliente/producoes/1/arquivos',
                headers=bearer('client-a'),
                data={'tipo': 'entrega'},
                files={'arquivo': ('forged.mp3', b'forged', 'audio/mpeg')},
            )
            assert invalid_type.status_code == 422

            producer_files = await client.get(
                '/portal/produtor/producoes/1/arquivos',
                headers=bearer('producer-a'),
            )
            assert producer_files.status_code == 200
            assert material.json()['id'] in {item['id'] for item in producer_files.json()}
            assert (await client.get(
                '/portal/produtor/producoes/1/arquivos',
                headers=bearer('producer-b'),
            )).status_code == 404

            assert (await client.get('/portal/produtor/repasses', headers=bearer('client-a'))).status_code == 403
            assert (await client.patch(
                f"/producoes/1/arquivos/{preview.json()['id']}/visibilidade",
                headers=bearer('client-a'),
                json={'visivel_produtor': True, 'visivel_cliente': True},
            )).status_code == 403

            with Session(engine) as db:
                db.get(ProducaoModel, 1).status = 'entregue'
                db.commit()
            closed = await client.post(
                '/portal/cliente/producoes/1/arquivos',
                headers=bearer('client-a'),
                data={'tipo': 'material'},
                files={'arquivo': ('late.wav', b'RIFF-late', 'audio/wav')},
            )
            assert closed.status_code == 409

asyncio.run(check())
''')

    def test_producer_preview_auto_visible_versions_and_admin_revocation(self):
        self.run_case(r'''
async def check():
    storage = MemoryStorage()
    with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            historical = await client.post(
                '/producoes/1/arquivos', headers=bearer('admin'),
                data={'tipo': 'previa', 'visivel_produtor': 'true', 'visivel_cliente': 'false'},
                files={'arquivo': ('historical.mp3', b'ID3-historical', 'audio/mpeg')},
            )
            assert historical.status_code == 201 and historical.json()['visivel_cliente'] is False
            first = await client.post(
                '/portal/produtor/producoes/1/arquivos', headers=bearer('producer-a'),
                data={'tipo': 'previa'},
                files={'arquivo': ('preview-v1.mp3', b'ID3-preview-v1', 'audio/mpeg')},
            )
            assert first.status_code == 201, first.text
            assert first.json()['visivel_cliente'] is True and first.json()['visivel_produtor'] is True

            delivery = await client.post(
                '/portal/produtor/producoes/1/arquivos', headers=bearer('producer-a'),
                data={'tipo': 'entrega'},
                files={'arquivo': ('delivery.mp3', b'ID3-delivery', 'audio/mpeg')},
            )
            assert delivery.status_code == 201 and delivery.json()['visivel_cliente'] is False
            client_files = await client.get('/portal/cliente/producoes/1/arquivos', headers=bearer('client-a'))
            assert {item['id'] for item in client_files.json()} == {first.json()['id']}
            playable = await client.get(
                f"/portal/cliente/arquivos/{first.json()['id']}/conteudo", headers=bearer('client-a'),
            )
            assert playable.status_code == 200 and playable.content == b'ID3-preview-v1'
            assert playable.headers['cache-control'] == 'private, no-store'
            for file_id in (historical.json()['id'], delivery.json()['id']):
                hidden = await client.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=bearer('client-a'))
                assert hidden.status_code == 404
            assert (await client.get(
                f"/portal/cliente/arquivos/{first.json()['id']}/conteudo", headers=bearer('client-b'),
            )).status_code == 404

            second = await client.post(
                '/portal/produtor/producoes/1/arquivos', headers=bearer('producer-a'),
                data={'tipo': 'previa', 'substitui_arquivo_id': str(first.json()['id'])},
                files={'arquivo': ('preview-v2.mp3', b'ID3-preview-v2', 'audio/mpeg')},
            )
            assert second.status_code == 201 and second.json()['versao'] == 2
            assert second.json()['grupo_versao'] == first.json()['grupo_versao']
            assert second.json()['visivel_cliente'] is True
            assert (await client.get(
                f"/portal/cliente/arquivos/{second.json()['id']}/conteudo", headers=bearer('client-a'),
            )).content == b'ID3-preview-v2'
            assert (await client.get(
                f"/portal/produtor/arquivos/{second.json()['id']}/conteudo", headers=bearer('producer-a'),
            )).status_code == 200
            assert (await client.get(
                f"/producoes/1/arquivos/{second.json()['id']}/conteudo", headers=bearer('admin'),
            )).status_code == 200

            revoked = await client.patch(
                f"/producoes/1/arquivos/{second.json()['id']}/visibilidade",
                headers=bearer('admin'),
                json={'visivel_produtor': True, 'visivel_cliente': False},
            )
            assert revoked.status_code == 200 and revoked.json()['visivel_cliente'] is False
            client_files = await client.get('/portal/cliente/producoes/1/arquivos', headers=bearer('client-a'))
            assert {item['id'] for item in client_files.json()} == {first.json()['id']}
            assert (await client.get(
                f"/portal/cliente/arquivos/{second.json()['id']}/conteudo", headers=bearer('client-a'),
            )).status_code == 404
            assert (await client.get(
                f"/portal/produtor/arquivos/{second.json()['id']}/conteudo", headers=bearer('producer-a'),
            )).status_code == 200
            with Session(engine) as db:
                assert db.query(AuditLogModel).filter_by(action='production.file_visibility_changed').count() == 1
                assert db.get(ProducaoArquivoModel, historical.json()['id']).visivel_cliente is False
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
