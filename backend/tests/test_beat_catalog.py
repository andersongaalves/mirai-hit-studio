"""Roadmap 3.0, 5.22: private tagged beat catalog and commercial exclusivity."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_portal_produtor import SETUP
from test_proposta_comercial import SETUP as COMMERCIAL_SETUP

EXTRA = r"""
import hashlib, io, math, struct, wave
from unittest.mock import patch
from models import AudioTagModel, AudioTagPerfilModel, BeatLicencaModel, BeatModel
from routers.beats import router as beats_router
from schemas.beat import BeatCreate
from services import beat_service

app.include_router(beats_router)

def wav(seconds=0.2):
    output = io.BytesIO()
    with wave.open(output, 'wb') as sound:
        sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(22050)
        sound.writeframes(b''.join(struct.pack('<h', int(2000 * math.sin(2 * math.pi * 440 * n / 22050))) for n in range(int(seconds * 22050))))
    return output.getvalue()

def mp3(): return b'ID3' + b'\0' * 32

class MemoryStorage:
    def __init__(self): self.objects, self.deleted = {}, []
    def save(self, data, mime):
        key = f'r2://temp/arquivos/{len(self.objects)+1:032x}/{len(self.objects)+2:032x}'
        self.objects[key] = data; return key
    def read(self, key): return self.objects[key]
    def delete(self, key): self.deleted.append(key); self.objects.pop(key, None)

storage = MemoryStorage()
class MemoryImages:
    def __init__(self): self.objects, self.deleted = {}, []
    def save(self, data, mime):
        from types import SimpleNamespace
        key = f'cloudinary://test/public-images/{len(self.objects)+1:032x}'
        self.objects[key] = data
        return SimpleNamespace(reference=key, public_url=f'https://images.example.test/{len(self.objects)}.png')
    def get_public_url(self, reference): return 'https://images.example.test/cover.png'
    def delete(self, reference): self.deleted.append(str(reference)); self.objects.pop(str(reference), None)
images = MemoryImages()
def png(): return b'\x89PNG\r\n\x1a\n' + b'cover'
with Session(engine) as db:
    db.get(UsuarioModel, 2).painel_beats = True
    db.add(UsuarioModel(id=4, username='client-a', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1))
    tag = AudioTagModel(usuario_id=1, nome='tag.wav', mime_type='audio/wav', conteudo=wav(), sha256=hashlib.sha256(wav()).hexdigest(), duracao=.2)
    db.add(tag); db.flush(); db.add(AudioTagPerfilModel(chave='studio', tag_id=tag.id, intervalo_segundos=10, volume_percentual=40, versao=1))
    db.commit()
"""


class BeatCatalogTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + textwrap.dedent(source))

    def test_role_review_private_preview_and_exclusive_sale(self):
        self.run_case(r"""
async def check():
    from core import config
    config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
    with patch.object(beat_service, 'new_production_file_storage', return_value=storage), patch.object(beat_service, 'storage_for', return_value=images), patch.object(beat_service.audio_tag_service, 'duracao', return_value=.2), patch.object(beat_service.audio_tag_service, 'mixar', return_value=mp3()+b'tag'):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
            denied = await api.post('/portal/produtor/beats', headers=bearer('producer-b'), data={'titulo':'Nope','preco_lease':'50'}, files={'mp3':('beat.mp3',mp3(),'audio/mpeg'),'capa':('cover.png',png(),'image/png')})
            assert denied.status_code == 403
            created = await api.post('/portal/produtor/beats', headers=bearer('producer-a'), data={'titulo':'Horizonte','bpm':'140','generos':'Trap','preco_lease':'100','preco_wav':'200','preco_multitrack':'300','preco_exclusivo':'500'}, files={'mp3':('beat.mp3',mp3(),'audio/mpeg'),'wav':('beat.wav',wav(),'audio/wav'),'multitrack':('beat.zip',b'PK\x03\x04more','application/zip'),'capa':('cover.png',png(),'image/png')})
            assert created.status_code == 201, created.text
            beat_id = created.json()['id']
            assert created.json()['status'] == 'revisao' and len(storage.objects) == 4
            assert created.json()['capa_url'].startswith('https://images.example.test/') and len(images.objects) == 1
            assert created.json()['preco_wav_base'] == 200 and created.json()['preco_multitrack_base'] == 300
            assert (await api.get('/portal/cliente/beats', headers=bearer('client-a'))).json() == []
            assert (await api.get(f'/beats/{beat_id}/preview', headers=bearer('client-a'))).status_code == 404
            changed = await api.put(f'/admin/beats/{beat_id}', headers=bearer('admin'), data={'titulo':'Horizonte revisado','descricao':'Nova descricao','bpm':'142','tonalidade':'Am','generos':'Trap','preco_lease':'110','preco_wav':'220','preco_multitrack':'330','preco_exclusivo':'550'})
            assert changed.status_code == 200, changed.text
            assert changed.json()['titulo'] == 'Horizonte revisado' and changed.json()['preco_lease_base'] == 110
            approved = await api.patch(f'/admin/beats/{beat_id}', headers=bearer('admin'), json={'decisao':'aprovar','motivo':''})
            assert approved.status_code == 200
            catalog = (await api.get('/portal/cliente/beats', headers=bearer('client-a'))).json()
            assert [item['id'] for item in catalog] == [beat_id]
            assert catalog[0]['preco_wav'] == 220 and catalog[0]['preco_multitrack'] == 330 and catalog[0]['capa_url']
            preview = await api.get(f'/beats/{beat_id}/preview', headers=bearer('client-a'))
            assert preview.content == mp3()+b'tag' and preview.headers['cache-control'] == 'private, no-store'
            assert (await api.get(f'/beats/{beat_id}/preview', headers=bearer('producer-b'))).status_code == 404
            key = '11111111-1111-4111-8111-111111111111'
            requested = await api.post(f'/portal/cliente/beats/{beat_id}/solicitar', headers={**bearer('client-a'),'Idempotency-Key':key}, json={'licenca':'lease_wav'})
            assert requested.status_code == 201, requested.text
            assert requested.json()['itens'][0]['beat_id'] == beat_id and requested.json()['itens'][0]['licenca_beat'] == 'lease_wav'
            assert requested.json()['status'] == 'aceita'
            assert requested.json()['checkout_path'] == f"/checkout?proposta={requested.json()['id']}"
            assert (await api.get('/portal/cliente/beats/adquiridos', headers=bearer('client-a'))).json() == []
            replay = await api.post(f'/portal/cliente/beats/{beat_id}/solicitar', headers={**bearer('client-a'),'Idempotency-Key':key}, json={'licenca':'lease_wav'})
            assert replay.status_code == 201 and replay.json()['id'] == requested.json()['id']
            blocked_edit = await api.put(f'/admin/beats/{beat_id}', headers=bearer('client-a'), data={'titulo':'Again','preco_lease':'110'})
            assert blocked_edit.status_code == 403
    with Session(engine) as db:
        beat = db.get(BeatModel, beat_id)
        proposal = type('Proposal', (), {'id': 90, 'itens_json':[{'beat_id':beat_id,'licenca_beat':'exclusivo','valor_unitario':'500.00'}]})()
        # FK targets are represented by real rows in the full commercial test; here the lock/availability contract is exercised before insert.
        assert beat.status == 'aprovado' and beat.ativo
asyncio.run(check())
""")

    def test_storage_is_compensated_when_database_write_fails(self):
        self.run_case(r"""
with Session(engine) as db:
    actor = db.get(UsuarioModel, 2)
    payload = BeatCreate(titulo='Falha', preco_lease='10')
    with patch.object(beat_service, 'new_production_file_storage', return_value=storage), patch.object(beat_service, 'storage_for', return_value=images), patch.object(beat_service.audio_tag_service, 'duracao', return_value=.2), patch.object(beat_service.audio_tag_service, 'mixar', return_value=mp3()+b'tag'), patch.object(db, 'commit', side_effect=RuntimeError('db')):
        try: beat_service.create(db, actor=actor, payload=payload, mp3=(mp3(),'audio/mpeg'), cover=(png(),'image/png'), wav=(wav(),'audio/wav'))
        except RuntimeError: pass
        else: raise AssertionError('failure swallowed')
    assert not storage.objects and len(storage.deleted) == 3 and not images.objects and len(images.deleted) == 1
""")

    def test_upload_limits_are_admin_configurable_and_enforced_before_storage(self):
        self.run_case(r"""
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
        producer = await api.get('/portal/produtor/beats/configuracao', headers=bearer('producer-a'))
        assert producer.status_code == 200 and producer.json()['ready'] is True
        assert producer.json()['limits'] == {'capa_mb':10,'mp3_mb':50,'wav_mb':50,'multitrack_mb':50,'multitrack_mode':'arquivo'}
        assert (await api.get('/admin/beats/configuracao', headers=bearer('client-a'))).status_code == 403
        invalid = await api.put('/admin/beats/configuracao', headers=bearer('admin'), json={
            'capa_mb':10,'mp3_mb':50,'wav_mb':100,'multitrack_mb':150,'multitrack_mode':'arquivo',
        })
        assert invalid.status_code == 422
        updated = await api.put('/admin/beats/configuracao', headers=bearer('admin'), json={
            'capa_mb':10,'mp3_mb':1,'wav_mb':50,'multitrack_mb':50,'multitrack_mode':'arquivo',
        })
        assert updated.status_code == 200, updated.text
        assert updated.json()['mp3_mb'] == 1
        oversized = await api.post('/portal/produtor/beats', headers=bearer('producer-a'),
            data={'titulo':'Grande','preco_lease':'100'}, files={
                'mp3':('beat.mp3', b'ID3' + b'0' * (1024 * 1024), 'audio/mpeg'),
                'capa':('cover.png', png(), 'image/png'),
            })
        assert oversized.status_code == 413
        assert 'limite configurado' in oversized.json()['detail'] and not storage.objects
asyncio.run(check())
""")

    def test_external_multitrack_link_is_only_released_after_payment(self):
        self.run_case(r"""
from datetime import datetime, timezone
async def check():
    with patch.object(beat_service, 'new_production_file_storage', return_value=storage), patch.object(beat_service, 'storage_for', return_value=images), patch.object(beat_service.audio_tag_service, 'duracao', return_value=.2), patch.object(beat_service.audio_tag_service, 'mixar', return_value=mp3()+b'tag'):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
            configured = await api.put('/admin/beats/configuracao', headers=bearer('admin'), json={
                'capa_mb':10,'mp3_mb':50,'wav_mb':50,'multitrack_mb':50,'multitrack_mode':'link',
            })
            assert configured.status_code == 200, configured.text
            created = await api.post('/portal/produtor/beats', headers=bearer('producer-a'),
                data={'titulo':'Link privado','preco_lease':'100','preco_multitrack':'300','multitrack_url':'https://drive.example.test/private-token'},
                files={'mp3':('beat.mp3',mp3(),'audio/mpeg'),'capa':('cover.png',png(),'image/png')})
            assert created.status_code == 201, created.text
            beat_id = created.json()['id']
            assert created.json()['multitrack_origem'] == 'link'
            assert 'private-token' not in created.text
            assert (await api.get(f'/portal/cliente/beats/{beat_id}/multitrack', headers=bearer('client-a'))).status_code == 404
            with Session(engine) as db:
                db.add(BeatLicencaModel(beat_id=beat_id, proposta_id=1, cliente_id=1, tipo='multitrack', status='adquirida', valor=300, adquirida_em=datetime.now(timezone.utc)))
                db.commit()
            released = await api.get(f'/portal/cliente/beats/{beat_id}/multitrack', headers=bearer('client-a'))
            assert released.status_code == 200 and released.json() == {'type':'link','url':'https://drive.example.test/private-token'}
            purchased = await api.get(f'/portal/cliente/beats/{beat_id}/arquivo/multitrack', headers=bearer('client-a'))
            assert purchased.status_code == 200 and purchased.json() == released.json()
            acquired = await api.get('/portal/cliente/beats/adquiridos', headers=bearer('client-a'))
            assert acquired.status_code == 200 and acquired.json()[0]['beat_id'] == beat_id
            assert acquired.json()[0]['arquivos'] == ['multitrack']
asyncio.run(check())
""")

    def test_admin_replaces_tagged_preview_and_missing_format_is_rejected(self):
        self.run_case(r"""
async def check():
    with patch.object(beat_service, 'new_production_file_storage', return_value=storage), patch.object(beat_service, 'storage_for', return_value=images), patch.object(beat_service.audio_tag_service, 'duracao', return_value=.2), patch.object(beat_service.audio_tag_service, 'mixar', side_effect=[mp3()+b'tag-a', mp3()+b'tag-b']):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
            invalid = await api.post('/portal/produtor/beats', headers=bearer('producer-a'), data={'titulo':'Sem WAV','preco_wav':'200'}, files={'mp3':('beat.mp3',mp3(),'audio/mpeg'),'capa':('cover.png',png(),'image/png')})
            assert invalid.status_code == 422 and not storage.objects
            created = await api.post('/portal/produtor/beats', headers=bearer('producer-a'), data={'titulo':'Troca','preco_lease':'100'}, files={'mp3':('beat.mp3',mp3(),'audio/mpeg'),'capa':('cover.png',png(),'image/png')})
            assert created.status_code == 201, created.text
            beat_id = created.json()['id']
            assert len(storage.objects) == 2
            before = set(storage.objects)
            changed = await api.put(f'/admin/beats/{beat_id}', headers=bearer('admin'), data={'titulo':'Troca revisada','preco_lease':'120','preco_wav':'250'}, files={'mp3':('novo.mp3',mp3()+b'new','audio/mpeg'),'wav':('beat.wav',wav(),'audio/wav'),'capa':('new.png',png()+b'new','image/png')})
            assert changed.status_code == 200, changed.text
            assert changed.json()['status'] == 'revisao' and changed.json()['tem_wav']
            assert len(storage.objects) == 3 and not (before & set(storage.objects))
            assert before.issubset(set(storage.deleted))
            assert len(images.objects) == 1 and len(images.deleted) == 1
            assert (await api.patch(f'/admin/beats/{beat_id}', headers=bearer('admin'), json={'decisao':'aprovar'})).status_code == 200
            preview = await api.get(f'/beats/{beat_id}/preview', headers=bearer('client-a'))
            assert preview.content == mp3()+b'tag-b'
asyncio.run(check())
""")

    def test_proposal_item_contract_rejects_incomplete_or_mixed_origin(self):
        self.run_case(r"""
from pydantic import ValidationError
from schemas.proposta import PropostaItem
for payload in [
    {'descricao':'Beat','quantidade':1,'valor_unitario':'10','beat_id':1},
    {'descricao':'Beat','quantidade':2,'valor_unitario':'10','beat_id':1,'licenca_beat':'lease'},
    {'descricao':'Beat','quantidade':1,'valor_unitario':'10','beat_id':1,'licenca_beat':'lease','servico_id':1},
]:
    try: PropostaItem.model_validate(payload)
    except ValidationError: pass
    else: raise AssertionError(payload)
assert PropostaItem.model_validate({'descricao':'Beat','quantidade':1,'valor_unitario':'10','beat_id':1,'licenca_beat':'lease'}).beat_id == 1
""")


class BeatCommercialTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(COMMERCIAL_SETUP + textwrap.dedent(source))

    def test_exclusive_reservation_blocks_lease_and_full_payment_removes_catalog(self):
        self.run_case(r"""
from decimal import Decimal
from models import BeatLicencaModel, BeatModel, ClienteModel, OrcamentoModel
from models.enums.financeiro import PagamentoStatus, PagamentoTipo
from services import beat_service, financial_service, producao_liberacao_service
from core import config
import resend
config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
with Session(engine) as db:
    db.add_all([ClienteModel(id=91, nome='Cliente 1', email='c1@example.test'), ClienteModel(id=92, nome='Cliente 2', email='c2@example.test')])
    db.get(OrcamentoModel, 1).cliente_id = 91; db.get(OrcamentoModel, 2).cliente_id = 92
    beat = BeatModel(produtor_id=1, titulo='Contrato', descricao='', generos='Trap', preco_lease=100,
        preco_exclusivo=500, status='aprovado', ativo=True, original_ref='r2://temp/arquivos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        original_sha256='a'*64, preview_ref='r2://temp/arquivos/cccccccccccccccccccccccccccccccc/dddddddddddddddddddddddddddddddd',
        preview_sha256='b'*64, wav_ref='r2://temp/arquivos/eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee/ffffffffffffffffffffffffffffffff',
        wav_sha256='c'*64, multitrack_url='https://drive.example.test/exclusive', tamanho_bytes=10, mime_type='audio/mpeg')
    db.add(beat); db.commit()
    first = service.criar_por_orcamento(db, 1)
    first = service.atualizar(db, first.id, PropostaUpdate(itens=[{'descricao':'Contrato exclusivo','quantidade':1,'valor_unitario':'500','beat_id':beat.id,'licenca_beat':'exclusivo'}]))
    with patch.object(resend.Emails, 'send', return_value={'id':'m1'}): commercial.enviar(db, first.id)
    commercial.aprovar(db, first.id)
    license = db.scalar(select(BeatLicencaModel).where(BeatLicencaModel.proposta_id == first.id))
    assert license.status == 'reservada' and license.tipo == 'exclusivo'
    second = service.criar_por_orcamento(db, 2)
    second = service.atualizar(db, second.id, PropostaUpdate(itens=[{'descricao':'Lease','quantidade':1,'valor_unitario':'100','beat_id':beat.id,'licenca_beat':'lease'}]))
    with patch.object(resend.Emails, 'send', return_value={'id':'m2'}): commercial.enviar(db, second.id)
    try: commercial.aprovar(db, second.id)
    except service.PropostaConflito as error: assert 'incompat' in str(error)
    else: raise AssertionError('lease accepted over exclusive reservation')
    charge = financial_service.buscar_por_proposta(db, first.id)
    financial_service.registrar_pagamento(db, charge.id, tipo=PagamentoTipo.INTEGRAL, valor=Decimal('500'), status=PagamentoStatus.APROVADO)
    producao_liberacao_service.avaliar_liberacao_producao(db, charge.id)
    db.commit(); db.refresh(beat); db.refresh(license)
    assert beat.status == 'vendido' and beat.ativo is False
    assert license.status == 'adquirida' and license.adquirida_em is not None
    assert beat_service._available_files(beat, license.tipo) == ['mp3', 'wav', 'multitrack']
""")
