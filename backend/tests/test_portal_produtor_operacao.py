"""Producer files and payouts with synthetic identities and Storage."""

import unittest

import httpx
import test_bootstrap_database as isolated

from services.producao_arquivo_storage import SupabaseProducaoArquivoStorage

SETUP = r'''
import asyncio
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy.orm import Session

from core.security import create_access_token
from database import get_db
from models import (
    AuditLogModel, ClienteModel, OrcamentoModel, ProducaoArquivoModel,
    ProducaoModel, RepasseProdutorModel, UsuarioModel,
)
from routers.portal_operacao_admin import router as admin_operation_router
from routers.portal_produtor import router as producer_router
from services import producao_arquivo_service
from services.producao_arquivo_storage import ProducaoArquivoStorageError

bootstrap(engine)
with Session(engine) as db:
    admin = UsuarioModel(id=1, username='admin', password_hash='unused', role='admin', is_admin=True, ativo=True)
    producer_a = UsuarioModel(id=2, username='producer-a', password_hash='unused', role='produtor', is_admin=False, ativo=True)
    producer_b = UsuarioModel(id=3, username='producer-b', password_hash='unused', role='produtor', is_admin=False, ativo=True)
    client_a = ClienteModel(id=1, nome='Cliente A', email='a@example.test')
    client_b = ClienteModel(id=2, nome='Cliente B', email='b@example.test')
    db.add_all([admin, producer_a, producer_b, client_a, client_b])
    db.flush()
    budget_a = OrcamentoModel(id=1, nome_cliente='Cliente A', email='a@example.test', servico='Mixagem', cliente_id=1, produtor_id=2)
    budget_b = OrcamentoModel(id=2, nome_cliente='Cliente B', email='b@example.test', servico='Masterizacao', cliente_id=2, produtor_id=3)
    db.add_all([budget_a, budget_b])
    db.flush()
    db.add_all([
        ProducaoModel(id=1, titulo='Faixa A', cliente='Cliente A', servico='Mixagem', produtor_id=2, orcamento_id=1, etapas='[]'),
        ProducaoModel(id=2, titulo='Faixa B', cliente='Cliente B', servico='Masterizacao', produtor_id=3, orcamento_id=2, etapas='[]'),
    ])
    db.commit()

app = FastAPI()
app.include_router(producer_router)
app.include_router(admin_operation_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
def bearer(username):
    return {'Authorization': 'Bearer ' + create_access_token({'sub': username})}

class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.deleted = []
        self.counter = 0
    def save(self, data, mime_type):
        self.counter += 1
        key = f'arquivos/{self.counter:032x}/{(self.counter + 100):032x}'
        self.objects[key] = data
        return key
    def read(self, key):
        if key not in self.objects:
            raise ProducaoArquivoStorageError('missing')
        return self.objects[key]
    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)
'''


class StorageAdapterTests(unittest.TestCase):
    def test_private_bucket_immutable_object_and_server_auth(self):
        requests = []

        def handler(request):
            requests.append(request)
            if request.method == "GET" and "/bucket/" in request.url.path:
                return httpx.Response(200, json={"public": False})
            if request.method == "POST" and "/object/" in request.url.path:
                return httpx.Response(200, json={"Key": "stored"})
            if request.method == "GET" and "/object/authenticated/" in request.url.path:
                return httpx.Response(200, content=b"private-audio")
            if request.method == "DELETE":
                return httpx.Response(200, json=[])
            return httpx.Response(404)

        storage = SupabaseProducaoArquivoStorage(
            base_url="https://project.supabase.co",
            service_key="synthetic-secret",
            bucket="producao-arquivos",
            transport=httpx.MockTransport(handler),
        )
        key = storage.save(b"ID3-private", "audio/mpeg")
        self.assertRegex(key, r"^arquivos/[a-f0-9]{32}/[a-f0-9]{32}$")
        self.assertEqual(storage.read(key), b"private-audio")
        storage.delete(key)
        upload = next(item for item in requests if item.method == "POST")
        self.assertEqual(upload.headers["x-upsert"], "false")
        self.assertIn("authorization", upload.headers)
        self.assertNotIn("Cliente", key)


class PortalProducerOperationTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_private_files_ownership_versions_and_safe_projection(self):
        self.run_case(r'''
async def check():
    storage = MemoryStorage()
    with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            uploaded = await client.post(
                '/producoes/1/arquivos',
                headers=bearer('admin'),
                data={'tipo':'material', 'visivel_produtor':'true', 'visivel_cliente':'false'},
                files={'arquivo':('guia.pdf', b'%PDF-private', 'application/pdf')},
            )
            assert uploaded.status_code == 201, uploaded.text
            material = uploaded.json()
            assert 'object_key' not in material
            assert material['visivel_produtor'] is True

            own = await client.get('/portal/produtor/producoes/1/arquivos', headers=bearer('producer-a'))
            other = await client.get('/portal/produtor/producoes/1/arquivos', headers=bearer('producer-b'))
            assert own.status_code == 200 and len(own.json()) == 1
            assert other.status_code == 404

            download = await client.get(f"/portal/produtor/arquivos/{material['id']}/conteudo", headers=bearer('producer-a'))
            denied = await client.get(f"/portal/produtor/arquivos/{material['id']}/conteudo", headers=bearer('producer-b'))
            assert download.status_code == 200 and download.content == b'%PDF-private'
            assert denied.status_code == 404

            preview = await client.post(
                '/portal/produtor/producoes/1/arquivos',
                headers=bearer('producer-a'),
                data={'tipo':'previa'},
                files={'arquivo':('preview.mp3', b'ID3-preview-v1', 'audio/mpeg')},
            )
            assert preview.status_code == 201, preview.text
            first = preview.json()
            assert first['versao'] == 1 and first['visivel_cliente'] is False

            invalid_type = await client.post(
                '/portal/produtor/producoes/1/arquivos',
                headers=bearer('producer-a'),
                data={'tipo':'material'},
                files={'arquivo':('material.pdf', b'%PDF-x', 'application/pdf')},
            )
            alien_upload = await client.post(
                '/portal/produtor/producoes/1/arquivos',
                headers=bearer('producer-b'),
                data={'tipo':'previa'},
                files={'arquivo':('alien.mp3', b'ID3-alien', 'audio/mpeg')},
            )
            assert invalid_type.status_code == 422
            assert alien_upload.status_code == 404

            replacement = await client.post(
                '/portal/produtor/producoes/1/arquivos',
                headers=bearer('producer-a'),
                data={'tipo':'previa', 'substitui_arquivo_id':str(first['id'])},
                files={'arquivo':('preview-v2.mp3', b'ID3-preview-v2', 'audio/mpeg')},
            )
            assert replacement.status_code == 201, replacement.text
            second = replacement.json()
            assert second['versao'] == 2
            assert second['grupo_versao'] == first['grupo_versao']
            assert second['substitui_arquivo_id'] == first['id']
            assert len(storage.objects) == 3

            duplicate_replacement = await client.post(
                '/portal/produtor/producoes/1/arquivos',
                headers=bearer('producer-a'),
                data={'tipo':'previa', 'substitui_arquivo_id':str(first['id'])},
                files={'arquivo':('preview-v3.mp3', b'ID3-preview-v3', 'audio/mpeg')},
            )
            assert duplicate_replacement.status_code == 409
            assert len(storage.objects) == 3

            listed = await client.get('/producoes/1/arquivos', headers=bearer('admin'))
            assert listed.status_code == 200 and len(listed.json()) == 3
            assert all('object_key' not in item for item in listed.json())

            with Session(engine) as db:
                rows = db.query(ProducaoArquivoModel).all()
                assert len({row.object_key for row in rows}) == 3
                assert all('Cliente' not in row.object_key for row in rows)
                assert db.query(AuditLogModel).filter_by(action='production.file_uploaded').count() == 3
asyncio.run(check())
''')

    def test_storage_failure_and_database_compensation(self):
        self.run_case(r'''
class FailingStorage(MemoryStorage):
    def save(self, data, mime_type):
        raise ProducaoArquivoStorageError('storage unavailable')

async def check():
    failing = FailingStorage()
    with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=failing):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post(
                '/producoes/1/arquivos', headers=bearer('admin'), data={'tipo':'material'},
                files={'arquivo':('guide.pdf', b'%PDF-fail', 'application/pdf')})
            assert response.status_code == 503
    with Session(engine) as db:
        assert db.query(ProducaoArquivoModel).count() == 0

    storage = MemoryStorage()
    with Session(engine) as db:
        production = db.get(ProducaoModel, 1)
        actor = db.get(UsuarioModel, 1)
        try:
            with patch.object(producao_arquivo_service.audit_service, 'record', side_effect=RuntimeError('synthetic db failure')):
                producao_arquivo_service.upload(
                    db, production=production, actor=actor, file_type='material',
                    filename='guide.pdf', mime_type='application/pdf', data=b'%PDF-data',
                    visible_to_producer=True, visible_to_client=False, storage=storage)
        except RuntimeError:
            pass
        else:
            raise AssertionError('database failure hidden')
        assert db.query(ProducaoArquivoModel).count() == 0
        assert len(storage.deleted) == 1 and not storage.objects
asyncio.run(check())
''')

    def test_payout_snapshot_admin_mutations_and_receipt_access(self):
        self.run_case(r'''
async def check():
    storage = MemoryStorage()
    with patch.object(producao_arquivo_service, 'new_production_file_storage', return_value=storage):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            created = await client.put(
                '/producoes/1/repasse', headers=bearer('admin'),
                json={'valor_combinado':'100.00'})
            assert created.status_code == 200, created.text
            payout = created.json()
            assert payout['produtor_id'] == 2 and payout['status'] == 'definido'

            blocked = await client.put(
                '/producoes/1/repasse', headers=bearer('producer-a'),
                json={'valor_combinado':'999.00'})
            assert blocked.status_code == 403
            own = await client.get('/portal/produtor/repasses', headers=bearer('producer-a'))
            other = await client.get('/portal/produtor/repasses', headers=bearer('producer-b'))
            assert len(own.json()) == 1 and other.json() == []

            with Session(engine) as db:
                production = db.get(ProducaoModel, 1)
                production.produtor_id = 3
                db.commit()

            own_after = await client.get('/portal/produtor/repasses', headers=bearer('producer-a'))
            new_owner = await client.get('/portal/produtor/repasses', headers=bearer('producer-b'))
            assert len(own_after.json()) == 1 and new_owner.json() == []
            assert (await client.get('/portal/produtor/producoes/1', headers=bearer('producer-a'))).status_code == 404

            early_payment = await client.post(
                '/producoes/1/repasse/pagar', headers=bearer('admin'), json={})
            assert early_payment.status_code == 409
            released = await client.post('/producoes/1/repasse/liberar', headers=bearer('admin'))
            assert released.status_code == 200 and released.json()['status'] == 'liberado'

            receipt = await client.post(
                '/producoes/1/arquivos', headers=bearer('admin'),
                data={'tipo':'comprovante'},
                files={'arquivo':('comprovante.pdf', b'%PDF-receipt', 'application/pdf')})
            assert receipt.status_code == 201, receipt.text
            receipt_id = receipt.json()['id']
            paid = await client.post(
                '/producoes/1/repasse/pagar', headers=bearer('admin'),
                json={'referencia_pagamento':'PIX-REF-SINTETICA', 'comprovante_arquivo_id':receipt_id})
            assert paid.status_code == 200, paid.text
            assert paid.json()['status'] == 'pago' and paid.json()['comprovante_arquivo_id'] == receipt_id

            proof = await client.get(
                f"/portal/produtor/repasses/{payout['id']}/comprovante",
                headers=bearer('producer-a'))
            alien_proof = await client.get(
                f"/portal/produtor/repasses/{payout['id']}/comprovante",
                headers=bearer('producer-b'))
            assert proof.status_code == 200 and proof.content == b'%PDF-receipt'
            assert alien_proof.status_code == 404

            corrected = await client.patch(
                '/producoes/1/repasse/correcao', headers=bearer('admin'),
                json={'valor_combinado':'120.00', 'referencia_pagamento':'PIX-REF-CORRIGIDA'})
            assert corrected.status_code == 200, corrected.text
            assert corrected.json()['valor_combinado'] == '120.00'
            assert corrected.json()['produtor_id'] == 2

            with Session(engine) as db:
                stored = db.query(RepasseProdutorModel).one()
                assert stored.produtor_id == 2 and str(stored.valor_combinado) == '120.00'
                correction = db.query(AuditLogModel).filter_by(action='producer_payout.corrected').one()
                assert correction.metadata_json['old_amount'] == '100.00'
                assert correction.metadata_json['new_amount'] == '120.00'
                assert correction.metadata_json['reference_changed'] is True
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
