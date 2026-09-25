"""F3.3 webhook and reconciliation tests with disposable fakes only."""

import unittest

import test_bootstrap_database as isolated
from test_mercado_pago import MP_SETUP


WEBHOOK_SETUP = MP_SETUP + r'''
import hashlib
import hmac
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func
from models import ProviderWebhookEventModel
from integrations.mercado_pago import (
    MercadoPagoRateLimited, MercadoPagoTimeout, MercadoPagoUnavailable,
    ProviderPaymentResult,
)
from routers.webhooks import get_mercado_pago_client, router as webhook_router
from services import mercado_pago_webhook_service as webhook_service
from database import get_db

config.settings.MERCADO_PAGO_WEBHOOK_SECRET = 'webhook-test-secret'

class ResultClient:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []
    def get_order(self, provider_id):
        self.calls.append(provider_id)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

def provider_result(payment, *, provider_id='ORD-1', status='processed',
                    detail='accredited', amount=None, currency='BRL', reference=None):
    return ProviderPaymentResult(
        provider_id=provider_id,
        external_reference=payment.provider_reference if reference is None else reference,
        currency=currency,
        status=map_provider_status(status, detail),
        provider_status=status,
        status_detail=detail,
        method='pix',
        amount=Decimal(str(amount if amount is not None else payment.valor)),
        approved_at=None,
    )

def payment_attempt(db, *, provider_order_id=None, budget_id=1, tipo='integral'):
    current_charge = charge(db, budget_id)
    payment = mp_service.criar_tentativa(
        db, current_charge.id, tipo=tipo, metodo='pix'
    )
    payment.provider_order_id = provider_order_id
    db.commit()
    db.refresh(payment)
    return payment

def signature(resource_id, request_id='request-1', timestamp='1726826886'):
    manifest = f'id:{resource_id.lower()};request-id:{request_id};ts:{timestamp};'
    digest = hmac.new(
        config.settings.MERCADO_PAGO_WEBHOOK_SECRET.encode(),
        manifest.encode(), hashlib.sha256,
    ).hexdigest()
    return f'ts={timestamp},v1={digest}'

def webhook_app(provider):
    app = FastAPI()
    app.include_router(webhook_router)
    def override_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_mercado_pago_client] = lambda: provider
    return TestClient(app)

def post_webhook(client, resource_id='ORD-1', *, request_id='request-1',
                 timestamp='1726826886', event_type='order', body=None, sig=None):
    payload = body if body is not None else {
        'id': 'event-1', 'type': event_type, 'action': 'order.updated',
        'data': {'id': resource_id},
    }
    return client.post(
        '/webhooks/mercado-pago',
        params={'data.id': resource_id, 'type': event_type},
        headers={
            'x-request-id': request_id,
            'x-signature': sig or signature(resource_id, request_id, timestamp),
        },
        json=payload,
    )
'''


class MercadoPagoWebhookTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(WEBHOOK_SETUP + source)

    def test_signature_is_required_and_verified_before_persistence(self):
        self.run_case(r'''
with Session(engine) as db:
    payment = payment_attempt(db)
    provider = ResultClient(provider_result(payment))
client = webhook_app(provider)
response = post_webhook(
    client,
    sig='ts=1726826886,v1=' + '0' * 64,
    body={
        'id': 'forged', 'type': 'order', 'status': 'approved',
        'data': {'id': 'ORD-1'},
    },
)
assert response.status_code == 401
assert provider.calls == []
response = client.post(
    '/webhooks/mercado-pago',
    params={'data.id': 'ORD-1', 'type': 'order'},
    json={'type': 'order', 'data': {'id': 'ORD-1'}},
)
assert response.status_code == 401
with Session(engine) as db:
    assert db.scalar(select(func.count()).select_from(ProviderWebhookEventModel)) == 0

valid_signature = signature('ORD-1')
config.settings.MERCADO_PAGO_WEBHOOK_SECRET = None
response = post_webhook(client, sig=valid_signature)
assert response.status_code == 503
assert provider.calls == []
with Session(engine) as db:
    assert db.scalar(select(func.count()).select_from(ProviderWebhookEventModel)) == 0
''')

    def test_authoritative_lookup_timeout_recovery_and_duplicate_delivery(self):
        self.run_case(r'''
with Session(engine) as db:
    payment = payment_attempt(db)
    payment_id = payment.id
    result = provider_result(payment)
provider = ResultClient(result)
client = webhook_app(provider)
body = {
    'id': 'event-1', 'type': 'order', 'action': 'order.updated',
    'data': {'id': 'ORD-1'}, 'status': 'pending',
}
first = post_webhook(client, body=body)
assert first.status_code == 200 and first.json() == {'status': 'processed', 'duplicate': False}
for _ in range(9):
    duplicate = post_webhook(client, body=body)
    assert duplicate.status_code == 200
    assert duplicate.json() == {'status': 'processed', 'duplicate': True}
assert provider.calls == ['ORD-1']
with Session(engine) as db:
    payment = db.get(PagamentoModel, payment_id)
    assert payment.provider_order_id == 'ORD-1'
    assert payment.status == 'aprovado'
    assert payment.cobranca.status == 'paga'
    assert payment.reconciliation_status is None
    assert db.scalar(select(func.count()).select_from(ProviderWebhookEventModel)) == 1
''')

    def test_body_cannot_forge_approval(self):
        self.run_case(r'''
with Session(engine) as db:
    payment = payment_attempt(db, provider_order_id='ORD-pending')
    payment_id = payment.id
    authoritative = provider_result(
        payment, provider_id='ORD-pending', status='pending', detail='waiting_transfer'
    )
client = webhook_app(ResultClient(authoritative))
response = post_webhook(
    client,
    'ORD-pending',
    body={
        'id': 'event-forged', 'type': 'order', 'action': 'order.updated',
        'data': {'id': 'ORD-pending'}, 'status': 'approved',
    },
)
assert response.status_code == 200
with Session(engine) as db:
    payment = db.get(PagamentoModel, payment_id)
    assert payment.status == 'pendente'
    assert payment.cobranca.status == 'pendente'
''')

    def test_out_of_order_delivery_and_full_refund_do_not_regress(self):
        self.run_case(r'''
with Session(engine) as db:
    payment = payment_attempt(db, provider_order_id='ORD-state')
    payment.status = 'aprovado'
    payment.aprovado_em = datetime.now(timezone.utc)
    finance.sincronizar_status(payment.cobranca)
    db.commit()
    payment_id = payment.id
    pending = provider_result(
        payment, provider_id='ORD-state', status='pending', detail='waiting_transfer'
    )
    refunded = provider_result(
        payment, provider_id='ORD-state', status='refunded', detail='refunded'
    )
provider = ResultClient(pending, refunded)
client = webhook_app(provider)
assert post_webhook(client, 'ORD-state', request_id='request-old').status_code == 200
with Session(engine) as db:
    assert db.get(PagamentoModel, payment_id).status == 'aprovado'
assert post_webhook(client, 'ORD-state', request_id='request-refund').status_code == 200
with Session(engine) as db:
    payment = db.get(PagamentoModel, payment_id)
    assert payment.status == 'reembolsado' and payment.reembolsado_em is not None
    assert payment.cobranca.status == 'pendente'
''')

    def test_partial_refund_chargeback_and_identity_mismatches_are_conflicts(self):
        self.run_case(r'''
cases = [
    ('ORD-partial', 'processed', 'partially_refunded', None, 'BRL', None,
     'partial_refund_unsupported'),
    ('ORD-chargeback', 'charged_back', 'settled', None, 'BRL', None,
     'chargeback_unsupported'),
    ('ORD-reference', 'processed', 'accredited', None, 'BRL', 'wrong-reference',
     'external_reference_mismatch'),
    ('ORD-amount', 'processed', 'accredited', '149.99', 'BRL', None,
     'amount_mismatch'),
    ('ORD-currency', 'processed', 'accredited', None, 'USD', None,
     'currency_mismatch'),
]
with Session(engine) as db:
    db.add(OrcamentoModel(
        id=5, nome_cliente='Cliente Teste', email='teste@example.com',
        servico='Mixagem', valor_total=150.25, detalhes='Pedido original',
        link_guia='https://example.com/guia', produtor_id=1,
    ))
    db.commit()
for index, (order_id, status, detail, amount, currency, reference, reason) in enumerate(cases, 1):
    with Session(engine) as db:
        payment = payment_attempt(db, provider_order_id=order_id, budget_id=index)
        payment_id = payment.id
        result = provider_result(
            payment, provider_id=order_id, status=status, detail=detail,
            amount=amount, currency=currency, reference=reference,
        )
    response = post_webhook(
        webhook_app(ResultClient(result)), order_id, request_id=f'request-{index}'
    )
    assert response.status_code == 200 and response.json()['status'] == 'conflict'
    with Session(engine) as db:
        persisted = db.get(PagamentoModel, payment_id)
        assert persisted.status == 'pendente'
        assert persisted.reconciliation_status == 'conflict'
        assert persisted.reconciliation_reason == reason

with Session(engine) as db:
    payment = db.get(PagamentoModel, 1)
    mismatch = provider_result(payment, provider_id='ORD-other')
response = post_webhook(
    webhook_app(ResultClient(mismatch)), 'ORD-partial', request_id='request-id-mismatch'
)
assert response.status_code == 200 and response.json()['status'] == 'conflict'
with Session(engine) as db:
    assert db.get(PagamentoModel, 1).status == 'pendente'
''')

    def test_missing_order_requires_reconciliation_without_provider_call(self):
        self.run_case(r'''
with Session(engine) as db:
    payment = payment_attempt(db)
    provider = ResultClient()
    try:
        mp_service.reconcile_payment(db, payment.id, client=provider)
    except mp_service.ReconciliationRequired as error:
        assert error.reason == 'missing_provider_order_id'
    else:
        raise AssertionError('missing provider order was accepted')
    assert provider.calls == []
    persisted = db.get(PagamentoModel, payment.id)
    assert persisted.reconciliation_status == 'required'
    assert persisted.reconciliation_reason == 'missing_provider_order_id'

with Session(engine) as db:
    known = payment_attempt(db, provider_order_id='ORD-known', budget_id=2)
    known_id = known.id
    provider = ResultClient(provider_result(known, provider_id='ORD-known'))
    reconciled = mp_service.reconcile_payment(db, known.id, client=provider)
    assert reconciled.changed and reconciled.current_status == 'aprovado'
    assert provider.calls == ['ORD-known']
with Session(engine) as db:
    assert db.get(PagamentoModel, known_id).status == 'aprovado'
''')

    def test_two_sessions_reconcile_idempotently(self):
        self.run_case(r'''
with Session(engine) as db:
    payment = payment_attempt(db, provider_order_id='ORD-concurrent')
    payment_id = payment.id
    first_result = provider_result(payment, provider_id='ORD-concurrent')
    second_result = provider_result(payment, provider_id='ORD-concurrent')
with Session(engine) as first_db, Session(engine) as second_db:
    first = mp_service.reconcile_order(
        first_db, 'ORD-concurrent', client=ResultClient(first_result)
    )
    second = mp_service.reconcile_order(
        second_db, 'ORD-concurrent', client=ResultClient(second_result)
    )
assert first.changed and first.current_status == 'aprovado'
assert not second.changed and second.outcome == 'unchanged'
with Session(engine) as db:
    assert db.scalar(select(func.count()).select_from(PagamentoModel)) == 1
    payment = db.get(PagamentoModel, payment_id)
    assert payment.status == 'aprovado' and payment.cobranca.status == 'paga'
''')

    def test_irrelevant_event_is_ignored_and_temporary_failure_is_retried(self):
        self.run_case(r'''
ignored_provider = ResultClient()
ignored = post_webhook(
    webhook_app(ignored_provider), 'ORD-ignore', event_type='payment',
    request_id='request-ignore',
    body={'id': 'event-ignore', 'type': 'payment', 'data': {'id': 'ORD-ignore'}},
)
assert ignored.status_code == 200 and ignored.json()['status'] == 'ignored'
assert ignored_provider.calls == []

errors = [MercadoPagoTimeout(), MercadoPagoRateLimited(http_status=429),
          MercadoPagoUnavailable(http_status=500)]
for index, error in enumerate(errors, 1):
    order_id = f'ORD-retry-{index}'
    with Session(engine) as db:
        payment = payment_attempt(db, provider_order_id=order_id, budget_id=index)
        result = provider_result(payment, provider_id=order_id)
    provider = ResultClient(error, result)
    client = webhook_app(provider)
    request_id = f'request-retry-{index}'
    failed = post_webhook(client, order_id, request_id=request_id)
    assert failed.status_code == 503
    retried = post_webhook(client, order_id, request_id=request_id)
    assert retried.status_code == 200 and retried.json()['status'] == 'processed'
    with Session(engine) as db:
        event = db.scalar(select(ProviderWebhookEventModel).where(
            ProviderWebhookEventModel.resource_id == order_id
        ))
        assert event.status == 'processed' and event.error_category is None
''')

    def test_body_identity_and_database_failure_return_non_success(self):
        self.run_case(r'''
from unittest.mock import patch
from sqlalchemy.exc import OperationalError
provider = ResultClient()
client = webhook_app(provider)
response = post_webhook(
    client,
    body={'id': 'event', 'type': 'order', 'data': {'id': 'ORD-forged'}},
)
assert response.status_code == 400 and provider.calls == []
with patch.object(
    webhook_service,
    'process_webhook',
    side_effect=OperationalError('statement', {}, Exception('synthetic')),
):
    response = post_webhook(client, request_id='request-database')
assert response.status_code == 503 and provider.calls == []
''')

    def test_migration_upgrade_downgrade_upgrade_matches_metadata(self):
        isolated.BootstrapTests().run_case(r'''
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

config = migration_config()
head = bootstrap(engine)
assert head == 'f2a8c4e6d901'
command.downgrade(config, 'd9e4b7a1c2f6')
columns = {column['name'] for column in inspect(engine).get_columns('pagamentos')}
assert 'provider_payment_id' in columns and 'provider_order_id' not in columns
assert 'provider_webhook_events' not in inspect(engine).get_table_names()
command.upgrade(config, 'head')
columns = {column['name'] for column in inspect(engine).get_columns('pagamentos')}
assert 'provider_order_id' in columns and 'provider_payment_id' not in columns
assert 'provider_webhook_events' in inspect(engine).get_table_names()
with engine.connect() as connection:
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
assert ScriptDirectory.from_config(config).get_current_head() == head
''')


if __name__ == "__main__":
    unittest.main()
