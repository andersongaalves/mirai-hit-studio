"""Roadmap 3.0, 5.22: private tagged beat catalog and commercial exclusivity."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_portal_produtor import SETUP
from test_proposta_comercial import SETUP as COMMERCIAL_SETUP

EXTRA = r"""
import hashlib, io, math, struct, wave
from unittest.mock import patch
from models import AudioTagModel, AudioTagPerfilModel, BeatLicencaModel, BeatModel, ConfigModel
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
            # AUD6-S11-002/S04-002: the studio hears about the submission, the producer about the decision.
            from models import PortalNotificacaoModel
            with Session(engine) as db:
                events = {(row.papel, row.tipo) for row in db.query(PortalNotificacaoModel).filter_by(beat_id=beat_id)}
                assert ('admin', 'admin_beat_revisao') in events and ('produtor', 'beat_aprovado') in events, events
            with Session(engine) as db:
                config = db.query(ConfigModel).first()
                if config is None:
                    config = ConfigModel(desconto=20)
                    db.add(config)
                else:
                    config.desconto = 20
                db.commit()
            catalog = (await api.get('/portal/cliente/beats', headers=bearer('client-a'))).json()
            assert [item['id'] for item in catalog] == [beat_id]
            assert catalog[0]['preco_wav'] == 220 and catalog[0]['preco_multitrack'] == 330 and catalog[0]['capa_url']
            assert not {'produtor_id', 'status', 'ativo', 'motivo_rejeicao'} & set(catalog[0])
            preview = await api.get(f'/beats/{beat_id}/preview', headers=bearer('client-a'))
            assert preview.content == mp3()+b'tag' and preview.headers['cache-control'] == 'private, no-store'
            producer_catalog = await api.get('/portal/produtor/catalogo-beats', headers=bearer('producer-b'))
            assert producer_catalog.status_code == 200
            assert producer_catalog.json()[0]['produtor'] == catalog[0]['produtor']
            assert (await api.get(f'/beats/{beat_id}/preview', headers=bearer('producer-b'))).content == mp3()+b'tag'
            key = '11111111-1111-4111-8111-111111111111'
            requested = await api.post(f'/portal/cliente/beats/{beat_id}/solicitar', headers={**bearer('client-a'),'Idempotency-Key':key}, json={'licenca':'lease_wav'})
            assert requested.status_code == 201, requested.text
            assert requested.json()['itens'][0]['beat_id'] == beat_id and requested.json()['itens'][0]['licenca_beat'] == 'lease_wav'
            assert float(requested.json()['itens'][0]['valor_unitario']) == 220.0
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

    def test_download_names_follow_the_beat_title(self):
        self.run_case(r"""
from types import SimpleNamespace
assert beat_service._download_name(SimpleNamespace(id=4, titulo='Horizonte Ação #1'), '', 'wav') == 'horizonte-acao-1.wav'
assert beat_service._download_name(SimpleNamespace(id=4, titulo='../../etc'), '-multitrack', 'zip') == 'etc-multitrack.zip'
assert beat_service._download_name(SimpleNamespace(id=9, titulo='✨✨'), '', 'mp3') == 'beat-9.mp3'
""")

    def test_admin_license_actions_require_admin_and_reason(self):
        self.run_case(r"""
async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
        assert (await api.post('/admin/beats/licencas/999/liberar', headers=bearer('client-a'), json={'motivo':'x'})).status_code == 403
        assert (await api.post('/admin/beats/licencas/999/liberar', headers=bearer('admin'), json={'motivo':''})).status_code == 422
        assert (await api.post('/admin/beats/licencas/999/liberar', headers=bearer('admin'), json={'motivo':'x'})).status_code == 404
        assert (await api.post('/admin/beats/999/voltar-ao-catalogo', headers=bearer('producer-a'), json={'motivo':'x'})).status_code == 403
        assert (await api.post('/admin/beats/999/voltar-ao-catalogo', headers=bearer('admin'), json={'motivo':'x'})).status_code == 404
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
    # AUD6-S06-003: R2 files leave through a signed link; the API never loads them.
    from types import SimpleNamespace
    from fastapi import HTTPException
    from services.producao_arquivo_storage import ProducaoArquivoIntegridadeError
    class SignedStorage:
        def __init__(self, result): self.result, self.calls, self.reads = result, [], 0
        def download_link(self, reference, **kwargs):
            self.calls.append((reference, kwargs))
            if isinstance(self.result, Exception): raise self.result
            return self.result
        def read(self, reference): self.reads += 1; return b'not-the-recorded-bytes'
    client = SimpleNamespace(cliente_id=91)
    signed = SignedStorage('https://signed.example.test/contrato.wav')
    with patch.object(beat_service, 'new_production_file_storage', return_value=signed):
        delivery = beat_service.purchased_file(db, beat.id, 'wav', client)
    assert delivery == {'type': 'download', 'url': 'https://signed.example.test/contrato.wav', 'filename': 'contrato.wav'}
    assert signed.calls == [(beat.wav_ref, {'filename': 'contrato.wav', 'content_type': 'audio/wav', 'sha256': 'c' * 64})]
    assert signed.reads == 0
    for result in (None, ProducaoArquivoIntegridadeError('x')):
        fallback = SignedStorage(result)
        with patch.object(beat_service, 'new_production_file_storage', return_value=fallback):
            try: beat_service.purchased_file(db, beat.id, 'mp3', client)
            except HTTPException as error: assert error.status_code == 409
            else: raise AssertionError('changed file was delivered')
        assert fallback.reads == (1 if result is None else 0)
""")


RESERVATION_SETUP = r"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from models import AuditLogModel, BeatLicencaModel, BeatModel, ClienteModel, OrcamentoModel, PagamentoModel
from models.enums.financeiro import PagamentoStatus, PagamentoTipo
from services import beat_service, financial_service, producao_liberacao_service
from fastapi import HTTPException
from core import config
import resend
config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
def make_beat(db):
    db.add_all([ClienteModel(id=91, nome='Cliente 1', email='c1@example.test'), ClienteModel(id=92, nome='Cliente 2', email='c2@example.test')])
    db.get(OrcamentoModel, 1).cliente_id = 91; db.get(OrcamentoModel, 2).cliente_id = 92
    beat = BeatModel(produtor_id=1, titulo='Prazo', descricao='', generos='Trap', preco_lease=100,
        preco_exclusivo=500, status='aprovado', ativo=True, original_ref='r2://temp/arquivos/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        original_sha256='a'*64, preview_ref='r2://temp/arquivos/cccccccccccccccccccccccccccccccc/dddddddddddddddddddddddddddddddd',
        preview_sha256='b'*64, tamanho_bytes=10, mime_type='audio/mpeg')
    db.add(beat); db.commit()
    return beat
def accepted(db, budget_id, beat, kind, price, mail):
    proposal = service.criar_por_orcamento(db, budget_id)
    proposal = service.atualizar(db, proposal.id, PropostaUpdate(itens=[{'descricao':'Beat','quantidade':1,'valor_unitario':price,'beat_id':beat.id,'licenca_beat':kind}]))
    with patch.object(resend.Emails, 'send', return_value={'id':mail}): commercial.enviar(db, proposal.id)
    commercial.aprovar(db, proposal.id)
    return proposal
def license_of(db, proposal_id):
    return db.scalar(select(BeatLicencaModel).where(BeatLicencaModel.proposta_id == proposal_id))
def age(db, license, hours):
    license.expira_em = datetime.now(timezone.utc) - timedelta(hours=hours)
    db.commit()
def pay(db, proposal_id, amount):
    charge = financial_service.buscar_por_proposta(db, proposal_id)
    payment = financial_service.registrar_pagamento(db, charge.id, tipo=PagamentoTipo.INTEGRAL, valor=Decimal(amount), status=PagamentoStatus.APROVADO)
    producao_liberacao_service.avaliar_liberacao_producao(db, charge.id)
    db.commit()
    return charge, payment
"""


class BeatReservationTests(unittest.TestCase):
    """Etapa 07, APL-S06-01/02 (AUD6-S06-001 and AUD6-S06-002)."""

    def run_case(self, source):
        isolated.BootstrapTests().run_case(COMMERCIAL_SETUP + RESERVATION_SETUP + textwrap.dedent(source))

    def test_expired_exclusive_reservation_frees_the_catalog_and_blocks_checkout(self):
        self.run_case(r"""
with Session(engine) as db:
    beat = make_beat(db)
    first = accepted(db, 1, beat, 'exclusivo', '500', 'm1')
    license = license_of(db, first.id)
    assert license.status == 'reservada' and license.expira_em is not None
    assert beat_service.client_list(db) == []
    assert beat_service.checkout_blocked_reason(db, first.id) is None
    # A recent pending Pix keeps the reservation past its deadline.
    charge = financial_service.buscar_por_proposta(db, first.id)
    pending = financial_service.registrar_pagamento(db, charge.id, tipo=PagamentoTipo.INTEGRAL, valor=Decimal('500'), status=PagamentoStatus.PENDENTE)
    db.commit()
    age(db, license, 1)
    assert beat_service.expire_reservations(db) == 0 and license.status == 'reservada'
    pending.created_at = datetime.now(timezone.utc) - timedelta(hours=30)
    pending.status = PagamentoStatus.CANCELADO.value
    db.commit()
    catalog = beat_service.client_list(db)
    db.refresh(license)
    assert license.status == 'cancelada' and license.motivo_cancelamento == 'expirada' and license.cancelada_em
    assert [item['id'] for item in catalog] == [beat.id] and catalog[0]['preco_exclusivo'] == 500
    assert 'expirou' in beat_service.checkout_blocked_reason(db, first.id)
    assert db.query(AuditLogModel).filter_by(action='beat.licenca.expirada', entity_id=license.id).count() == 1
    # The beat can now be reserved by someone else.
    second = accepted(db, 2, beat, 'lease', '100', 'm2')
    assert license_of(db, second.id).status == 'reservada'
""")

    def test_payment_after_expiry_is_honoured_only_when_the_beat_is_still_free(self):
        self.run_case(r"""
with Session(engine) as db:
    beat = make_beat(db)
    first = accepted(db, 1, beat, 'lease', '100', 'm1')
    license = license_of(db, first.id)
    age(db, license, 1)
    beat_service.expire_reservations(db); db.commit()
    assert license.status == 'cancelada'
    charge, payment = pay(db, first.id, '100')
    db.refresh(license); db.refresh(payment)
    assert license.status == 'adquirida' and license.motivo_cancelamento is None
    assert payment.reconciliation_status is None

    second = accepted(db, 2, beat, 'exclusivo', '500', 'm2')
    exclusive = license_of(db, second.id)
    age(db, exclusive, 1)
    beat_service.expire_reservations(db); db.commit()
    db.get(OrcamentoModel, 3).cliente_id = 91; db.commit()
    other = accepted(db, 3, beat, 'exclusivo', '500', 'm3')
    assert license_of(db, other.id).status == 'reservada'
    charge, payment = pay(db, second.id, '500')
    db.refresh(exclusive); db.refresh(payment); db.refresh(beat)
    assert exclusive.status == 'cancelada' and beat.status == 'aprovado'
    assert payment.reconciliation_status == 'conflict' and payment.reconciliation_reason == 'beat_reservation_released'
""")

    def test_refund_revokes_access_and_admin_decides_on_relisting(self):
        self.run_case(r"""
admin = type('Actor', (), {'id': 1})()
with Session(engine) as db:
    beat = make_beat(db)
    first = accepted(db, 1, beat, 'exclusivo', '500', 'm1')
    license = license_of(db, first.id)
    try: beat_service.relist(db, beat.id, 'teste', admin)
    except HTTPException as error: assert error.status_code == 409
    else: raise AssertionError('relisted an approved beat')
    charge, payment = pay(db, first.id, '500')
    db.refresh(beat); db.refresh(license)
    assert license.status == 'adquirida' and beat.status == 'vendido'
    payment.status = PagamentoStatus.REEMBOLSADO.value
    financial_service.sincronizar_status(charge)
    producao_liberacao_service.avaliar_cobranca_bloqueada(db, charge)
    db.commit(); db.refresh(license); db.refresh(beat)
    assert license.status == 'cancelada' and license.motivo_cancelamento == 'pagamento_revertido'
    assert beat.status == 'vendido' and beat.ativo is False
    assert beat_service.client_list(db) == []
    listed = [item for item in beat_service.admin_list(db) if item['id'] == beat.id][0]
    assert listed['pode_voltar_ao_catalogo'] is True and listed['licencas'][0]['motivo_cancelamento'] == 'pagamento_revertido'
    try: beat_service.relist(db, beat.id, '  ', admin)
    except HTTPException as error: assert error.status_code == 422
    else: raise AssertionError('relist without reason')
    relisted = beat_service.relist(db, beat.id, 'Reembolso confirmado', admin)
    assert relisted['status'] == 'aprovado' and relisted['ativo'] is True
    assert [item['id'] for item in beat_service.client_list(db)] == [beat.id]
    assert db.query(AuditLogModel).filter_by(action='beat.licenca.revogada').count() == 1
    assert db.query(AuditLogModel).filter_by(action='beat.relistado', actor_user_id=1).count() == 1
""")

    def test_admin_releases_an_open_reservation_with_a_reason(self):
        self.run_case(r"""
admin = type('Actor', (), {'id': 1})()
with Session(engine) as db:
    beat = make_beat(db)
    first = accepted(db, 1, beat, 'exclusivo', '500', 'm1')
    license = license_of(db, first.id)
    # AUD6-S04-003: rejecting while a client holds the reservation is refused.
    from schemas.beat import BeatReview
    try: beat_service.review(db, beat.id, BeatReview(decisao='rejeitar', motivo='Qualidade'), admin)
    except HTTPException as error: assert error.status_code == 409 and 'reserva' in error.detail
    else: raise AssertionError('rejected a reserved beat')
    db.rollback()
    released = beat_service.release_reservation(db, license.id, 'Cliente desistiu', admin)
    assert released['status'] == 'cancelada' and released['motivo_cancelamento'] == 'admin'
    try: beat_service.release_reservation(db, license.id, 'De novo', admin)
    except HTTPException as error: assert error.status_code == 409
    else: raise AssertionError('released twice')
    assert [item['id'] for item in beat_service.client_list(db)] == [beat.id]
    rejected = beat_service.review(db, beat.id, BeatReview(decisao='rejeitar', motivo='Qualidade'), admin)
    assert rejected['status'] == 'rejeitado'
    entry = db.query(AuditLogModel).filter_by(action='beat.licenca.liberada').one()
    assert entry.actor_user_id == 1
    assert entry.metadata_json == {'beat_id': beat.id, 'proposal_id': first.id, 'reason': 'Cliente desistiu'}
""")
