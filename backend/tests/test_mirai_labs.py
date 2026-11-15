"""Mirai Hit Labs: plugin catalog, purchase through the checkout, license and downloads."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_portal_produtor import SETUP

EXTRA = r"""
import hashlib
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy import select
from models import (AuditLogModel, CobrancaModel, PluginArquivoModel, PluginLicencaModel, PluginModel,
                    ProducaoModel, PropostaModel)
from models.enums.financeiro import PagamentoStatus, PagamentoTipo
from routers.labs import router as labs_router
from services import financial_service, plugin_service, producao_liberacao_service

app.include_router(labs_router)

class MemoryStorage:
    def __init__(self): self.objects, self.deleted, self.saved = {}, [], 0
    def save(self, data, mime):
        assert mime == 'application/zip'
        self.saved += 1
        key = f'r2://temp/arquivos/{self.saved:032x}/{self.saved+1000:032x}'
        self.objects[key] = data; return key
    def read(self, key): return self.objects[key]
    def delete(self, key): self.deleted.append(key); self.objects.pop(key, None)

class MemoryImages:
    def __init__(self): self.objects, self.deleted = {}, []
    def save(self, data, mime):
        key = f'cloudinary://test/public-images/{len(self.objects)+1:032x}'
        self.objects[key] = data
        return SimpleNamespace(reference=key, public_url=f'https://images.example.test/{len(self.objects)}.png')
    def get_public_url(self, reference): return 'https://images.example.test/cover.png'
    def delete(self, reference): self.deleted.append(str(reference)); self.objects.pop(str(reference), None)

storage, images = MemoryStorage(), MemoryImages()
ZIP = b'PK\x03\x04' + b'installer' * 10
PNG = b'\x89PNG\r\n\x1a\n' + b'cover'
with Session(engine) as db:
    db.add(UsuarioModel(id=4, username='client-a', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=1))
    db.add(UsuarioModel(id=5, username='client-b', password_hash='unused', role='cliente', is_admin=False, ativo=True, cliente_id=2))
    db.commit()

def key(): return {'Idempotency-Key': str(uuid.uuid4())}
def plugin_payload(**overrides):
    data = {'nome': 'Mirai Saturator', 'slug': 'mirai-saturator', 'tagline': 'Saturação analógica',
            'descricao': 'Calor de fita e válvula.', 'categoria': 'Saturação', 'versao': '1.0.0',
            'formatos': ['AU', 'VST3', 'VST3'], 'recursos': ['Três modos', '  Três modos ', 'Oversampling 4x'],
            'requisitos': 'Windows 10+ ou macOS 12+', 'preco': '149.90', 'preco_promocional': None,
            'video_url': None, 'status': 'rascunho', 'destaque': True, 'ordem': 0}
    data.update(overrides)
    return data
"""


class MiraiLabsTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + textwrap.dedent(source))

    def test_catalog_purchase_license_download_and_admin(self):
        self.run_case(r"""
async def check():
    from core import config
    config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
    with patch.object(plugin_service, 'new_production_file_storage', return_value=storage), patch.object(plugin_service, 'storage_for', return_value=images):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
            admin = bearer('admin')
            assert (await api.get('/admin/labs/plugins', headers=bearer('client-a'))).status_code == 403
            assert (await api.post('/admin/labs/plugins', headers=admin, json=plugin_payload(slug='Bad Slug'))).status_code == 422
            assert (await api.post('/admin/labs/plugins', headers=admin, json=plugin_payload(preco_promocional='200'))).status_code == 422
            # A plugin cannot be published before it has a cover and an installer.
            early = await api.post('/admin/labs/plugins', headers=admin, json=plugin_payload(status='publicado'))
            assert early.status_code == 409, early.text
            created = await api.post('/admin/labs/plugins', headers=admin, json=plugin_payload())
            assert created.status_code == 201, created.text
            plugin = created.json()
            assert plugin['formatos'] == ['VST3', 'AU'] and plugin['recursos'] == ['Três modos', 'Oversampling 4x']
            assert (await api.post('/admin/labs/plugins', headers=admin, json=plugin_payload())).status_code == 409
            assert (await api.get('/labs/plugins')).json() == []
            blocked = await api.put(f"/admin/labs/plugins/{plugin['id']}", headers=admin, json=plugin_payload(status='publicado'))
            assert blocked.status_code == 409
            cover = await api.post(f"/admin/labs/plugins/{plugin['id']}/capa", headers=admin, files={'capa': ('capa.png', PNG, 'image/png')})
            assert cover.status_code == 200 and cover.json()['capa_url'].startswith('https://images.example.test/')
            assert (await api.post(f"/admin/labs/plugins/{plugin['id']}/instaladores/windows", headers=admin,
                                   files={'arquivo': ('setup.exe', b'MZ', 'application/octet-stream')})).status_code == 422
            windows = await api.post(f"/admin/labs/plugins/{plugin['id']}/instaladores/windows", headers=admin,
                                     data={'versao': '1.0.1'}, files={'arquivo': ('setup.zip', ZIP, 'application/zip')})
            assert windows.status_code == 200, windows.text
            assert windows.json()['instaladores'][0]['sistema'] == 'windows' and windows.json()['instaladores'][0]['versao'] == '1.0.1'
            assert (await api.put(f"/admin/labs/plugins/{plugin['id']}/instaladores/macos/link", headers=admin,
                                  json={'link': 'http://insecure.example.test/mac.zip'})).status_code == 422
            mac = await api.put(f"/admin/labs/plugins/{plugin['id']}/instaladores/macos/link", headers=admin,
                                json={'link': 'https://drive.example.test/mirai-saturator-mac'})
            assert mac.status_code == 200 and [item['sistema'] for item in mac.json()['instaladores']] == ['windows', 'macos']
            # Replacing the Windows installer removes the old file from storage.
            first_ref = next(iter(storage.objects))
            replaced = await api.post(f"/admin/labs/plugins/{plugin['id']}/instaladores/windows", headers=admin,
                                      files={'arquivo': ('setup.zip', ZIP + b'v2', 'application/zip')})
            assert replaced.status_code == 200 and storage.deleted == [first_ref] and len(storage.objects) == 1
            english = {'tagline_en': '  Analog saturation ', 'descricao_en': 'Tape and tube warmth.', 'categoria_en': 'Saturation',
                       'recursos_en': ['Three modes', 'Three  modes', '4x oversampling'], 'requisitos_en': 'Windows 10+ or macOS 12+'}
            published = await api.put(f"/admin/labs/plugins/{plugin['id']}", headers=admin, json=plugin_payload(status='publicado', **english))
            assert published.status_code == 200, published.text
            assert published.json()['publicado_em']

            # Public catalog: published plugins only, without internal data.
            public = await api.get('/labs/plugins')
            assert public.status_code == 200 and public.headers['cache-control'] == 'public, max-age=60'
            assert [item['slug'] for item in public.json()] == ['mirai-saturator']
            item = public.json()[0]
            assert item['preco_vigente'] == '149.90' and item['gratuito'] is False
            assert [row['sistema'] for row in item['sistemas']] == ['windows', 'macos']
            # English texts for the store (default language), cleaned like the Portuguese ones.
            assert item['tagline'] == 'Saturação analógica'
            assert item['en'] == {'tagline': 'Analog saturation', 'descricao': 'Tape and tube warmth.', 'categoria': 'Saturation',
                                  'recursos': ['Three modes', '4x oversampling'], 'requisitos': 'Windows 10+ or macOS 12+'}
            assert not {'id', 'status', 'licencas', 'instaladores', 'capa_ref'} & set(item)
            assert 'drive.example.test' not in public.text and 'r2://' not in public.text
            assert (await api.get('/labs/plugins/mirai-saturator')).json() == item
            assert (await api.get('/labs/plugins/nao-existe')).status_code == 404

            # Purchase: account required; the order goes to the studio checkout.
            assert (await api.post('/labs/plugins/mirai-saturator/comprar', headers=key())).status_code == 401
            assert (await api.post('/labs/plugins/mirai-saturator/comprar', headers=bearer('client-a'))).status_code == 422
            order_key = key()
            bought = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-a'), **order_key})
            assert bought.status_code == 201, bought.text
            proposal_id = bought.json()['proposta_id']
            assert set(bought.json()) == {'gratuito', 'proposta_id', 'checkout_path', 'checkout_url'}
            assert bought.json()['gratuito'] is False and bought.json()['checkout_path'] == f'/checkout?proposta={proposal_id}'
            # the opaque public checkout: Labs-only accounts have no studio portal to open the proposal path
            checkout_url = bought.json()['checkout_url']
            assert checkout_url.startswith('http://localhost:4173/checkout/')
            replay = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-a'), **order_key})
            assert replay.status_code == 201 and replay.json()['proposta_id'] == proposal_id
            # Coming back before paying reopens the same checkout instead of a new order.
            again = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-a'), **key()})
            assert again.status_code == 201 and again.json()['proposta_id'] == proposal_id
            with Session(engine) as db:
                proposal = db.get(PropostaModel, proposal_id)
                assert proposal.finalidade == 'plugins' and proposal.politica_pagamento == 'integral' and proposal.status == 'aceita'
                assert proposal.itens_json[0]['plugin_id'] == plugin['id'] and proposal.snapshot_economico['itens'][0]['plugin_nome'] == 'Mirai Saturator'
                license = db.scalar(select(PluginLicencaModel).where(PluginLicencaModel.proposta_id == proposal_id))
                assert license.status == 'reservada' and license.valor == Decimal('149.90') and license.chave.startswith('MHL-')
                charge = financial_service.buscar_por_proposta(db, proposal_id)
                assert charge.valor_total == Decimal('149.90') and charge.status == 'pendente'
                assert checkout_url == f'http://localhost:4173/checkout/{charge.referencia_externa}'
            waiting = (await api.get('/portal/cliente/plugins', headers=bearer('client-a'))).json()
            assert waiting == [{'id': license.id, 'status': 'aguardando_pagamento', 'plugin': 'Mirai Saturator',
                                'slug': 'mirai-saturator', 'capa_url': item['capa_url'], 'sistemas': [],
                                'checkout_path': f'/checkout?proposta={proposal_id}', 'checkout_url': checkout_url}]
            assert 'MHL-' not in str(waiting)
            # The Labs store shows the same list (My plugins) to studio clients.
            assert (await api.get('/labs/conta/plugins', headers=bearer('client-a'))).json() == waiting
            assert (await api.get('/labs/conta/plugins')).status_code == 401
            # A Labs-only account buys on the store but never opens the studio portal list.
            with Session(engine) as db:
                db.get(UsuarioModel, 5).somente_labs = True
                db.commit()
            assert (await api.get('/labs/conta/plugins', headers=bearer('client-b'))).json() == []
            assert (await api.get('/portal/cliente/plugins', headers=bearer('client-b'))).status_code == 403
            with Session(engine) as db:
                db.get(UsuarioModel, 5).somente_labs = False
                db.commit()
            assert (await api.get(f'/portal/cliente/plugins/{license.id}/download/windows', headers=bearer('client-a'))).status_code == 404

            # Payment: the license becomes active; no production is created for a plugin order.
            with Session(engine) as db:
                charge = financial_service.buscar_por_proposta(db, proposal_id)
                financial_service.registrar_pagamento(db, charge.id, tipo=PagamentoTipo.INTEGRAL, valor=Decimal('149.90'), status=PagamentoStatus.APROVADO)
                producao_liberacao_service.avaliar_liberacao_producao(db, charge.id)
                db.commit()
                assert db.get(PluginLicencaModel, license.id).status == 'ativa'
                assert db.scalar(select(ProducaoModel).where(ProducaoModel.orcamento_id == db.get(PropostaModel, proposal_id).orcamento_id)) is None
            mine = (await api.get('/portal/cliente/plugins', headers=bearer('client-a'))).json()
            assert len(mine) == 1 and mine[0]['status'] == 'ativa' and mine[0]['chave'] == license.chave
            assert [row['sistema'] for row in mine[0]['sistemas']] == ['windows', 'macos']
            assert (await api.get('/portal/cliente/plugins', headers=bearer('client-b'))).json() == []
            win = await api.get(f'/portal/cliente/plugins/{license.id}/download/windows', headers=bearer('client-a'))
            assert win.status_code == 200 and win.content == ZIP + b'v2'
            assert win.headers['content-disposition'] == 'attachment; filename="Mirai-Saturator-1.0.0-Windows.zip"'
            assert win.headers['cache-control'] == 'private, no-store'
            mac_link = await api.get(f'/portal/cliente/plugins/{license.id}/download/macos', headers=bearer('client-a'))
            assert mac_link.json() == {'type': 'link', 'url': 'https://drive.example.test/mirai-saturator-mac'}
            assert (await api.get(f'/portal/cliente/plugins/{license.id}/download/macos', headers=bearer('client-b'))).status_code == 404
            assert (await api.get(f'/portal/cliente/plugins/{license.id}/download/linux', headers=bearer('client-a'))).status_code == 404
            owned = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-a'), **key()})
            assert owned.status_code == 409 and 'Meus plugins' in owned.json()['detail']

            # Activation check for the plugin itself: valid or not, never personal data.
            valid = await api.post('/labs/licencas/validar', json={'chave': license.chave.lower(), 'plugin': 'mirai-saturator'})
            assert valid.json() == {'valida': True, 'plugin': 'mirai-saturator', 'status': 'ativa'}
            assert valid.headers['cache-control'] == 'no-store' and 'a@example.test' not in valid.text
            other = await api.post('/labs/licencas/validar', json={'chave': license.chave, 'plugin': 'outro-plugin'})
            assert other.json()['valida'] is False

            # A refund suspends the license (files and key hidden) until it is paid again.
            with Session(engine) as db:
                charge = financial_service.buscar_por_proposta(db, proposal_id)
                charge.status = 'cancelada'
                plugin_service.confirm_paid(db, charge)
                db.commit()
            suspended = (await api.get('/portal/cliente/plugins', headers=bearer('client-a'))).json()
            assert suspended[0]['status'] == 'suspensa' and 'chave' not in suspended[0] and suspended[0]['sistemas'] == []
            assert (await api.get(f'/portal/cliente/plugins/{license.id}/download/windows', headers=bearer('client-a'))).status_code == 404
            assert (await api.post('/labs/licencas/validar', json={'chave': license.chave, 'plugin': 'mirai-saturator'})).json()['valida'] is False
            with Session(engine) as db:
                charge = financial_service.buscar_por_proposta(db, proposal_id)
                charge.status = 'paga'
                plugin_service.confirm_paid(db, charge)
                db.commit()
                assert db.get(PluginLicencaModel, license.id).status == 'ativa'

            # Free plugin: granted at once, one license per client.
            free = await api.post('/admin/labs/plugins', headers=admin, json=plugin_payload(nome='Mirai Tuner', slug='mirai-tuner', preco='0', destaque=False))
            assert free.status_code == 201
            await api.post(f"/admin/labs/plugins/{free.json()['id']}/capa", headers=admin, files={'capa': ('capa.png', PNG, 'image/png')})
            await api.put(f"/admin/labs/plugins/{free.json()['id']}/instaladores/windows/link", headers=admin, json={'link': 'https://drive.example.test/tuner'})
            assert (await api.put(f"/admin/labs/plugins/{free.json()['id']}", headers=admin, json=plugin_payload(nome='Mirai Tuner', slug='mirai-tuner', preco='0', destaque=False, status='publicado'))).status_code == 200
            assert [row['slug'] for row in (await api.get('/labs/plugins')).json()] == ['mirai-saturator', 'mirai-tuner']
            granted = await api.post('/labs/plugins/mirai-tuner/comprar', headers={**bearer('client-b'), **key()})
            assert granted.status_code == 201 and granted.json()['gratuito'] is True, granted.text
            assert (await api.post('/labs/plugins/mirai-tuner/comprar', headers={**bearer('client-b'), **key()})).status_code == 409
            assert [row['plugin'] for row in (await api.get('/portal/cliente/plugins', headers=bearer('client-b'))).json()] == ['Mirai Tuner']

            # Admin: licenses sold, courtesy and revocation.
            sold = await api.get(f"/admin/labs/plugins/{plugin['id']}/licencas", headers=admin)
            assert sold.status_code == 200 and [(row['cliente'], row['status'], row['origem']) for row in sold.json()] == [('Cliente A', 'ativa', 'compra')]
            gift = await api.post(f"/admin/labs/plugins/{plugin['id']}/cortesias", headers=admin, json={'cliente_id': 2})
            assert gift.status_code == 201, gift.text
            assert (await api.post(f"/admin/labs/plugins/{plugin['id']}/cortesias", headers=admin, json={'cliente_id': 2})).status_code == 409
            revoked = await api.post(f"/admin/labs/licencas/{gift.json()['id']}/revogar", headers=admin, json={'motivo': 'teste'})
            assert revoked.status_code == 200 and revoked.json()['status'] == 'revogada'
            assert (await api.post(f"/admin/labs/licencas/{gift.json()['id']}/revogar", headers=admin, json={'motivo': 'teste'})).status_code == 409
            # Courtesy again after a revocation reuses the client's license.
            assert (await api.post(f"/admin/labs/plugins/{plugin['id']}/cortesias", headers=admin, json={'cliente_id': 2})).status_code == 201
            listed = (await api.get('/admin/labs/plugins', headers=admin)).json()
            assert listed[0]['licencas'] == {'ativas': 2, 'reservadas': 0, 'revogadas': 0}
            # A published plugin keeps at least one installer.
            assert (await api.delete(f"/admin/labs/plugins/{free.json()['id']}/instaladores/windows", headers=admin)).status_code == 409
            assert (await api.delete(f"/admin/labs/plugins/{plugin['id']}/instaladores/macos", headers=admin)).status_code == 200

    with Session(engine) as db:
        actions = {row.action for row in db.query(AuditLogModel).all()}
        assert {'plugin.created', 'plugin.installer_updated', 'plugin.checkout_created', 'plugin.license_activated',
                'plugin.license_suspended', 'plugin.installer_downloaded', 'plugin.license_granted',
                'plugin.license_revoked', 'plugin.installer_removed'} <= actions, actions
asyncio.run(check())
""")


if __name__ == "__main__":
    unittest.main()
