"""Mirai Hit Labs international purchases: Stripe Checkout (USD), webhook, return and refunds."""

import textwrap
import unittest

import test_bootstrap_database as isolated
from test_mirai_labs import EXTRA
from test_portal_produtor import SETUP

STRIPE = r"""
import hashlib, hmac, json, time
from datetime import datetime, timedelta, timezone
from services import stripe_service
from models import PluginPedidoStripeModel

def published_plugin(slug='mirai-saturator', price='149.90'):
    with Session(engine) as db:
        plugin = PluginModel(slug=slug, nome='Mirai Saturator', preco=Decimal(price), status='publicado', formatos_json=['VST3'],
                             recursos_json=[], recursos_en_json=[], versao='1.0.0', publicado_em=datetime.now(timezone.utc))
        db.add(plugin)
        db.flush()
        db.add(PluginArquivoModel(plugin_id=plugin.id, sistema='windows', link_externo='https://drive.example.test/win', versao='1.0.0'))
        db.commit()
        return plugin.id

def signed(event, secret='whsec_test', stamp=None):
    body = json.dumps(event).encode()
    stamp = stamp or int(time.time())
    signature = hmac.new(secret.encode(), f'{stamp}.'.encode() + body, hashlib.sha256).hexdigest()
    return body, {'Stripe-Signature': f't={stamp},v1={signature}', 'Content-Type': 'application/json'}

def session_event(kind, session_id, order_id, amount=14990, currency='usd', paid=True, status='complete'):
    return {'id': 'evt_' + session_id, 'type': kind, 'data': {'object': {
        'id': session_id, 'object': 'checkout.session', 'client_reference_id': str(order_id), 'metadata': {'order_id': str(order_id)},
        'amount_total': amount, 'currency': currency, 'payment_status': 'paid' if paid else 'unpaid', 'status': status,
        'payment_intent': 'pi_' + session_id}}}

class FakeStripe:
    def __init__(self):
        self.calls, self.sessions, self.count = [], {}, 0
    def __call__(self, method, path, data=None, idempotency_key=None):
        self.calls.append((method, path, data, idempotency_key))
        if method == 'POST' and path == '/checkout/sessions':
            self.count += 1
            sid = f'cs_test_{self.count}'
            session = {'id': sid, 'url': f'https://checkout.stripe.com/c/pay/{sid}', 'status': 'open', 'payment_status': 'unpaid',
                       'expires_at': int(time.time()) + 3600, 'amount_total': int(data['line_items[0][price_data][unit_amount]']),
                       'currency': 'usd', 'metadata': {'order_id': data['metadata[order_id]']}, 'client_reference_id': data['client_reference_id']}
            self.sessions[sid] = session
            return session
        if method == 'GET' and path.startswith('/checkout/sessions/'):
            return self.sessions[path.rsplit('/', 1)[1]]
        raise AssertionError(path)
"""


class LabsStripeTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + EXTRA + STRIPE + textwrap.dedent(source))

    def test_international_purchase_webhook_return_refund_and_expiry(self):
        self.run_case(r"""
async def check():
    from core import config
    plugin_id = published_plugin()
    fake = FakeStripe()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as api:
        # Turned off until the keys are set.
        config.settings.STRIPE_SECRET_KEY = ''
        off = await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers={**bearer('client-a'), **key()})
        assert off.status_code == 503, off.text
        config.settings.STRIPE_SECRET_KEY = 'sk_test_123'
        config.settings.STRIPE_WEBHOOK_SECRET = 'whsec_test'
        config.settings.LABS_PUBLIC_URL = 'http://localhost:4174'
        assert (await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers=key())).status_code == 401
        assert (await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers=bearer('client-a'))).status_code == 422

        with patch.object(stripe_service, '_api', fake):
            order_key = key()
            opened = await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers={**bearer('client-a'), **order_key})
            assert opened.status_code == 201, opened.text
            assert opened.json()['checkout_url'] == 'https://checkout.stripe.com/c/pay/cs_test_1'
            method, path, data, idem = fake.calls[0]
            # Same number as the price, in dollars (no conversion).
            assert data['line_items[0][price_data][currency]'] == 'usd' and data['line_items[0][price_data][unit_amount]'] == '14990'
            assert data['success_url'] == 'http://localhost:4174/my-plugins?checkout=success&session_id={CHECKOUT_SESSION_ID}'
            assert data['cancel_url'] == 'http://localhost:4174/plugins/mirai-saturator?checkout=cancelled'
            assert data['locale'] == 'en' and idem == f"mirai-labs-order-{opened.json()['pedido_id']}"
            # Repeating the click, or coming back before paying, reopens the same Stripe page.
            replay = await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers={**bearer('client-a'), **order_key})
            again = await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers={**bearer('client-a'), **key()})
            assert replay.json() == opened.json() and again.json() == opened.json() and len(fake.calls) == 1

        order_id = opened.json()['pedido_id']
        with Session(engine) as db:
            order = db.get(PluginPedidoStripeModel, order_id)
            license = db.get(PluginLicencaModel, order.licenca_id)
            assert order.status == 'aberto' and order.valor == Decimal('149.90') and order.moeda == 'usd'
            assert license.origem == 'stripe' and license.status == 'reservada' and license.proposta_id is None
        waiting = (await api.get('/labs/conta/plugins', headers=bearer('client-a'))).json()
        assert waiting[0]['status'] == 'aguardando_pagamento' and waiting[0]['moeda'] == 'usd'
        assert waiting[0]['checkout_url'] == 'https://checkout.stripe.com/c/pay/cs_test_1' and 'MHL-' not in str(waiting)

        # Webhook: forged or stale signatures are refused; nothing changes.
        body, headers = signed(session_event('checkout.session.completed', 'cs_test_1', order_id), secret='whsec_wrong')
        assert (await api.post('/labs/stripe/webhook', content=body, headers=headers)).status_code == 400
        body, headers = signed(session_event('checkout.session.completed', 'cs_test_1', order_id), stamp=int(time.time()) - 3600)
        assert (await api.post('/labs/stripe/webhook', content=body, headers=headers)).status_code == 400
        # A paid session with another amount never activates the license.
        body, headers = signed(session_event('checkout.session.completed', 'cs_test_1', order_id, amount=100))
        assert (await api.post('/labs/stripe/webhook', content=body, headers=headers)).status_code == 200
        with Session(engine) as db:
            assert db.get(PluginPedidoStripeModel, order_id).status == 'aberto'

        # Confirmed payment: the license becomes active (twice is the same as once).
        body, headers = signed(session_event('checkout.session.completed', 'cs_test_1', order_id))
        for _ in range(2):
            assert (await api.post('/labs/stripe/webhook', content=body, headers=headers)).status_code == 200
        with Session(engine) as db:
            order = db.get(PluginPedidoStripeModel, order_id)
            license = db.get(PluginLicencaModel, order.licenca_id)
            assert order.status == 'pago' and order.pago_em and order.stripe_payment_intent == 'pi_cs_test_1'
            assert license.status == 'ativa' and license.ativada_em
        mine = (await api.get('/labs/conta/plugins', headers=bearer('client-a'))).json()
        assert mine[0]['status'] == 'ativa' and mine[0]['chave'].startswith('MHL-')
        download = await api.get(f"/labs/conta/plugins/{mine[0]['id']}/download/windows", headers=bearer('client-a'))
        assert download.status_code == 200 and download.json()['url'] == 'https://drive.example.test/win'
        owned = await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers={**bearer('client-a'), **key()})
        assert owned.status_code == 409

        # Full refund: the license is suspended.
        refund = {'id': 'evt_refund', 'type': 'charge.refunded', 'data': {'object': {
            'payment_intent': 'pi_cs_test_1', 'amount': 14990, 'amount_refunded': 14990, 'refunded': True}}}
        body, headers = signed(refund)
        assert (await api.post('/labs/stripe/webhook', content=body, headers=headers)).status_code == 200
        with Session(engine) as db:
            order = db.get(PluginPedidoStripeModel, order_id)
            license = db.get(PluginLicencaModel, order.licenca_id)
            assert order.status == 'reembolsado' and license.status == 'reservada' and license.motivo == 'pagamento_revertido'
        assert (await api.get('/labs/conta/plugins', headers=bearer('client-a'))).json()[0]['status'] == 'suspensa'

        with patch.object(stripe_service, '_api', fake):
            # Another customer: the Stripe page expires before paying -> the reservation is released.
            first = await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers={**bearer('client-b'), **key()})
            body, headers = signed(session_event('checkout.session.expired', 'cs_test_2', first.json()['pedido_id'], paid=False, status='expired'))
            assert (await api.post('/labs/stripe/webhook', content=body, headers=headers)).status_code == 200
            with Session(engine) as db:
                order = db.get(PluginPedidoStripeModel, first.json()['pedido_id'])
                assert order.status == 'expirado' and db.get(PluginLicencaModel, order.licenca_id).status == 'cancelada'
            assert (await api.get('/labs/conta/plugins', headers=bearer('client-b'))).json() == []

            # A new order, paid; back on My plugins the store asks Stripe before the webhook arrives.
            second = await api.post('/labs/plugins/mirai-saturator/comprar-internacional', headers={**bearer('client-b'), **key()})
            assert second.json()['checkout_url'].endswith('cs_test_3')
            assert (await api.post('/labs/stripe/sessoes/cs_test_3/confirmar', headers=bearer('client-a'))).status_code == 404
            pending = await api.post('/labs/stripe/sessoes/cs_test_3/confirmar', headers=bearer('client-b'))
            assert pending.json() == {'status': 'aberto', 'pago': False}
            fake.sessions['cs_test_3'].update({'status': 'complete', 'payment_status': 'paid', 'payment_intent': 'pi_3'})
            confirmed = await api.post('/labs/stripe/sessoes/cs_test_3/confirmar', headers=bearer('client-b'))
            assert confirmed.json() == {'status': 'pago', 'pago': True}
        assert (await api.get('/labs/conta/plugins', headers=bearer('client-b'))).json()[0]['status'] == 'ativa'

        # Free plugins never go through Stripe.
        published_plugin(slug='mirai-tuner', price='0')
        free = await api.post('/labs/plugins/mirai-tuner/comprar-internacional', headers={**bearer('client-a'), **key()})
        assert free.status_code == 409

asyncio.run(check())

# The signature check itself.
payload = b'{"type":"x"}'
stamp = int(time.time())
good = hmac.new(b'whsec_test', f'{stamp}.'.encode() + payload, hashlib.sha256).hexdigest()
assert stripe_service.verificar_assinatura(payload, f't={stamp},v1=bad,v1={good}', 'whsec_test')
assert not stripe_service.verificar_assinatura(payload, f't={stamp},v1={good}', '')
assert not stripe_service.verificar_assinatura(payload, None, 'whsec_test')
assert not stripe_service.verificar_assinatura(payload + b' ', f't={stamp},v1={good}', 'whsec_test')
""")


if __name__ == "__main__":
    unittest.main()
