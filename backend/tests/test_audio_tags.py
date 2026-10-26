"""Audio tags use real decoding/rendering and private Storage boundary fakes."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_portal_produtor import SETUP

EXTRA = '''
import hashlib, io, math, struct, wave
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from models import AudioTagModel, AudioTagPerfilModel, PreviaTagJobModel, ProducaoArquivoModel
from routers.audio_tags import router as tag_router
from routers.portal_cliente import router as client_router
from services import audio_tag_service as tags, producao_arquivo_service as files
app.include_router(tag_router)
app.include_router(client_router)
with Session(engine) as db:
    db.add(UsuarioModel(id=4, username='client-a', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1))
    db.add(UsuarioModel(id=5, username='client-b', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=2))
    db.commit()

def wav(seconds=0.3, frequency=1000):
    output = io.BytesIO()
    with wave.open(output, 'wb') as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(22050)
        sound.writeframes(b''.join(struct.pack('<h', int(3000 * math.sin(2 * math.pi * frequency * n / 22050)))
                                  for n in range(int(seconds * 22050))))
    return output.getvalue()
class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.deleted = []
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
'''


class AudioTagTests(unittest.TestCase):
    def run_case(self, code):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + textwrap.dedent(code))

    def test_private_configuration_snapshot_and_client_variant(self):
        self.run_case('''
            async def check():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
                    assert (await api.get('/admin/audio-tag', headers=bearer('producer-a'))).status_code == 403
                    assert (await api.get('/portal/produtor/audio-tag', headers=bearer('client-a'))).status_code == 403
                    before = await api.get('/admin/audio-tag', headers=bearer('admin'))
                    assert before.json()['versao'] == 0 and before.json()['nome'] is None
                    config = {'versao':0, 'intervalo_segundos':10, 'volume_percentual':40}
                    changed = await api.put('/admin/audio-tag', headers=bearer('admin'), json=config)
                    assert changed.status_code == 200 and changed.json()['versao'] == 1, changed.text
                    assert (await api.put('/admin/audio-tag', headers=bearer('admin'), json=config)).status_code == 409
                    assert (await api.put('/admin/audio-tag', headers=bearer('admin'), json={**config,'volume_percentual':0})).status_code == 422
                    for blob in (b'invalid', wav(11)):
                        bad = await api.post('/admin/audio-tag', headers=bearer('admin'), data={'versao':'1'},
                                             files={'arquivo':('tag.wav',blob,'audio/wav')})
                        assert bad.status_code == 422, bad.text
                    stamp = await api.post('/admin/audio-tag', headers=bearer('admin'), data={'versao':'1'},
                                           files={'arquivo':('mirai.wav',wav(),'audio/wav')})
                    assert stamp.status_code == 200 and stamp.json()['versao'] == 2, stamp.text
                    assert (await api.get('/portal/produtor/audio-tag', headers=bearer('producer-a'))).json()['padrao_disponivel']
                    assert (await api.get('/portal/produtor/audio-tag/conteudo', headers=bearer('producer-a'))).status_code == 404
                    original = wav(2)
                    with patch.object(files, 'new_production_file_storage', return_value=storage):
                        uploaded = await api.post('/portal/produtor/producoes/1/arquivos', headers=bearer('producer-a'),
                            data={'tipo':'previa'}, files={'arquivo':('mix.wav', original, 'audio/wav')})
                    assert uploaded.status_code == 201, uploaded.text
                    file_id = uploaded.json()['id']
                    assert uploaded.json()['processamento_tag'] == 'pendente' and uploaded.json()['visivel_cliente'] is True
                    with Session(engine) as db:
                        model = db.get(ProducaoArquivoModel, file_id)
                        assert model.original_restrito and not model.visivel_cliente
                        assert model.tag_processamento.tag_id == stamp.json()['tag_id']
                        assert files.read(model, storage=storage) == original
                        # Even an old backend cannot expose the original through its visibility flag.
                        model.visivel_cliente = True
                        try:
                            db.commit()
                        except IntegrityError:
                            db.rollback()
                        else:
                            raise AssertionError('original exposed to legacy backend')
                    with patch.object(files, 'new_production_file_storage', return_value=storage):
                        pending = await api.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=bearer('client-a'))
                    assert pending.status_code == 503
                    assert (await api.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=bearer('client-b'))).status_code == 404
                    await api.put('/admin/audio-tag', headers=bearer('admin'), json={**config,'versao':2,'volume_percentual':80})
                    rendered = b'synthetic-rendered-mp3'
                    def renderer(source, tag, interval, volume):
                        assert source == original and interval == 10 and volume == 40
                        return rendered
                    assert tags.processar_um(session_factory, storage=storage, renderer=renderer)
                    assert not tags.processar_um(session_factory, storage=storage, renderer=renderer)
                    from scripts.migrate_production_files import inventory
                    with Session(engine) as db:
                        before_objects = dict(storage.objects)
                        report = inventory(db)
                        assert report['tagged_previews_preserved_not_copied'] == 1
                        assert report['references_printed'] == report['deletions'] == 0
                        assert not db.new and not db.dirty and not db.deleted
                        assert storage.objects == before_objects and not storage.deleted
                        assert all(key not in str(report) for key in storage.objects)
                    with patch.object(files, 'new_production_file_storage', return_value=storage):
                        delivered = await api.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=bearer('client-a'))
                        assert delivered.status_code == 200 and delivered.content == rendered
                        assert delivered.headers['content-type'].startswith('audio/mpeg')
                        producer = await api.get(f'/portal/produtor/arquivos/{file_id}/conteudo', headers=bearer('producer-a'))
                        assert producer.content == original
                    listed = (await api.get('/portal/cliente/producoes/1/arquivos', headers=bearer('client-a'))).json()[0]
                    assert listed['sha256'] == hashlib.sha256(rendered).hexdigest() and listed['processamento_tag'] == 'pronto'
                    assert 'object_key' not in listed
                    with Session(engine) as db:
                        files.update_visibility(db, model=db.get(ProducaoArquivoModel,file_id), actor=db.get(UsuarioModel,1), producer=True, client=False)
                    assert (await api.get('/portal/cliente/producoes/1/arquivos', headers=bearer('client-a'))).json() == []
                    assert (await api.get(f'/portal/cliente/arquivos/{file_id}/conteudo', headers=bearer('client-a'))).status_code == 404
                    personal = await api.post('/portal/produtor/audio-tag', headers=bearer('producer-a'), data={'versao':'0'},
                                              files={'arquivo':('personal.wav',wav(frequency=900),'audio/wav')})
                    assert personal.status_code == 200, personal.text
                    own_audio = await api.get('/portal/produtor/audio-tag/conteudo', headers=bearer('producer-a'))
                    assert own_audio.content == wav(frequency=900)
                    assert (await api.get('/portal/produtor/audio-tag/conteudo', headers=bearer('producer-b'))).status_code == 404
                    assert (await api.get('/portal/produtor/audio-tag', headers=bearer('producer-b'))).json()['tag_id'] is None
                    with patch.object(files, 'new_production_file_storage', return_value=storage):
                        version2 = await api.post('/portal/produtor/producoes/1/arquivos', headers=bearer('producer-a'),
                            data={'tipo':'previa','substitui_arquivo_id':str(file_id)}, files={'arquivo':('mix-v2.wav', original, 'audio/wav')})
                    assert version2.status_code == 201 and version2.json()['versao'] == 2, version2.text
                    with Session(engine) as db:
                        assert db.get(PreviaTagJobModel,version2.json()['id']).tag_id == personal.json()['tag_id']
                        assert db.get(PreviaTagJobModel,file_id).tag_id == stamp.json()['tag_id']
            asyncio.run(check())
        ''')

    def test_personal_tag_failure_retry_and_non_preview_types(self):
        self.run_case('''
            with Session(engine) as db:
                actor = db.get(UsuarioModel,2)
                assert tags.preparar(db,actor=actor,file_type='previa',mime_type='audio/wav',data=wav()) is None
                own = tags.salvar(db, actor=actor, chave='producer:2', data=wav(), filename='own.wav', mime_type='audio/wav', versao=0)
                snapshot = tags.preparar(db,actor=actor,file_type='previa',mime_type='audio/wav',data=wav())
                assert snapshot['tag_id'] == own['tag_id']
                for kind in ('entrega','material','referencia','comprovante'):
                    assert tags.preparar(db,actor=actor,file_type=kind,mime_type='audio/wav',data=wav()) is None
                sent = files.upload(db, production=db.get(ProducaoModel,1), actor=actor, file_type='previa', filename='mix.wav',
                    mime_type='audio/wav', data=wav(), visible_to_client=True, visible_to_producer=True, storage=storage)
                file_id = sent.id
                original_key = sent.object_key
            def failure(*args):
                raise RuntimeError('synthetic-only')
            assert not tags.processar_um(session_factory, storage=storage, renderer=failure)
            with Session(engine) as db:
                job = db.get(PreviaTagJobModel,file_id)
                assert job.estado == 'erro' and job.object_key is None
                from models import PortalNotificacaoModel
                assert db.query(PortalNotificacaoModel).filter_by(
                    tipo='admin_falha_tag', arquivo_id=file_id, papel='admin').count() == 1
                assert original_key in storage.objects
                model = db.get(ProducaoArquivoModel,file_id)
                assert not model.visivel_cliente
                try:
                    files.read(model, storage=storage, client=True)
                except files.ProducaoArquivoUnavailable:
                    pass
                else:
                    raise AssertionError('failed job exposed original')
            async def retry():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
                    endpoint = f'/admin/audio-tag/previas/{file_id}/reprocessar'
                    assert (await api.get('/admin/audio-tag/previas/falhas',headers=bearer('producer-a'))).status_code == 403
                    pending = (await api.get('/admin/audio-tag/previas/falhas',headers=bearer('admin'))).json()
                    assert [(row['arquivo_id'], row['arquivo_nome'], row['producao_id']) for row in pending] == [(file_id, 'mix.wav', 1)], pending
                    assert (await api.post(endpoint,headers=bearer('producer-a'))).status_code == 403
                    assert (await api.post(endpoint,headers=bearer('admin'))).json()['estado'] == 'pendente'
                    assert (await api.get('/admin/audio-tag/previas/falhas',headers=bearer('admin'))).json() == []
            asyncio.run(retry())
            assert tags.processar_um(session_factory,storage=storage,renderer=lambda *args: b'tagged')
            with Session(engine) as db:
                model = db.get(ProducaoArquivoModel,file_id)
                storage.objects[model.tag_processamento.object_key] = b'tampered'
                try:
                    files.read(model,storage=storage,client=True)
                except files.ProducaoArquivoUnavailable:
                    pass
                else:
                    raise AssertionError('integrity mismatch accepted')
        ''')

    def test_derivative_storage_is_reserved_without_extra_logical_files(self):
        self.run_case('''
            from models import ProducaoCotaArquivoModel
            from services import cota_arquivo_service as quotas
            with Session(engine) as db:
                actor = db.get(UsuarioModel,2)
                tags.salvar(db, actor=actor, chave='producer:2', data=wav(), filename='own.wav', mime_type='audio/wav', versao=0)
                db.add(ProducaoCotaArquivoModel(producao_id=1,tipo='previa',origem='admin',max_total_mb=1))
                db.commit()
                def send():
                    return files.upload(db, production=db.get(ProducaoModel,1), actor=actor, file_type='previa', filename='mix.wav',
                        mime_type='audio/wav', data=wav(1), visible_to_client=True, visible_to_producer=True,
                        storage=storage,enforce_quota=True)
                first = send()
                usage = quotas._uso(db,1)['previa']
                assert usage[0] == 1 and usage[1] == len(wav(1)) + first.tag_processamento.reserva_bytes
                try:
                    send()
                except files.ProducaoArquivoConflict:
                    pass
                else:
                    raise AssertionError('storage reservation exceeded quota')
            assert len(storage.objects) == 1
            assert tags.processar_um(session_factory,storage=storage,renderer=lambda *args: b'tagged')
            with Session(engine) as db:
                count,total = quotas._uso(db,1)['previa']
                assert count == 1 and total == len(wav(1)) + len(b'tagged')
        ''')

    def test_failed_commit_compensates_only_the_new_variant(self):
        self.run_case('''
            with Session(engine) as db:
                actor = db.get(UsuarioModel,2)
                tags.salvar(db, actor=actor, chave='producer:2', data=wav(), filename='own.wav', mime_type='audio/wav', versao=0)
                sent = files.upload(db, production=db.get(ProducaoModel,1), actor=actor, file_type='previa', filename='mix.wav',
                    mime_type='audio/wav', data=wav(), visible_to_client=True, visible_to_producer=True, storage=storage)
                file_id, original_key = sent.id, sent.object_key
            original_commit = Session.commit
            commits = []
            def fail_once(db):
                commits.append(True)
                if len(commits) == 1:
                    raise RuntimeError('synthetic commit failure')
                return original_commit(db)
            with patch.object(Session,'commit',fail_once):
                assert not tags.processar_um(session_factory, storage=storage, renderer=lambda *args: b'tagged')
            assert list(storage.objects) == [original_key]
            assert len(storage.deleted) == 1 and original_key not in storage.deleted
            with Session(engine) as db:
                job = db.get(PreviaTagJobModel,file_id)
                assert job.estado == 'erro' and job.object_key is None
                assert db.get(ProducaoArquivoModel,file_id).object_key == original_key
        ''')

    def test_ambiguous_upload_commit_preserves_original_and_job(self):
        self.run_case('''
            with Session(engine) as db:
                actor = db.get(UsuarioModel,2)
                tags.salvar(db, actor=actor, chave='producer:2', data=wav(), filename='own.wav', mime_type='audio/wav', versao=0)
                original_commit = Session.commit
                def lost_ack(session):
                    original_commit(session)
                    raise RuntimeError('synthetic lost upload acknowledgement')
                with patch.object(Session,'commit',lost_ack):
                    sent = files.upload(db, production=db.get(ProducaoModel,1), actor=actor, file_type='previa', filename='mix.wav',
                        mime_type='audio/wav', data=wav(), visible_to_client=True, visible_to_producer=True, storage=storage)
                assert storage.objects[sent.object_key] == wav() and storage.deleted == []
                assert sent.tag_processamento.estado == 'pendente'
            assert tags.processar_um(session_factory,storage=storage,renderer=lambda *args: b'tagged')
        ''')

    def test_ambiguous_commit_never_deletes_a_committed_variant(self):
        self.run_case('''
            with Session(engine) as db:
                actor = db.get(UsuarioModel,2)
                tags.salvar(db, actor=actor, chave='producer:2', data=wav(), filename='own.wav', mime_type='audio/wav', versao=0)
                sent = files.upload(db, production=db.get(ProducaoModel,1), actor=actor, file_type='previa', filename='mix.wav',
                    mime_type='audio/wav', data=wav(), visible_to_client=True, visible_to_producer=True, storage=storage)
                file_id = sent.id
            original_commit = Session.commit
            def lost_ack(db):
                original_commit(db)
                raise RuntimeError('synthetic lost acknowledgement')
            with patch.object(Session,'commit',lost_ack):
                assert tags.processar_um(session_factory,storage=storage,renderer=lambda *args: b'tagged')
            with Session(engine) as db:
                job = db.get(PreviaTagJobModel,file_id)
                assert job.estado == 'pronto' and storage.objects[job.object_key] == b'tagged'
            assert len(storage.objects) == 2 and storage.deleted == []
        ''')

    def test_real_ffmpeg_periodic_mix_and_duration(self):
        self.run_case('''
            import subprocess
            from imageio_ffmpeg import get_ffmpeg_exe
            original = wav(15, frequency=0)
            tagged = tags.mixar(original, wav(0.5), 10, 40)
            assert 14.9 < tags.duracao(tagged, limite=16) < 15.2
            with tags.TemporaryDirectory() as directory:
                filename = tags.Path(directory) / 'preview.mp3'
                filename.write_bytes(tagged)
                pcm = subprocess.run([get_ffmpeg_exe(), '-v','error','-i',str(filename),'-f','s16le','-ac','1','-ar','22050','pipe:1'],
                    capture_output=True,check=True,timeout=30).stdout
            samples = struct.unpack('<' + 'h' * (len(pcm)//2), pcm)
            def energy(start, end):
                values = samples[int(start*22050):int(end*22050)]
                return sum(abs(value) for value in values)/len(values)
            assert energy(0.1,0.4) > 100 and energy(10.1,10.4) > 100
            assert energy(5,5.5) < 5
            assert original != tagged
        ''')

    def test_additive_migration_roundtrip(self):
        isolated.BootstrapTests().run_case('''
from alembic import command
assert bootstrap(engine) == 'f2b4d6e8a0c3'
assert 'audio_tags' in inspect(engine).get_table_names()
command.downgrade(migration_config(), 'd7f9a1c3e568')
assert 'audio_tags' not in inspect(engine).get_table_names()
assert 'original_restrito' not in {c['name'] for c in inspect(engine).get_columns('producao_arquivos')}
command.upgrade(migration_config(), 'head')
assert 'previa_tag_jobs' in inspect(engine).get_table_names()
''')


if __name__ == "__main__":
    unittest.main()
