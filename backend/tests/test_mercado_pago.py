"""F3.2 Mercado Pago tests; all HTTP and databases are disposable fakes."""

import unittest

import test_bootstrap_database as isolated
from test_proposta_service import SETUP


MP_SETUP = SETUP + r'''
import io
import logging
import requests
from decimal import Decimal
from sqlalchemy.orm import Session
from models import CobrancaModel, PagamentoModel
from integrations.mercado_pago import (
    MercadoPagoAuthError, MercadoPagoClient, MercadoPagoConflict,
    MercadoPagoInvalidResponse, MercadoPagoNotConfigured, MercadoPagoPayer,
    MercadoPagoRateLimited, MercadoPagoTimeout, MercadoPagoUnavailable,
    MercadoPagoValidationError, map_provider_status,
)
from models.enums.financeiro import PagamentoStatus
from services import financial_service as finance
from services import mercado_pago_service as mp_service

class FakeResponse:
    def __init__(self, status, data, headers=None):
        self.status_code = status
        self.data = data
        self.headers = headers or {}
    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

def order(amount='150.25', status='action_required', detail='waiting_transfer',
          method='pix', provider_id='ORD-1', pix=True,
          external_reference='opaque', currency='BRL'):
    payment_method = {'id': method, 'type': 'bank_transfer' if method == 'pix' else 'credit_card'}
    if pix:
        payment_method.update({
            'ticket_url': 'https://www.mercadopago.com.br/payments/ticket',
            'qr_code': 'pix-secret-code',
            'qr_code_base64': 'pix-secret-base64',
        })
    return {
        'id': provider_id,
        'external_reference': external_reference,
        'currency': currency,
        'status': status,
        'status_detail': detail,
        'total_amount': amount,
        'last_updated_date': '2026-09-20T12:00:00Z',
        'transactions': {'payments': [{
            'id': 'PAY-1', 'amount': amount, 'status': status,
            'status_detail': detail, 'payment_method': payment_method,
        }]},
    }

def charge(db, budget_id=1):
    proposal = service.criar_por_orcamento(db, budget_id)
    model = db.get(PropostaModel, proposal.id)
    model.status = 'enviada'
    db.commit()
    result = finance.criar_para_proposta(db, model)
    db.commit()
    return result
'''


class MercadoPagoTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(MP_SETUP + source)

    def test_configuration_status_mapping_and_error_categories(self):
        self.run_case(r'''
client = MercadoPagoClient(access_token='', session=FakeSession([]))
try:
    client.ensure_configured()
except MercadoPagoNotConfigured as error:
    assert str(error) == 'provider_not_configured'
else:
    raise AssertionError('missing token accepted')

assert map_provider_status('pending') == PagamentoStatus.PENDENTE
assert map_provider_status('processed', 'accredited') == PagamentoStatus.APROVADO
assert map_provider_status('rejected') == PagamentoStatus.RECUSADO
assert map_provider_status('cancelled') == PagamentoStatus.CANCELADO
assert map_provider_status('refunded') == PagamentoStatus.REEMBOLSADO
assert map_provider_status('future_status') == PagamentoStatus.PENDENTE

cases = [
    (400, MercadoPagoValidationError, {}),
    (401, MercadoPagoAuthError, {}),
    (403, MercadoPagoAuthError, {}),
    (409, MercadoPagoConflict, {}),
    (423, MercadoPagoConflict, {}),
    (429, MercadoPagoRateLimited, {'Retry-After': '7'}),
    (500, MercadoPagoUnavailable, {}),
]
for status, expected, headers in cases:
    current = MercadoPagoClient(access_token='test-token', session=FakeSession([
        FakeResponse(status, {'error': 'safe-fake'}, headers)
    ]))
    try:
        current.get_order('ORD-test')
    except expected as error:
        assert error.http_status == status
        if status == 429:
            assert error.retry_after == '7' and error.retryable
    else:
        raise AssertionError(f'HTTP {status} was accepted')

for response in [FakeResponse(200, ValueError('invalid json')), FakeResponse(200, []),
                 FakeResponse(200, {'id': 'missing-fields'})]:
    current = MercadoPagoClient(access_token='test-token', session=FakeSession([response]))
    try:
        current.get_order('ORD-test')
    except MercadoPagoInvalidResponse:
        pass
    else:
        raise AssertionError('invalid provider response accepted')
''')

    def test_pix_timeout_reuses_attempt_and_normalizes_result(self):
        self.run_case(r'''
with Session(engine) as db:
    current_charge = charge(db)
    payment = mp_service.criar_tentativa(db, current_charge.id, tipo='integral', metodo='pix')
    first_key = payment.provider_idempotency_key
    assert first_key == payment.provider_reference
    payer = MercadoPagoPayer(email='payer@example.com', identification_type='CPF',
                             identification_number='11122233344')
    session = FakeSession([
        requests.Timeout(),
        FakeResponse(201, order()),
    ])
    client = MercadoPagoClient(access_token='test-token', session=session)
    try:
        mp_service.enviar_pix(db, payment.id, payer=payer, client=client, request_id='request-safe')
    except MercadoPagoTimeout as error:
        assert error.payment_id == payment.id and error.retryable
    else:
        raise AssertionError('timeout hidden')
    persisted = db.get(PagamentoModel, payment.id)
    assert persisted.status == 'pendente' and persisted.provider_order_id is None
    result = mp_service.enviar_pix(db, payment.id, payer=payer, client=client)
    assert result.payment_id == payment.id
    assert result.result.status == PagamentoStatus.PENDENTE
    assert result.result.pix.qr_code == 'pix-secret-code'
    assert result.result.pix.ticket_url.startswith('https://')
    persisted = db.get(PagamentoModel, payment.id)
    assert persisted.provider_order_id == 'ORD-1'
    assert persisted.provider_idempotency_key == first_key
    assert [call[2]['headers']['X-Idempotency-Key'] for call in session.calls] == [first_key, first_key]
    assert session.calls[0][2]['json']['total_amount'] == '150.25'
    assert session.calls[0][2]['json']['external_reference'] == first_key
    assert session.calls[0][2]['json']['payer']['identification']['number'] == '11122233344'
    second = mp_service.criar_tentativa(db, current_charge.id, tipo='integral', metodo='pix')
    assert second.provider_idempotency_key != first_key
    assert db.query(PagamentoModel).count() == 2
''')

    def test_card_token_is_transient_and_amount_is_backend_controlled(self):
        self.run_case(r'''
card_token = 'temporary-card-token-sentinel'
with Session(engine) as db:
    current_charge = charge(db)
    session = FakeSession([FakeResponse(201, order(
        status='processed', detail='accredited', method='visa', pix=False,
    ))])
    client = MercadoPagoClient(access_token='access-token-sentinel', session=session)
    result = mp_service.criar_cartao(
        db, current_charge.id, tipo='integral', payer=MercadoPagoPayer(email='payer@example.com'),
        card_token=card_token, payment_method_id='visa', installments=2, client=client,
    )
    payload = session.calls[0][2]['json']
    method = payload['transactions']['payments'][0]['payment_method']
    assert payload['total_amount'] == '150.25'
    assert method == {'id': 'visa', 'type': 'credit_card', 'token': card_token, 'installments': 2}
    payment = db.get(PagamentoModel, result.payment_id)
    assert payment.status == 'aprovado' and payment.provider_order_id == 'ORD-1'
    assert payment.cobranca.status == 'paga'
    persisted = '|'.join(str(value) for value in [
        payment.metodo, payment.provider, payment.provider_order_id,
        payment.provider_reference, payment.provider_idempotency_key,
    ])
    assert card_token not in persisted and 'access-token-sentinel' not in persisted

for invalid in [0, -1, 25, True]:
    client = MercadoPagoClient(access_token='test-token', session=FakeSession([]))
    try:
        client.create_card(amount=Decimal('1.00'), external_reference='opaque',
            idempotency_key='stable', payer=MercadoPagoPayer(email='payer@example.com'),
            card_token='token', payment_method_id='visa', installments=invalid)
    except MercadoPagoValidationError:
        pass
    else:
        raise AssertionError(f'invalid installments accepted: {invalid}')
''')

    def test_partial_amounts_precision_and_lookup(self):
        self.run_case(r'''
with Session(engine) as db:
    current_charge = charge(db)
    entry_session = FakeSession([FakeResponse(201, order(
        amount='75.12', status='processed', detail='accredited', provider_id='ORD-entry'
    ))])
    entry = mp_service.criar_pix(
        db, current_charge.id, tipo='entrada', payer=MercadoPagoPayer(email='payer@example.com'),
        client=MercadoPagoClient(access_token='test-token', session=entry_session),
    )
    assert db.get(PagamentoModel, entry.payment_id).valor == Decimal('75.12')
    assert db.get(CobrancaModel, current_charge.id).status == 'parcialmente_paga'
    balance = mp_service.criar_tentativa(db, current_charge.id, tipo='saldo', metodo='pix')
    assert balance.valor == Decimal('75.13')

lookup_session = FakeSession([FakeResponse(200, order(
    amount='99.90', status='processed', detail='accredited', provider_id='ORD-lookup'
))])
lookup = mp_service.consultar_order(
    'ORD-lookup', client=MercadoPagoClient(access_token='test-token', session=lookup_session)
)
assert lookup.provider_id == 'ORD-lookup' and lookup.amount == Decimal('99.90')
assert lookup.status == PagamentoStatus.APROVADO
assert lookup_session.calls[0][0:2] == ('GET', 'https://api.mercadopago.com/v1/orders/ORD-lookup')

for value in ['0.01', '0.10', '99.90', '99.99', '100.00', '198.00', '199.99']:
    fake = FakeSession([FakeResponse(201, order(amount=value))])
    client = MercadoPagoClient(access_token='test-token', session=fake)
    parsed = client.create_pix(amount=Decimal(value), external_reference='opaque',
        idempotency_key='stable-key', payer=MercadoPagoPayer(email='payer@example.com'))
    assert fake.calls[0][2]['json']['total_amount'] == value
    assert parsed.amount == Decimal(value)
''')

    def test_safe_logging_and_no_local_attempt_without_configuration(self):
        self.run_case(r'''
with Session(engine) as db:
    current_charge = charge(db)
    try:
        mp_service.criar_pix(
            db, current_charge.id, tipo='integral', payer=MercadoPagoPayer(
                email='private@example.com', identification_type='CPF',
                identification_number='99988877766'),
            client=MercadoPagoClient(access_token='', session=FakeSession([])),
        )
    except MercadoPagoNotConfigured:
        pass
    else:
        raise AssertionError('unconfigured provider accepted')
    assert db.query(PagamentoModel).count() == 0

    payment = mp_service.criar_tentativa(db, current_charge.id, tipo='integral', metodo='cartao')
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    mp_service.logger.addHandler(handler)
    mp_service.logger.setLevel(logging.WARNING)
    try:
        mp_service.enviar_cartao(
            db, payment.id, payer=MercadoPagoPayer(
                email='private@example.com', identification_type='CPF',
                identification_number='99988877766'),
            card_token='private-card-token', payment_method_id='visa', installments=1,
            client=MercadoPagoClient(access_token='private-access-token',
                                     session=FakeSession([requests.Timeout()])),
            request_id='request-safe',
        )
    except MercadoPagoTimeout:
        pass
    finally:
        mp_service.logger.removeHandler(handler)
    output = stream.getvalue()
    assert 'provider_timeout' in output and f'payment_id={payment.id}' in output
    for secret in ['private@example.com', '99988877766', 'private-card-token',
                   'private-access-token', 'pix-secret-code']:
        assert secret not in output
''')

    def test_migration_upgrade_downgrade_upgrade_matches_metadata(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

config = migration_config()
head = bootstrap(engine)
assert head == 'd4e6f8a1b2c3'
command.downgrade(config, 'c4f8a2d19e73')
columns = {column['name'] for column in inspect(engine).get_columns('pagamentos')}
assert 'provider_idempotency_key' not in columns
command.upgrade(config, 'head')
columns = {column['name'] for column in inspect(engine).get_columns('pagamentos')}
assert 'provider_idempotency_key' in columns
assert 'provider_order_id' in columns
assert 'provider_payment_id' not in columns
assert 'provider_webhook_events' in inspect(engine).get_table_names()
with engine.connect() as connection:
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
assert ScriptDirectory.from_config(config).get_current_head() == head
''')


if __name__ == "__main__":
    unittest.main()
