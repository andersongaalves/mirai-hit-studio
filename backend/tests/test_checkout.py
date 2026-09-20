"""F3.4 guest checkout tests; provider HTTP and database are disposable fakes."""

import unittest

import test_bootstrap_database as isolated
from test_mercado_pago import MP_SETUP


CHECKOUT_SETUP = MP_SETUP + r'''
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from database import get_db
from integrations.mercado_pago import MercadoPagoTimeout, MercadoPagoRateLimited
from models.enums.financeiro import CobrancaStatus
from routers.checkout import router as checkout_router, get_mercado_pago_client
from schemas.checkout import CheckoutCardRequest
from services import checkout_service

def accepted_charge(db, budget_id=1):
    current = charge(db, budget_id)
    current.proposta.status = 'aceita'
    db.commit()
    db.refresh(current)
    return current

def checkout_app(db, provider):
    app = FastAPI()
    @app.middleware('http')
    async def request_id(request: Request, call_next):
        request.state.request_id = 'safe-request'
        return await call_next(request)
    app.include_router(checkout_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_mercado_pago_client] = lambda: provider
    return TestClient(app)
'''


class CheckoutTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(CHECKOUT_SETUP + source)

    def test_public_summary_options_and_no_internal_data(self):
        self.run_case(r'''
with Session(engine) as db:
    current = accepted_charge(db)
    token = current.referencia_externa
    summary = checkout_service.resumo(db, token)
    assert [option.tipo for option in summary.opcoes] == ['integral', 'entrada']
    assert summary.opcoes[0].valor == Decimal('150.25')
    assert summary.opcoes[1].valor == Decimal('75.12')
    assert summary.descricao == 'Mixagem' and summary.status == 'pendente'
    public = summary.model_dump(mode='json')
    serialized = str(public).lower()
    for forbidden in ['teste@example.com', 'cliente teste', 'provider_order_id', 'cliente_id', 'orcamento_id']:
        assert forbidden not in serialized
    assert checkout_service.resumo(db, token.upper()).proposta_numero == summary.proposta_numero
    for invalid in ['1', 'not-a-token', '00000000-0000-0000-0000-000000000000']:
        try:
            checkout_service.resumo(db, invalid)
        except checkout_service.CheckoutNaoEncontrado:
            pass
        else:
            raise AssertionError('invalid checkout token accepted')
''')

    def test_pix_is_backend_controlled_recoverable_and_idempotent(self):
        self.run_case(r'''
with Session(engine) as db:
    current = accepted_charge(db)
    token = current.referencia_externa
    provider_order = order(amount='75.12', provider_id='ORD-pix', external_reference='placeholder')
    provider = MercadoPagoClient(access_token='private-access-token', session=FakeSession([]))
    client = checkout_app(db, provider)
    config.settings.MERCADO_PAGO_PUBLIC_KEY = 'public-key-only'
    assert client.get('/checkout/config').json() == {'mercado_pago_public_key': 'public-key-only'}
    assert client.post(f'/checkout/{token}/pix', json={'payment_option':'entrada','amount':'0.01'}).status_code == 422

    original_request = provider._session
    class DynamicSession(FakeSession):
        def request(self, method, url, **kwargs):
            if method == 'POST':
                reference = kwargs['json']['external_reference']
                data = order(amount='75.12', provider_id='ORD-pix', external_reference=reference)
            else:
                payment = db.query(PagamentoModel).one()
                data = order(amount='75.12', provider_id='ORD-pix', external_reference=payment.provider_reference)
            self.calls.append((method, url, kwargs))
            return FakeResponse(201 if method == 'POST' else 200, data)
    provider._session = DynamicSession([])
    first = client.post(f'/checkout/{token}/pix', json={'payment_option':'entrada'})
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload['status'] == 'pending' and payload['valor'] == '75.12'
    assert payload['pix']['qr_code'] == 'pix-secret-code'
    assert db.query(PagamentoModel).count() == 1
    second = client.post(f'/checkout/{token}/pix', json={'payment_option':'entrada'})
    assert second.status_code == 200 and second.json()['pix']['qr_code'] == 'pix-secret-code'
    assert db.query(PagamentoModel).count() == 1
    assert [call[0] for call in provider._session.calls] == ['POST', 'GET']
    sent = provider._session.calls[0][2]['json']
    assert sent['total_amount'] == '75.12' and sent['transactions']['payments'][0]['amount'] == '75.12'
    assert 'amount' not in {'payment_option':'entrada'}
''')

    def test_card_token_is_transient_and_3ds_is_normalized(self):
        self.run_case(r'''
with Session(engine) as db:
    current = accepted_charge(db)
    token = current.referencia_externa
    card_order = order(amount='150.25', status='action_required', detail='pending_challenge',
                       method='visa', pix=False, provider_id='ORD-card', external_reference='placeholder')
    card_order['transactions']['payments'][0]['payment_method']['transaction_security'] = {
        'url': 'https://www.mercadopago.com.br/auth/challenge'
    }
    class CardSession(FakeSession):
        def request(self, method, url, **kwargs):
            data = dict(card_order)
            data['external_reference'] = kwargs['json']['external_reference']
            self.calls.append((method, url, kwargs))
            return FakeResponse(201, data)
    session = CardSession([])
    provider = MercadoPagoClient(access_token='private-access-token', session=session)
    client = checkout_app(db, provider)
    card_token = 'transient-card-token'
    response = client.post(f'/checkout/{token}/card', json={
        'payment_option':'integral', 'card_token':card_token,
        'payment_method_id':'visa', 'payment_method_type':'credit_card',
        'installments':3, 'payer_email':'payer@example.com'
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['status'] == 'action_required'
    assert body['challenge_url'] == 'https://www.mercadopago.com.br/auth/challenge'
    provider_payload = session.calls[0][2]['json']
    assert provider_payload['config']['online']['transaction_security'] == {
        'validation':'on_fraud_risk', 'liability_shift':'required'}
    method = provider_payload['transactions']['payments'][0]['payment_method']
    assert method['installments'] == 3 and method['token'] == card_token
    persisted = db.query(PagamentoModel).one()
    assert card_token not in str(persisted.__dict__)
    assert card_token not in response.text and 'private-access-token' not in response.text
''')

    def test_paid_partial_cancelled_and_ambiguous_timeout(self):
        self.run_case(r'''
with Session(engine) as db:
    partial = accepted_charge(db, 1)
    finance.registrar_pagamento(db, partial.id, tipo='entrada', valor='75.12', status='aprovado')
    finance.sincronizar_status(partial)
    db.commit()
    summary = checkout_service.resumo(db, partial.referencia_externa)
    assert summary.status == 'parcialmente_paga'
    assert [option.tipo for option in summary.opcoes] == ['saldo']
    assert summary.saldo == Decimal('75.13')

    paid = accepted_charge(db, 2)
    finance.registrar_pagamento(db, paid.id, tipo='integral', valor='150.25', status='aprovado')
    finance.sincronizar_status(paid)
    db.commit()
    assert checkout_service.resumo(db, paid.referencia_externa).opcoes == []

    cancelled = accepted_charge(db, 3)
    cancelled.status = CobrancaStatus.CANCELADA.value
    db.commit()
    assert checkout_service.resumo(db, cancelled.referencia_externa).status == 'cancelada'

    ambiguous = accepted_charge(db, 4)
    provider = MercadoPagoClient(access_token='test-token', session=FakeSession([requests.Timeout()]))
    try:
        checkout_service.criar_pix(db, ambiguous.referencia_externa, 'integral', client=provider)
    except MercadoPagoTimeout:
        pass
    else:
        raise AssertionError('timeout hidden')
    assert db.query(PagamentoModel).filter(PagamentoModel.cobranca_id == ambiguous.id).count() == 1
    try:
        checkout_service.criar_pix(db, ambiguous.referencia_externa, 'integral', client=provider)
    except checkout_service.CheckoutConflito as error:
        assert 'conciliacao' in str(error)
    else:
        raise AssertionError('ambiguous timeout created another attempt')
    assert db.query(PagamentoModel).filter(PagamentoModel.cobranca_id == ambiguous.id).count() == 1
''')

    def test_admin_link_and_contract_reject_unsafe_inputs(self):
        self.run_case(r'''
with Session(engine) as db:
    current = accepted_charge(db)
    unauthenticated = checkout_app(db, MercadoPagoClient(access_token='test', session=FakeSession([])))
    assert unauthenticated.get(f'/checkout/proposta/{current.proposta_id}/link').status_code == 401
    link = checkout_service.link_por_proposta(db, current.proposta_id, 'https://miraihitstudio.com.br')
    assert link == f'https://miraihitstudio.com.br/checkout/{current.referencia_externa}'
    for payload in [
        {'payment_option':'integral','card_token':'x','payment_method_id':'visa','installments':0},
        {'payment_option':'integral','card_token':'x','payment_method_id':'visa','installments':1,
         'identification_type':'CPF'},
        {'payment_option':'integral','card_token':'x','payment_method_id':'visa','installments':1,
         'amount':'0.01'},
    ]:
        try:
            CheckoutCardRequest.model_validate(payload)
        except Exception:
            pass
        else:
            raise AssertionError('unsafe card payload accepted')
''')

    def test_checkout_creation_is_rate_limited_but_status_is_not(self):
        self.run_case(r'''
from core.http_security import SecurityMiddleware
rate_app = FastAPI()
rate_app.add_middleware(SecurityMiddleware)
@rate_app.post('/checkout/11111111-1111-4111-8111-111111111111/pix')
def limited(): return {'ok': True}
@rate_app.get('/checkout/11111111-1111-4111-8111-111111111111/status')
def polling(): return {'ok': True}
with patch('core.http_security.allow_request', return_value=(False, 17)) as limiter:
    rate_client = TestClient(rate_app)
    blocked = rate_client.post('/checkout/11111111-1111-4111-8111-111111111111/pix')
    assert blocked.status_code == 429 and blocked.headers['Retry-After'] == '17'
    assert rate_client.get('/checkout/11111111-1111-4111-8111-111111111111/status').status_code == 200
    assert limiter.call_count == 1
''')

    def test_provider_errors_are_safe_and_rejected_card_can_retry(self):
        self.run_case(r'''
with Session(engine) as db:
    limited = accepted_charge(db, 1)
    limited_client = checkout_app(db, MercadoPagoClient(
        access_token='secret', session=FakeSession([FakeResponse(429, {}, {'Retry-After':'9'})])))
    response = limited_client.post(f'/checkout/{limited.referencia_externa}/pix', json={'payment_option':'integral'})
    assert response.status_code == 429 and 'secret' not in response.text

    unavailable = accepted_charge(db, 2)
    unavailable_client = checkout_app(db, MercadoPagoClient(
        access_token='secret', session=FakeSession([FakeResponse(500, {})])))
    response = unavailable_client.post(f'/checkout/{unavailable.referencia_externa}/pix', json={'payment_option':'integral'})
    assert response.status_code == 503 and 'secret' not in response.text

    retry = accepted_charge(db, 3)
    class RetrySession(FakeSession):
        def request(self, method, url, **kwargs):
            reference = kwargs['json']['external_reference']
            status, detail, provider_id = (
                ('rejected', 'cc_rejected_other_reason', 'ORD-rejected')
                if not self.calls else ('processed', 'accredited', 'ORD-approved')
            )
            self.calls.append((method, url, kwargs))
            return FakeResponse(402 if status == 'rejected' else 201, order(
                amount='150.25', status=status, detail=detail, method='visa', pix=False,
                provider_id=provider_id, external_reference=reference))
    retry_provider = MercadoPagoClient(access_token='secret', session=RetrySession([]))
    retry_client = checkout_app(db, retry_provider)
    payload = {'payment_option':'integral', 'card_token':'token-one',
               'payment_method_id':'visa', 'installments':1}
    first = retry_client.post(f'/checkout/{retry.referencia_externa}/card', json=payload)
    assert first.status_code == 200 and first.json()['status'] == 'rejected'
    payload['card_token'] = 'token-two'
    second = retry_client.post(f'/checkout/{retry.referencia_externa}/card', json=payload)
    assert second.status_code == 200 and second.json()['status'] == 'approved'
    assert db.query(PagamentoModel).filter(PagamentoModel.cobranca_id == retry.id).count() == 2
    persisted = str(db.query(PagamentoModel).filter(PagamentoModel.cobranca_id == retry.id).all())
    assert 'token-one' not in persisted and 'token-two' not in persisted
''')

    def test_locked_submission_does_not_use_stale_payment_collection(self):
        self.run_case(r'''
with Session(engine) as db:
    current = accepted_charge(db)
    assert current.pagamentos == []
    with Session(engine) as concurrent:
        payment = finance.registrar_pagamento(
            concurrent, current.id, tipo='integral', valor='150.25', status='pendente',
            metodo='pix', provider=mp_service.PROVIDER, provider_reference='concurrent')
        payment.provider_idempotency_key = 'concurrent'
        concurrent.commit()
    try:
        checkout_service._get_or_create_attempt(db, current, tipo='entrada', metodo='cartao')
    except checkout_service.CheckoutConflito as error:
        assert 'processamento' in str(error)
    else:
        raise AssertionError('stale collection allowed a duplicate checkout attempt')
    assert db.query(PagamentoModel).filter(PagamentoModel.cobranca_id == current.id).count() == 1
''')


if __name__ == "__main__":
    unittest.main()
