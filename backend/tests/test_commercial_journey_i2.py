"""Connected real HTTP regression; SQLite is supplemental, not PostgreSQL evidence."""
from pathlib import Path
import unittest

import test_bootstrap_database as isolated


SETUP = r'''
import os
import socket
import tempfile
from io import BytesIO
from decimal import Decimal
from contextlib import ExitStack
import httpx
import resend
from fastapi import FastAPI
from sqlalchemy.orm import Session
from core.security import get_password_hash
from core.http_security import SecurityMiddleware
from models import UsuarioModel, OrcamentoModel, ProducaoModel, CobrancaModel, PagamentoModel
from database import get_db
from routers import auth, orcamentos, propostas, checkout, webhooks, financeiro
from integrations.mercado_pago import MercadoPagoClient
from services import mercado_pago_service
from pypdf import PdfReader
from commercial_i2_support import PaymentTransport, local_server, signed_webhook

config.settings.MERCADO_PAGO_WEBHOOK_SECRET = 'i2-synthetic-webhook-secret'
config.settings.MERCADO_PAGO_PUBLIC_KEY = 'TEST-i2-only'
config.settings.PUBLIC_FRONTEND_URL = 'http://localhost:4173'
config.settings.PUBLIC_API_URL = 'http://localhost:8000'
config.settings.AI_ENABLED = False
config.settings.AI_PROVIDER = 'disabled'
bootstrap(engine)
with Session(engine) as db:
    db.add(UsuarioModel(username='i2-operator', password_hash=get_password_hash('I2-test-password!'),
                        is_admin=True, role='admin', ativo=True))
    db.commit()
app = FastAPI()
app.add_middleware(SecurityMiddleware)
for module in (auth, orcamentos, propostas, checkout, webhooks, financeiro):
    app.include_router(module.router)
transport = PaymentTransport()
provider = MercadoPagoClient(access_token='TEST-i2-not-a-real-key', session=transport)
app.dependency_overrides[checkout.get_mercado_pago_client] = lambda: provider
app.dependency_overrides[webhooks.get_mercado_pago_client] = lambda: provider

def checked(response, status=200):
    assert response.status_code == status, (response.status_code, response.text[:500])
    return response.json()

with ExitStack() as stack:
    directory = stack.enter_context(tempfile.TemporaryDirectory(prefix='mirai-i2-pdf-'))
    stack.enter_context(patch.dict(os.environ, {'PROPOSTA_PDF_DIR': directory,
        'RATE_LIMIT_DB': os.path.join(directory, 'rate.sqlite3')}))
    send = stack.enter_context(patch.object(resend.Emails, 'send', return_value={'id':'i2-fake-email'}))
    stack.enter_context(patch.object(mercado_pago_service, 'MercadoPagoClient', return_value=provider))
    base_url = stack.enter_context(local_server(app))
    http = stack.enter_context(httpx.Client(base_url=base_url, timeout=40, trust_env=False))
    checked(http.get('/financeiro/resumo'), 401)
    login = checked(http.post('/auth/login', json={'username':'i2-operator','password':'I2-test-password!'}))
    headers = {'Authorization': 'Bearer ' + login['access_token']}
    payload = dict(nome_cliente='I2 Synthetic', email='i2-synthetic@example.com',
                   servico='I2 HTTP contract', valor_total=199.99, detalhes='I2 briefing preserved')
    budget = checked(http.post('/orcamentos', json=payload))
    proposal = checked(http.post(f"/orcamentos/{budget['id']}/proposta", headers=headers, json={}))
    proposal_id = proposal['id']
    assert proposal['cliente_snapshot']['orcamento']['detalhes'] == payload['detalhes']
    assert checked(http.post(f"/orcamentos/{budget['id']}/proposta", headers=headers, json={}))['id'] == proposal_id
    proposal = checked(http.patch(f'/propostas/{proposal_id}', headers=headers, json={
        'objeto':'I2 HTTP journey', 'itens':[{'descricao':'Synthetic work','quantidade':1,'valor_unitario':'199.99'}],
        'condicoes':'Synthetic terms', 'pagamentos':[{'tipo':'completo','titulo':'Integral',
          'url':'https://example.com/i2-test','habilitado':True}]}))
    assert Decimal(proposal['totais']['total']) == Decimal('199.99')
    html = http.get(f'/propostas/{proposal_id}/preview', headers=headers)
    assert html.status_code == 200 and 'I2 HTTP journey' in html.text
    checked(http.post(f'/propostas/{proposal_id}/gerar-documento', headers=headers))
    pdf = http.get(f'/propostas/{proposal_id}/documento', headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')
    assert len(PdfReader(BytesIO(pdf.content)).pages) > 0
    sent = checked(http.post(f'/propostas/{proposal_id}/enviar', headers=headers))
    before = send.call_count
    checked(http.post(f'/propostas/{proposal_id}/enviar', headers=headers))
    assert send.call_count == before and sent['status'] == 'enviada'
    approved = checked(http.post(f'/propostas/{proposal_id}/aprovar', headers=headers))
    checked(http.post(f'/propostas/{proposal_id}/aprovar', headers=headers))
    assert approved['status'] == 'aceita' and approved['aprovada_em']
    with Session(engine) as db:
        assert db.query(ProducaoModel).filter_by(orcamento_id=budget['id']).count() == 1
        charge = db.query(CobrancaModel).filter_by(proposta_id=proposal_id).one()
        reference, charge_id = charge.referencia_externa, charge.id
    summary = checked(http.get(f'/checkout/{reference}'))
    assert Decimal(summary['saldo']) == Decimal('199.99')
    assert payload['email'] not in str(summary) and payload['nome_cliente'] not in str(summary)
'''


class CommercialJourneyTests(unittest.TestCase):
    def run_journey(self, scenario):
        prefix = f"import sys; sys.path.insert(0, {str(Path(__file__).parent)!r})\n"
        isolated.BootstrapTests().run_case(prefix + SETUP + scenario)

    def test_card_rejection_challenge_reconciliation_and_refund(self):
        self.run_journey(r'''
    card = dict(payment_option='integral', card_token='I2-token-not-PAN', payment_method_id='visa',
                installments=1, payer_email='i2-payer@example.com')
    checked(http.post(f'/checkout/{reference}/card', json={**card, 'card_number':'synthetic'}), 422)
    transport.next_status = 'rejected'
    rejected = checked(http.post(f'/checkout/{reference}/card', json=card))
    assert rejected['status'] == 'rejected'
    assert checked(http.get(f'/checkout/{reference}'))['status'] == 'pendente'
    transport.next_status = 'action_required'
    challenge = checked(http.post(f'/checkout/{reference}/card', json=card))
    assert challenge['status'] == 'action_required' and challenge['challenge_url'].startswith('https:')
    assert checked(http.get(f'/checkout/{reference}'))['status'] == 'pendente'
    identifier = next(reversed(transport.orders))
    with Session(engine) as db:
        payment = db.query(PagamentoModel).filter_by(provider_order_id=identifier).one()
        payment_id = payment.id
        assert 'I2-token-not-PAN' not in str(payment.__dict__)
    transport.change(identifier, 'processed')
    checked(http.post(f'/financeiro/pagamentos/{payment_id}/reconciliar', headers=headers))
    assert checked(http.get(f'/checkout/{reference}'))['status'] == 'paga'
    transport.change(identifier, 'refunded', 'refunded')
    checked(signed_webhook(http, identifier, config.settings.MERCADO_PAGO_WEBHOOK_SECRET))
    refunded = checked(http.get(f'/checkout/{reference}'))
    assert Decimal(refunded['valor_pago']) == 0 and Decimal(refunded['saldo']) == Decimal('199.99')
    with Session(engine) as db:
        assert db.query(ProducaoModel).count() == 1
''')

    def test_timeout_remains_pending_until_authoritative_webhook(self):
        self.run_journey(r'''
    transport.timeout_next = True
    checked(http.post(f'/checkout/{reference}/pix', json={'payment_option':'integral'}), 503)
    checked(http.post(f'/checkout/{reference}/pix', json={'payment_option':'integral'}), 409)
    assert checked(http.get(f'/checkout/{reference}'))['status'] == 'pendente'
    assert transport.calls.count('POST') == 1
    identifier = next(iter(transport.orders))
    transport.change(identifier, 'processed')
    checked(signed_webhook(http, identifier, config.settings.MERCADO_PAGO_WEBHOOK_SECRET))
    assert checked(http.get(f'/checkout/{reference}'))['status'] == 'paga'
    with Session(engine) as db:
        assert db.query(PagamentoModel).count() == 1
''')

    def test_http_budget_to_partial_pix_to_finance(self):
        self.run_journey(r'''
    first = checked(http.post(f'/checkout/{reference}/pix', json={'payment_option':'entrada'}))
    assert first['status'] == 'pending' and Decimal(first['valor']) == Decimal('99.99')
    posts = transport.calls.count('POST')
    checked(http.post(f'/checkout/{reference}/pix', json={'payment_option':'entrada'}))
    assert transport.calls.count('POST') == posts
    identifier = next(iter(transport.orders))
    # Body lies about payment; only the authoritative provider GET may settle it.
    checked(signed_webhook(http, identifier, config.settings.MERCADO_PAGO_WEBHOOK_SECRET, status='approved'))
    assert checked(http.get(f'/checkout/{reference}'))['status'] == 'pendente'
    transport.change(identifier, 'processed')
    event_id = 'i2-paid-event'
    checked(signed_webhook(http, identifier, config.settings.MERCADO_PAGO_WEBHOOK_SECRET, event_id))
    checked(signed_webhook(http, identifier, config.settings.MERCADO_PAGO_WEBHOOK_SECRET, event_id))
    partial = checked(http.get(f'/checkout/{reference}'))
    assert partial['status'] == 'parcialmente_paga' and Decimal(partial['saldo']) == Decimal('100.00')
    transport.change(identifier, 'pending', 'pending')
    checked(signed_webhook(http, identifier, config.settings.MERCADO_PAGO_WEBHOOK_SECRET))
    assert checked(http.get(f'/checkout/{reference}'))['status'] == 'parcialmente_paga'
    checked(http.post(f'/checkout/{reference}/pix', json={'payment_option':'saldo'}))
    second_id = next(reversed(transport.orders))
    transport.change(second_id, 'processed')
    checked(signed_webhook(http, second_id, config.settings.MERCADO_PAGO_WEBHOOK_SECRET))
    paid = checked(http.get(f'/checkout/{reference}'))
    assert paid['status'] == 'paga' and Decimal(paid['saldo']) == 0
    assert Decimal(paid['valor_pago']) == Decimal('199.99')
    details = checked(http.get(f'/financeiro/cobrancas/{charge_id}', headers=headers))
    assert details['status'] == 'paga'
    with Session(engine) as db:
        assert db.query(ProducaoModel).count() == 1
        assert db.query(CobrancaModel).count() == 1
        assert db.query(PagamentoModel).count() == 2
    checked(http.post('/webhooks/mercado-pago', json={'data':{'id':identifier}}), 401)
    checked(http.get('/checkout/00000000-0000-0000-0000-000000000000'), 404)
''')


if __name__ == '__main__':
    unittest.main()
