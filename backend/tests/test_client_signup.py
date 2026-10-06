"""Public client signup lifecycle on a disposable database with fake email."""

import unittest

import test_bootstrap_database as isolated
from test_proposta_comercial import SETUP as COMMERCIAL_SETUP

SETUP = COMMERCIAL_SETUP + r'''
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from core.security import verify_password
from models import ClienteAcessoModel, ClienteModel
from pydantic import ValidationError
from schemas.client_access import ClientInviteActivation, ClientSignupRequest
from services import client_access_service as access

config.settings.PUBLIC_FRONTEND_URL = 'http://localhost:4173'

def signup_data(email='new-client@example.com', telefone='11999990000'):
    return ClientSignupRequest(
        nome='Novo Cliente',
        email=email,
        telefone=telefone,
        privacy_accepted=True,
    )

def raw_token(call):
    activation_url = call.call_args.args[1]
    return parse_qs(urlparse(activation_url).query)['token'][0]
'''


class ClientSignupTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_new_signup_activation_and_empty_commercial_context(self):
        self.run_case(r'''
with Session(engine) as db:
    initial_clients = db.query(ClienteModel).count()
    with patch.object(EmailService, 'enviar_confirmacao_cadastro', return_value={'id':'signup-message'}) as email:
        result = access.request_signup(db, signup_data(), '127.0.0.1', 'signup-1')
    assert result['accepted'] is True and 'puderem' in result['message']
    assert db.query(ClienteModel).count() == initial_clients + 1
    pending = db.query(ClienteAcessoModel).filter_by(origem='public_signup').one()
    client = db.get(ClienteModel, pending.cliente_id)
    token = raw_token(email)
    assert pending.token_hash == access._hash(token) and token not in pending.token_hash
    assert pending.token_finalidade == 'verificacao' and pending.privacy_accepted_at
    assert pending.request_fingerprint_hash and len(pending.request_fingerprint_hash) == 64
    assert access.token_state(db, token, 'validation-source') == 'valido'

    user = access.activate(db, ClientInviteActivation(
        token=token, username='new_client', password='secure-password'
    ), 'activation-source', 'signup-activate')
    assert user.role == 'cliente' and user.is_admin is False and user.ativo is True
    assert user.cliente_id == client.id and verify_password('secure-password', user.password_hash)
    assert client.orcamentos == [] and client.cobrancas == []
    assert db.query(ClienteAcessoModel).one().email_verified_at
    actions = [row.action for row in db.query(AuditLogModel).all()]
    assert 'client_access.signup_requested' in actions
    assert 'client_access.signup_activated' in actions
''')

    def test_commercial_identity_and_existing_account_do_not_get_claimed(self):
        self.run_case(r'''
with Session(engine) as db:
    commercial = ClienteModel(
        nome='Cliente Comercial', email='teste@example.com',
        telefone='11988887777', observacoes='', ativo=True,
    )
    db.add(commercial)
    db.commit()
    before_clients = db.query(ClienteModel).count()
    with patch.object(EmailService, 'enviar_confirmacao_cadastro') as email:
        first = access.request_signup(
            db,
            signup_data(email='TESTE@example.com', telefone=commercial.telefone),
            'source-commercial',
            'signup-commercial',
        )
    assert first == access._generic_signup_response()
    assert email.call_count == 0
    assert db.query(ClienteModel).count() == before_clients
    assert db.query(ClienteAcessoModel).count() == 0
    assert db.query(AuditLogModel).filter_by(
        action='client_access.signup_reconciliation_required'
    ).count() == 1

    commercial_user = UsuarioModel(
        username='existing_client', password_hash='not-used', role='cliente',
        is_admin=False, ativo=True, cliente_id=commercial.id,
    )
    db.add(commercial_user)
    db.commit()
    with patch.object(EmailService, 'enviar_confirmacao_cadastro') as email:
        second = access.request_signup(
            db,
            signup_data(email=commercial.email, telefone=None),
            'source-existing',
            'signup-existing',
        )
    assert second == first and email.call_count == 0
    assert db.query(UsuarioModel).filter_by(cliente_id=commercial.id).count() == 1
''')

    def test_pending_resend_rotates_token_and_purpose_isolated(self):
        self.run_case(r'''
with Session(engine) as db:
    with patch.object(EmailService, 'enviar_confirmacao_cadastro', return_value={'id':'first'}) as first:
        access.request_signup(db, signup_data(), 'source-a', 'signup-a')
    old_token = raw_token(first)
    with patch.object(EmailService, 'enviar_confirmacao_cadastro') as duplicate:
        access.request_signup(db, signup_data(), 'source-b', 'signup-b')
    assert duplicate.call_count == 0
    with patch.object(EmailService, 'enviar_confirmacao_cadastro', return_value={'id':'second'}) as second:
        access.resend_signup(db, 'NEW-CLIENT@example.com', 'source-c', 'signup-c')
    new_token = raw_token(second)
    assert old_token != new_token
    try:
        access.token_state(db, old_token, 'old-token')
    except access.ClientAccessInvalid:
        pass
    else:
        raise AssertionError('old signup token survived rotation')
    assert access.token_state(db, new_token, 'new-token') == 'valido'
    pending = db.query(ClienteAcessoModel).one()
    pending.token_finalidade = 'convite'
    db.commit()
    try:
        access.token_state(db, new_token, 'wrong-purpose')
    except access.ClientAccessInvalid:
        pass
    else:
        raise AssertionError('signup token accepted with invite purpose')
''')

    def test_delivery_failure_stays_pending_and_recoverable(self):
        self.run_case(r'''
with Session(engine) as db:
    with patch.object(EmailService, 'enviar_confirmacao_cadastro', side_effect=RuntimeError('private-provider-error')):
        result = access.request_signup(db, signup_data(), 'source-failure', 'signup-failure')
    assert result == access._generic_signup_response()
    pending = db.query(ClienteAcessoModel).one()
    assert pending.usuario_id is None and pending.last_sent_at is None and pending.send_count == 0
    with patch.object(EmailService, 'enviar_confirmacao_cadastro', return_value={'id':'recovered'}) as recovered:
        access.resend_signup(db, 'new-client@example.com', 'source-retry', 'signup-retry')
    assert recovered.call_count == 1
    pending = db.query(ClienteAcessoModel).one()
    assert pending.last_sent_at and pending.send_count == 1
''')

    def test_schema_mass_assignment_rate_limit_and_cleanup(self):
        self.run_case(r'''
try:
    ClientSignupRequest(
        nome='Ataque', email='attack@example.com', privacy_accepted=True,
        role='admin', is_admin=True, cliente_id=1,
    )
except ValidationError:
    pass
else:
    raise AssertionError('privilege fields accepted')

with Session(engine) as db:
    for index in range(5):
        access.enforce_rate_limit(
            db, action='signup', key='same-identity', limit=5,
            window=timedelta(hours=1),
        )
    try:
        access.enforce_rate_limit(
            db, action='signup', key='same-identity', limit=5,
            window=timedelta(hours=1),
        )
    except access.ClientAccessRateLimited:
        pass
    else:
        raise AssertionError('signup rate limit bypassed')

with Session(engine) as db:
    with patch.object(EmailService, 'enviar_confirmacao_cadastro', return_value={'id':'cleanup'}):
        access.request_signup(db, signup_data(email='cleanup@example.com'), 'cleanup-source', 'cleanup')
    pending = db.query(ClienteAcessoModel).one()
    client_id = pending.cliente_id
    pending.token_expires_at = access._now() - timedelta(days=31)
    db.commit()
    deleted_accesses, deleted_limits, deleted_clients = access.cleanup_expired(db)
    assert deleted_accesses == 1 and deleted_clients == 1
    assert db.get(ClienteModel, client_id) is None
''')


if __name__ == "__main__":
    unittest.main()
