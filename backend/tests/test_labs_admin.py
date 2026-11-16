"""Mirai Hit Labs admin panel: releases and update feed, coupons on both checkouts, orders,
refunds, customers, licenses and store content."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_labs_stripe import STRIPE
from test_mirai_labs import EXTRA
from test_portal_produtor import SETUP

ADMIN = r"""
from models import LabsCupomUsoModel, PluginVersaoModel
from routers.labs_admin import router as labs_admin_router
app.include_router(labs_admin_router)

def pay_brl(proposal_id, amount):
    with Session(engine) as db:
        charge = financial_service.buscar_por_proposta(db, proposal_id)
        financial_service.registrar_pagamento(db, charge.id, tipo=PagamentoTipo.INTEGRAL, valor=Decimal(amount), status=PagamentoStatus.APROVADO)
        producao_liberacao_service.avaliar_liberacao_producao(db, charge.id)
        db.commit()

def coupon(**overrides):
    data = {'codigo': 'lancamento10', 'descricao': 'Lançamento', 'tipo': 'percentual', 'valor': '10', 'plugin_id': None,
            'valido_de': None, 'valido_ate': None, 'max_usos': None, 'ativo': True}
    data.update(overrides)
    return data

class FakeRefunds(FakeStripe):
    def __call__(self, method, path, data=None, idempotency_key=None):
        if method == 'POST' and path == '/refunds':
            self.calls.append((method, path, data, idempotency_key))
            return {'id': 're_1', 'status': 'succeeded'}
        return super().__call__(method, path, data, idempotency_key)
"""


class LabsAdminTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + STRIPE + ADMIN + textwrap.dedent(source))

    def test_releases_update_feed_store_content_and_permissions(self):
        self.run_case(r"""
async def check():
    plugin_id = published_plugin()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
        admin = bearer('admin')
        for path in ('/admin/labs/resumo', '/admin/labs/pedidos', '/admin/labs/clientes', '/admin/labs/licencas',
                     '/admin/labs/cupons', '/admin/labs/conteudo', f'/admin/labs/plugins/{plugin_id}/versoes'):
            assert (await api.get(path)).status_code == 401, path
            assert (await api.get(path, headers=bearer('client-a'))).status_code == 403, path
            assert (await api.get(path, headers=admin)).status_code == 200, path

        # Releases: a stable release becomes the current version; a beta does not.
        feed = await api.get('/labs/plugins/mirai-saturator/atualizacao')
        assert feed.status_code == 200 and feed.json()['versao'] == '1.0.0' and feed.json()['publicada_em'] is None
        assert feed.headers['cache-control'] == 'public, max-age=300'
        bad = await api.post(f'/admin/labs/plugins/{plugin_id}/versoes', headers=admin, json={'versao': '1.1 beta'})
        assert bad.status_code == 422
        stable = await api.post(f'/admin/labs/plugins/{plugin_id}/versoes', headers=admin,
                                json={'versao': '1.1.0', 'notas': 'Novo modo válvula.', 'notas_en': 'New tube mode.'})
        assert stable.status_code == 201, stable.text
        assert stable.json()['publicada'] is True and stable.json()['canal'] == 'estavel'
        assert (await api.post(f'/admin/labs/plugins/{plugin_id}/versoes', headers=admin, json={'versao': '1.1.0'})).status_code == 409
        beta = await api.post(f'/admin/labs/plugins/{plugin_id}/versoes', headers=admin, json={'versao': '1.2.0-beta.1', 'canal': 'beta'})
        assert beta.status_code == 201
        assert (await api.get(f'/admin/labs/plugins/{plugin_id}', headers=admin)).json()['versao'] == '1.1.0'
        feed = (await api.get('/labs/plugins/mirai-saturator/atualizacao')).json()
        assert feed['versao'] == '1.1.0' and feed['notas_en'] == 'New tube mode.' and feed['obrigatoria'] is False
        assert feed['pagina'].endswith('/plugins/mirai-saturator') and feed['download'].endswith('/my-plugins')
        assert (await api.get('/labs/plugins/mirai-saturator/atualizacao?canal=beta')).json()['versao'] == '1.2.0-beta.1'
        everything = (await api.get('/labs/atualizacoes')).json()
        assert list(everything['plugins']) == ['mirai-saturator'] and everything['plugins']['mirai-saturator']['versao'] == '1.1.0'
        # A draft release is invisible; removing the current one falls back to the previous stable.
        draft = await api.post(f'/admin/labs/plugins/{plugin_id}/versoes', headers=admin, json={'versao': '2.0.0', 'publicar': False})
        assert draft.json()['publicada'] is False
        assert (await api.get('/labs/plugins/mirai-saturator/atualizacao')).json()['versao'] == '1.1.0'
        listed = (await api.get(f'/admin/labs/plugins/{plugin_id}/versoes', headers=admin)).json()
        assert {row['versao'] for row in listed} == {'1.1.0', '1.2.0-beta.1', '2.0.0'}
        removed = await api.delete(f"/admin/labs/versoes/{stable.json()['id']}", headers=admin)
        assert removed.status_code == 200 and removed.json()['versao_atual'] == '1.1.0'  # no other stable: kept as is
        edited = await api.put(f"/admin/labs/versoes/{draft.json()['id']}", headers=admin, json={'versao': '2.0.0', 'obrigatoria': True})
        assert edited.status_code == 200 and edited.json()['publicada'] is True
        feed = (await api.get('/labs/plugins/mirai-saturator/atualizacao')).json()
        assert feed['versao'] == '2.0.0' and feed['obrigatoria'] is True
        assert (await api.get('/labs/plugins/nao-existe/atualizacao')).status_code == 404

        # Store banner: public only when active; links must be https or a store path.
        assert (await api.get('/labs/conteudo')).json() == {'banner': None}
        assert (await api.put('/admin/labs/conteudo/banner', headers=admin, json={'ativo': True})).status_code == 422
        assert (await api.put('/admin/labs/conteudo/banner', headers=admin, json={'ativo': True, 'texto': 'x', 'link': 'javascript:alert(1)'})).status_code == 422
        saved = await api.put('/admin/labs/conteudo/banner', headers=admin,
                              json={'ativo': True, 'texto': 'Black Friday: 30% off', 'texto_en': 'Black Friday: 30% off', 'link': '/plugins/mirai-saturator'})
        assert saved.status_code == 200 and saved.json()['banner']['ativo'] is True
        assert (await api.get('/labs/conteudo')).json()['banner'] == {'texto': 'Black Friday: 30% off', 'texto_en': 'Black Friday: 30% off', 'link': '/plugins/mirai-saturator'}
        await api.put('/admin/labs/conteudo/banner', headers=admin, json={'ativo': False, 'texto': 'guardado'})
        assert (await api.get('/labs/conteudo')).json() == {'banner': None}
        assert (await api.get('/admin/labs/conteudo', headers=admin)).json()['banner']['texto'] == 'guardado'

        # Store order and featured plugins.
        second = published_plugin(slug='mirai-tuner', price='0')
        ordered = await api.put('/admin/labs/ordem', headers=admin, json={'ids': [second, plugin_id], 'destaques': [second]})
        assert ordered.status_code == 200
        assert [row['slug'] for row in (await api.get('/labs/plugins')).json()] == ['mirai-tuner', 'mirai-saturator']
        assert (await api.put('/admin/labs/ordem', headers=admin, json={'ids': [999]})).status_code == 404
""")

    def test_coupons_on_the_studio_checkout(self):
        self.run_case(r"""
async def check():
    from core import config
    config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
    plugin_id = published_plugin()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
        admin = bearer('admin')
        assert (await api.post('/admin/labs/cupons', headers=admin, json=coupon(valor='120'))).status_code == 422
        assert (await api.post('/admin/labs/cupons', headers=admin, json=coupon(codigo='a b'))).status_code == 422
        created = await api.post('/admin/labs/cupons', headers=admin, json=coupon(max_usos=1))
        assert created.status_code == 201, created.text
        assert created.json()['codigo'] == 'LANCAMENTO10' and created.json()['situacao'] == 'ativo'
        assert (await api.post('/admin/labs/cupons', headers=admin, json=coupon())).status_code == 409

        # Public preview of the price.
        preview = await api.post('/labs/cupons/validar', json={'codigo': 'lancamento10', 'plugin': 'mirai-saturator'})
        assert preview.json() == {'valido': True, 'codigo': 'LANCAMENTO10', 'tipo': 'percentual', 'valor': '10.00',
                                  'preco': '149.90', 'desconto': '14.99', 'preco_final': '134.91'}
        assert (await api.post('/labs/cupons/validar', json={'codigo': 'NADA', 'plugin': 'mirai-saturator'})).json() == {'valido': False, 'motivo': 'Cupom inválido.'}

        # Purchase with the coupon: the charge is the discounted value; the license keeps it.
        bought = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-a'), **key()}, json={'cupom': 'lancamento10'})
        assert bought.status_code == 201, bought.text
        proposal_id = bought.json()['proposta_id']
        with Session(engine) as db:
            charge = financial_service.buscar_por_proposta(db, proposal_id)
            assert charge.valor_total == Decimal('134.91')
            proposal = db.get(PropostaModel, proposal_id)
            assert Decimal(str(proposal.itens_json[0]['valor_unitario'])) == Decimal('149.90')
            assert Decimal(str(proposal.itens_json[0]['desconto'])) == Decimal('14.99')
            license = db.scalar(select(PluginLicencaModel).where(PluginLicencaModel.proposta_id == proposal_id))
            assert license.valor == Decimal('134.91')
            use = db.scalar(select(LabsCupomUsoModel))
            assert use.licenca_id == license.id and use.desconto == Decimal('14.99') and use.moeda == 'brl'
        # Used up (max 1): nobody else can use it while that purchase is open or paid.
        assert (await api.post('/labs/cupons/validar', json={'codigo': 'LANCAMENTO10', 'plugin': 'mirai-saturator'})).json()['motivo'] == 'Cupom esgotado.'
        other = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-b'), **key()}, json={'cupom': 'LANCAMENTO10'})
        assert other.status_code == 409 and other.json()['detail'] == 'Cupom esgotado.'
        pay_brl(proposal_id, '134.91')
        with Session(engine) as db:
            assert db.get(PluginLicencaModel, license.id).status == 'ativa'
        row = (await api.get('/admin/labs/cupons', headers=admin)).json()[0]
        assert row['usos'] == 1 and row['situacao'] == 'esgotado'
        # Used coupons keep their code and cannot be deleted (deactivate instead).
        assert (await api.put(f"/admin/labs/cupons/{row['id']}", headers=admin, json=coupon(codigo='OUTRO', max_usos=1))).status_code == 409
        assert (await api.delete(f"/admin/labs/cupons/{row['id']}", headers=admin)).status_code == 409
        off = await api.put(f"/admin/labs/cupons/{row['id']}", headers=admin, json=coupon(max_usos=5, ativo=False))
        assert off.status_code == 200 and off.json()['situacao'] == 'inativo'

        # A coupon for another plugin, an expired one and a full discount (granted like a courtesy).
        tuner = published_plugin(slug='mirai-tuner', price='49.90')
        await api.post('/admin/labs/cupons', headers=admin, json=coupon(codigo='SOTUNER', plugin_id=tuner))
        wrong = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-b'), **key()}, json={'cupom': 'SOTUNER'})
        assert wrong.status_code == 409 and wrong.json()['detail'] == 'Cupom não vale para este plugin.'
        await api.post('/admin/labs/cupons', headers=admin, json=coupon(codigo='VELHO', valido_de='2020-01-01T00:00:00Z', valido_ate='2020-02-01T00:00:00Z'))
        expired = await api.post('/labs/plugins/mirai-tuner/comprar', headers={**bearer('client-b'), **key()}, json={'cupom': 'VELHO'})
        assert expired.status_code == 409 and expired.json()['detail'] == 'Cupom expirado.'
        await api.post('/admin/labs/cupons', headers=admin, json=coupon(codigo='PRESENTE', tipo='valor', valor='500'))
        gift = await api.post('/labs/plugins/mirai-tuner/comprar', headers={**bearer('client-b'), **key()}, json={'cupom': 'presente'})
        assert gift.status_code == 201 and gift.json()['gratuito'] is True, gift.text
        with Session(engine) as db:
            granted = db.get(PluginLicencaModel, gift.json()['licenca_id'])
            assert granted.status == 'ativa' and granted.origem == 'cortesia' and granted.plugin_id == tuner
        # One use per account.
        again = await api.post('/labs/cupons/validar', json={'codigo': 'PRESENTE', 'plugin': 'mirai-saturator'})
        assert again.json()['valido'] is True
        reuse = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-b'), **key()}, json={'cupom': 'PRESENTE'})
        assert reuse.status_code == 409 and reuse.json()['detail'] == 'Cupom já usado nesta conta.'
        # Without a coupon the purchase is unchanged.
        plain = await api.post('/labs/plugins/mirai-saturator/comprar', headers={**bearer('client-b'), **key()})
        assert plain.status_code == 201
        with Session(engine) as db:
            assert financial_service.buscar_por_proposta(db, plain.json()['proposta_id']).valor_total == Decimal('149.90')
""")

    def test_stripe_coupon_orders_refund_customers_and_licenses(self):
        self.run_case(r"""
async def check():
    from core import config
    plugin_id = published_plugin()
    fake = FakeRefunds()
    config.settings.LABS_STRIPE_ENABLED = True
    config.settings.STRIPE_SECRET_KEY = 'sk_test_123'
    config.settings.STRIPE_WEBHOOK_SECRET = 'whsec_test'
    config.settings.LABS_PUBLIC_URL = 'http://localhost:4174'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
        admin = bearer('admin')
        await api.post('/admin/labs/cupons', headers=admin, json=coupon(codigo='USD20', tipo='valor', valor='20'))
        with patch.object(stripe_service, '_api', fake):
            opened = await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers={**bearer('client-a'), **key()}, json={'cupom': 'usd20'})
            assert opened.status_code == 201, opened.text
            data = fake.calls[0][2]
            assert data['line_items[0][price_data][unit_amount]'] == '12990'
            assert 'coupon USD20' in data['line_items[0][price_data][product_data][description]']
            with Session(engine) as db:
                order = db.scalar(select(PluginPedidoStripeModel))
                assert order.valor == Decimal('129.90')
                use = db.scalar(select(LabsCupomUsoModel))
                assert use.pedido_stripe_id == order.id and use.licenca_id == order.licenca_id and use.moeda == 'usd'
            body, headers = signed(session_event('checkout.session.completed', order.stripe_session_id, order.id, amount=12990))
            assert (await api.post('/labs/stripe/webhook', content=body, headers=headers)).status_code == 200

            # Orders: one list for both checkouts.
            orders = (await api.get('/admin/labs/pedidos', headers=admin)).json()
            assert len(orders) == 1
            row = orders[0]
            assert row['moeda'] == 'usd' and row['status'] == 'pago' and row['valor'] == '129.90'
            assert row['cupom'] == {'codigo': 'USD20', 'desconto': '20.00'} and row['pode_reembolsar'] is True
            assert row['cliente']['email'] == 'a@example.test'
            assert (await api.get('/admin/labs/pedidos?moeda=brl', headers=admin)).json() == []
            assert len((await api.get('/admin/labs/pedidos?q=Cliente%20A', headers=admin)).json()) == 1

            # Overview counts the sale.
            overview = (await api.get('/admin/labs/resumo', headers=admin)).json()
            assert overview['receita']['periodo']['usd'] == '129.90' and overview['receita']['total']['brl'] == '0.00'
            assert overview['vendas_periodo'] == 1 and overview['licencas']['ativas'] == 1
            assert overview['plugins'][0]['receita_usd'] == '129.90' and len(overview['serie']) == 30
            assert overview['ultimas_licencas'][0]['cliente'] == 'Cliente A'

            # Refund: Stripe is called once per order and the license is suspended.
            refunded = await api.post(f"/admin/labs/pedidos/stripe/{row['pedido_id']}/reembolsar", headers=admin, json={'motivo': 'pedido do cliente'})
            assert refunded.status_code == 200 and refunded.json()['status'] == 'reembolsado', refunded.text
            refund_call = [call for call in fake.calls if call[1] == '/refunds'][0]
            assert refund_call[2]['payment_intent'] == order.stripe_payment_intent and refund_call[3] == f'mirai-labs-refund-{order.id}'
            assert (await api.post(f"/admin/labs/pedidos/stripe/{row['pedido_id']}/reembolsar", headers=admin, json={'motivo': 'de novo'})).status_code == 409
            with Session(engine) as db:
                license = db.get(PluginLicencaModel, order.licenca_id)
                assert license.status == 'reservada' and license.motivo == 'pagamento_revertido'

        # Customers: who bought or has a Labs account.
        with Session(engine) as db:
            db.get(UsuarioModel, 5).somente_labs = True
            db.commit()
        customers = (await api.get('/admin/labs/clientes', headers=admin)).json()
        assert [(row['nome'], row['conta']['tipo']) for row in customers] == [('Cliente B', 'labs'), ('Cliente A', 'estudio')]
        detail = (await api.get('/admin/labs/clientes/1', headers=admin)).json()
        assert detail['conta']['usuario'] == 'client-a' and len(detail['licencas']) == 1 and len(detail['pedidos']) == 1
        assert (await api.get('/admin/labs/clientes/999', headers=admin)).status_code == 404

        # Courtesy by e-mail, license search, revoke and reactivate.
        assert (await api.post(f'/admin/labs/plugins/{plugin_id}/cortesias/email', headers=admin, json={'email': 'ninguem@example.test'})).status_code == 404
        gift = await api.post(f'/admin/labs/plugins/{plugin_id}/cortesias/email', headers=admin, json={'email': 'B@example.test'})
        assert gift.status_code == 201, gift.text
        with Session(engine) as db:
            key_b = db.get(PluginLicencaModel, gift.json()['id']).chave
        found = (await api.get(f'/admin/labs/licencas?q={key_b.lower()}', headers=admin)).json()
        assert [row['cliente'] for row in found] == ['Cliente B']
        assert len((await api.get('/admin/labs/licencas?origem=stripe', headers=admin)).json()) == 1
        assert (await api.post(f"/admin/labs/licencas/{gift.json()['id']}/reativar", headers=admin)).status_code == 409
        await api.post(f"/admin/labs/licencas/{gift.json()['id']}/revogar", headers=admin, json={'motivo': 'teste'})
        back = await api.post(f"/admin/labs/licencas/{gift.json()['id']}/reativar", headers=admin)
        assert back.status_code == 200 and back.json()['status'] == 'ativa'
""")


if __name__ == "__main__":
    unittest.main()
