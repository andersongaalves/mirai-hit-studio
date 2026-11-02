"""Admin file manager: folders, types, protection, download, delete and preview compression."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_portal_produtor import SETUP

EXTRA = r'''
from unittest.mock import patch
from sqlalchemy.orm import sessionmaker
from models import ProducaoArquivoModel, ProducaoMensagemModel
from routers.arquivos_admin import router as files_router
from services import arquivos_admin_service as manager
from services import producao_arquivo_service as files
app.include_router(files_router)

class MemoryStorage:
    def __init__(self):
        self.objects, self.deleted = {}, []
    def save(self, data, mime):
        from uuid import uuid4
        key = 'arquivos/' + uuid4().hex + '/' + uuid4().hex
        self.objects[key] = data
        return key
    def read(self, key):
        return self.objects[key]
    def delete(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)
storage = MemoryStorage()
session_factory = sessionmaker(bind=engine)

def send(name, data=b'ID3' + b'a' * 400, replaces=None, kind='previa', mime='audio/mpeg'):
    with Session(engine) as db:
        sent = files.upload(db, production=db.get(ProducaoModel, 1), actor=db.get(UsuarioModel, 2), file_type=kind,
            filename=name, mime_type=mime, data=data, visible_to_client=False, visible_to_producer=True,
            storage=storage, replaces_id=replaces)
        return sent.id, sent.object_key
'''


class ArquivosAdminTests(unittest.TestCase):
    def run_case(self, code):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + textwrap.dedent(code))

    def test_folders_types_protection_download_and_delete(self):
        self.run_case(r"""
            first, first_key = send('rough.mp3')
            second, second_key = send('rough-v2.mp3', replaces=first)
            attached, _ = send('anexo.mp3')
            pdf, _ = send('briefing.pdf', data=b'%PDF-1.4 synthetic', kind='material', mime='application/pdf')
            with Session(engine) as db:
                db.add(ProducaoMensagemModel(producao_id=1, autor_usuario_id=2, autor_papel='produtor', audiencia='todos',
                                             texto='Ouve esta', arquivo_id=attached))
                db.commit()
            async def check():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
                    admin = bearer('admin')
                    assert (await api.get('/admin/arquivos', headers=bearer('producer-a'))).status_code == 403
                    listing = (await api.get('/admin/arquivos', headers=admin)).json()
                    by_ref = {item['ref']: item for item in listing['arquivos']}
                    assert by_ref[f'arq:{second}']['pasta'] == ['Produções', '#1 Faixa A', 'Prévias']
                    assert by_ref[f'arq:{pdf}']['categoria'] == 'pdf' and by_ref[f'arq:{pdf}']['pasta'][-1] == 'Materiais'
                    assert by_ref[f'arq:{first}']['protegido'] and 'versão mais nova' in by_ref[f'arq:{first}']['motivo_protecao']
                    assert by_ref[f'arq:{attached}']['protegido'] and 'mensagem' in by_ref[f'arq:{attached}']['motivo_protecao']
                    assert not by_ref[f'arq:{second}']['protegido']
                    folders = {item['caminho']: item for item in listing['pastas']}
                    assert folders['Produções/#1 Faixa A']['arquivos'] == 4
                    assert listing['totais']['audio']['arquivos'] == 3 and listing['totais']['pdf']['arquivos'] == 1
                    only_pdf = (await api.get('/admin/arquivos', headers=admin, params={'categoria': 'pdf'})).json()['arquivos']
                    assert [item['ref'] for item in only_pdf] == [f'arq:{pdf}']
                    found = (await api.get('/admin/arquivos', headers=admin, params={'busca': 'briefing'})).json()['arquivos']
                    assert [item['ref'] for item in found] == [f'arq:{pdf}']
                    in_folder = (await api.get('/admin/arquivos', headers=admin, params={'pasta': 'Produções/#1 Faixa A/Materiais'})).json()['arquivos']
                    assert [item['ref'] for item in in_folder] == [f'arq:{pdf}']
                    with patch.object(files, 'new_production_file_storage', return_value=storage):
                        download = await api.get('/admin/arquivos/conteudo', headers=admin, params={'ref': f'arq:{pdf}'})
                        assert download.status_code == 200 and download.content == b'%PDF-1.4 synthetic'
                        assert "briefing.pdf" in download.headers['content-disposition']
                        # Protected files explain why and stay; deletion needs a reason.
                        kept = await api.request('DELETE', '/admin/arquivos', headers=admin, params={'ref': f'arq:{first}'}, json={'motivo': 'Limpeza'})
                        assert kept.status_code == 409 and 'versão mais nova' in kept.json()['detail']
                        assert (await api.request('DELETE', '/admin/arquivos', headers=admin, params={'ref': f'arq:{second}'}, json={'motivo': 'x'})).status_code == 422
                        removed = await api.request('DELETE', '/admin/arquivos', headers=admin, params={'ref': f'arq:{second}'}, json={'motivo': 'Enviado errado'})
                        assert removed.status_code == 204, removed.text
                    assert second_key in storage.deleted and second_key not in storage.objects
                    # The older version is the latest now, so it can go too.
                    listing = (await api.get('/admin/arquivos', headers=admin)).json()
                    assert not {item['ref']: item for item in listing['arquivos']}[f'arq:{first}']['protegido']
                    assert (await api.get('/admin/arquivos/conteudo', headers=admin, params={'ref': 'arq:999999'})).status_code == 404
            asyncio.run(check())
            with Session(engine) as db:
                from models.audit_log import AuditLogModel
                assert db.query(AuditLogModel).filter_by(action='file_manager.production_file_deleted').count() == 1
        """)

    def test_previews_of_delivered_productions_are_compressed_once(self):
        self.run_case(r"""
            big = b'ID3' + b'x' * 5000
            preview, preview_key = send('mix.wav', data=big, mime='audio/wav')
            assert not manager.comprimir_uma(session_factory, storage=storage, transcoder=lambda data: b'ID3small')
            with Session(engine) as db:
                db.get(ProducaoModel, 1).status = 'entregue'
                db.commit()
                assert manager.compressao_resumo(db) == {'previas_entregues': 1, 'comprimidas': 0, 'pendentes': 1, 'bitrate': '96k'}
            assert manager.comprimir_uma(session_factory, storage=storage, transcoder=lambda data: b'ID3small')
            assert not manager.comprimir_uma(session_factory, storage=storage, transcoder=lambda data: b'ID3small')
            with Session(engine) as db:
                model = db.get(ProducaoArquivoModel, preview)
                assert model.comprimido_em is not None and model.mime_type == 'audio/mpeg' and model.nome_exibicao == 'mix.mp3'
                assert model.tamanho_bytes == len(b'ID3small') and files.read(model, storage=storage) == b'ID3small'
                assert manager.compressao_resumo(db)['comprimidas'] == 1
            assert preview_key in storage.deleted
        """)


if __name__ == "__main__":
    unittest.main()
