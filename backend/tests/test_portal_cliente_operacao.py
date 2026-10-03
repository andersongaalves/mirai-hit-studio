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


if __name__ == "__main__":
    unittest.main()
