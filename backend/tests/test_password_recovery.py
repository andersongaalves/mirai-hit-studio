"""Client-only password recovery on disposable databases with fake email."""

import unittest

import test_bootstrap_database as isolated
from test_client_access import SETUP as CLIENT_ACCESS_SETUP

SETUP = CLIENT_ACCESS_SETUP + r'''
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import FastAPI

from core.security import create_access_token, decode_token, verify_password
from database import get_db
from models import AuthRateLimitModel
from routers.auth import router as auth_router
from routers.client_access import router as client_access_router
from schemas.client_access import PasswordRecoveryRequest, PasswordResetRequest

app = FastAPI()
app.include_router(auth_router)
app.include_router(client_access_router)

def session():
    with Session(engine) as db:
        yield db

app.dependency_overrides[get_db] = session

def active_account(db):
    proposal = accepted_proposal(db)
    actor = db.get(UsuarioModel, 1)
    with patch.object(EmailService, 'enviar_convite_cliente', return_value={'id':'invite'}) as sent:
        access.invite(db, proposal.id, actor, 'active-invite', 'active-source')
    token = raw_token(sent)
    user = access.activate(
        db,
        ClientInviteActivation(
            token=token,
            username='recovery_client',
            password='old-secure-password',
        ),
        'active-activation',
        'active-request',
    )
    return db.get(ClienteAcessoModel, db.query(ClienteAcessoModel).one().id), user

def recovery_token(call):
    return parse_qs(urlparse(call.call_args.args[1]).query)['token'][0]
'''


class PasswordRecoveryTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_full_reset_revokes_old_jwt_and_is_single_use(self):
        self.run_case(r'''
with Session(engine) as db:
    saved_access, user = active_account(db)
    old_jwt = create_access_token({'sub': user.username, 'av': user.auth_version})
    email = saved_access.email_normalizado

async def check():
    with patch.object(EmailService, 'enviar_recuperacao_senha', return_value={'id':'recovery-message'}) as sent:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            requested = await client.post('/auth/password-recovery', json={'email': email})
            assert requested.status_code == 202, requested.text
            missing = await client.post(
                '/auth/password-recovery', json={'email': 'missing@example.com'}
            )
            assert missing.status_code == 202
            assert missing.json() == requested.json()
            token = recovery_token(sent)
            assert token not in access._hash(token)
            assert (await client.post('/cliente-acessos/validar', json={'token': token})).status_code == 422
            reset = await client.post('/auth/password-recovery/reset', json={
                'token': token, 'password': 'new-secure-password',
            })
            assert reset.status_code == 200, reset.text
            assert reset.json() == {'reset': True, 'login_url': '/acesso'}
            replay = await client.post('/auth/password-recovery/reset', json={
                'token': token, 'password': 'another-secure-password',
            })
            assert replay.status_code == 409
            old_session = await client.get('/auth/me', headers={'Authorization': 'Bearer ' + old_jwt})
            assert old_session.status_code == 401
            assert (await client.post('/auth/login', json={
                'username':'recovery_client', 'password':'old-secure-password',
            })).status_code == 401
            fresh = await client.post('/auth/login', json={
                'username':'recovery_client', 'password':'new-secure-password',
            })
            assert fresh.status_code == 200, fresh.text
            payload = decode_token(fresh.json()['access_token'])
            assert payload['av'] == 1
network_guard.stop()
asyncio.run(check())

with Session(engine) as db:
    user = db.query(UsuarioModel).filter_by(username='recovery_client').one()
    saved_access = db.query(ClienteAcessoModel).one()
    assert user.auth_version == 1
    assert saved_access.token_consumed_at is not None
    assert verify_password('new-secure-password', user.password_hash)
    actions = [row.action for row in db.query(AuditLogModel).all()]
    assert 'client_access.recovery_requested' in actions
    assert 'client_access.password_reset_completed' in actions
    assert 'client_access.recovery_token_rejected' in actions
''')

    def test_generic_response_rotation_delivery_failure_and_eligibility(self):
        self.run_case(r'''
with Session(engine) as db:
    saved_access, user = active_account(db)
    email = saved_access.email_normalizado
    expected = access._generic_recovery_response()

    with patch.object(EmailService, 'enviar_recuperacao_senha', return_value={'id':'first'}) as first:
        assert access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'source-1', 'request-1'
        ) == expected
    first_token = recovery_token(first)
    with patch.object(EmailService, 'enviar_recuperacao_senha', return_value={'id':'second'}) as second:
        assert access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'source-2', 'request-2'
        ) == expected
    second_token = recovery_token(second)
    assert first_token != second_token
    try:
        access.reset_password(
            db,
            PasswordResetRequest(token=first_token, password='unused-password'),
            'old-token-source',
            'old-token-request',
        )
    except access.ClientAccessInvalid:
        pass
    else:
        raise AssertionError('rotated token accepted')

    with patch.object(EmailService, 'enviar_recuperacao_senha', side_effect=RuntimeError('provider-private')):
        assert access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'source-3', 'request-3'
        ) == expected
    saved = db.query(ClienteAcessoModel).one()
    assert saved.last_sent_at is not None
    assert db.query(AuditLogModel).filter_by(
        action='client_access.recovery_delivery_failed'
    ).count() == 1

    db.query(AuthRateLimitModel).delete()
    db.commit()
    with patch.object(EmailService, 'enviar_recuperacao_senha') as blocked:
        assert access.request_password_recovery(
            db,
            PasswordRecoveryRequest(email='missing@example.com'),
            'missing-source',
            'missing-request',
        ) == expected
    assert blocked.call_count == 0

    user.ativo = False
    db.commit()
    db.query(AuthRateLimitModel).delete()
    db.commit()
    with patch.object(EmailService, 'enviar_recuperacao_senha') as blocked:
        assert access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'inactive-source', 'inactive-request'
        ) == expected
    assert blocked.call_count == 0

    user.ativo = True
    user.is_admin = True
    db.commit()
    db.query(AuthRateLimitModel).delete()
    db.commit()
    with patch.object(EmailService, 'enviar_recuperacao_senha') as blocked:
        assert access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'admin-source', 'admin-request'
        ) == expected
    assert blocked.call_count == 0

    user.is_admin = False
    saved.email_verified_at = None
    db.commit()
    db.query(AuthRateLimitModel).delete()
    db.commit()
    with patch.object(EmailService, 'enviar_recuperacao_senha') as blocked:
        assert access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'unverified-source', 'unverified-request'
        ) == expected
    assert blocked.call_count == 0

    saved.email_verified_at = access._now()
    other_client = ClienteModel(
        nome='Outro Cliente', email='other@example.com', observacoes='', ativo=True,
    )
    db.add(other_client)
    db.flush()
    user.cliente_id = other_client.id
    db.commit()
    db.query(AuthRateLimitModel).delete()
    db.commit()
    with patch.object(EmailService, 'enviar_recuperacao_senha') as blocked:
        assert access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'mismatch-source', 'mismatch-request'
        ) == expected
    assert blocked.call_count == 0

    user.cliente_id = saved.cliente_id
    user.role = 'produtor'
    user.cliente_id = None
    db.commit()
    db.query(AuthRateLimitModel).delete()
    db.commit()
    with patch.object(EmailService, 'enviar_recuperacao_senha') as blocked:
        assert access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'role-source', 'role-request'
        ) == expected
    assert blocked.call_count == 0
''')

    def test_pending_signup_and_invite_are_not_overwritten(self):
        self.run_case(r'''
with Session(engine) as db:
    actor = db.get(UsuarioModel, 1)
    expected = access._generic_recovery_response()
    now = datetime.now(timezone.utc)
    pending_invite_client = ClienteModel(
        nome='Pending Invite', email='pending-invite@example.com', observacoes='', ativo=True,
    )
    pending_signup_client = ClienteModel(
        nome='Pending Signup', email='pending-signup@example.com', observacoes='', ativo=True,
    )
    commercial_client = ClienteModel(
        nome='Commercial Only', email='commercial-only@example.com', observacoes='', ativo=True,
    )
    db.add_all([pending_invite_client, pending_signup_client, commercial_client])
    db.flush()
    invite_token = 'pending-invite-token-with-sufficient-entropy-123456789'
    signup_token = 'pending-signup-token-with-sufficient-entropy-123456789'
    invite_hash = access._hash(invite_token)
    signup_hash = access._hash(signup_token)
    db.add_all([
        ClienteAcessoModel(
            cliente_id=pending_invite_client.id,
            email_normalizado=pending_invite_client.email,
            origem='admin_invite',
            token_finalidade='convite',
            token_hash=invite_hash,
            token_expires_at=now + timedelta(hours=1),
            invited_by_user_id=actor.id,
        ),
        ClienteAcessoModel(
            cliente_id=pending_signup_client.id,
            email_normalizado=pending_signup_client.email,
            origem='public_signup',
            token_finalidade='verificacao',
            token_hash=signup_hash,
            token_expires_at=now + timedelta(hours=1),
            privacy_accepted_at=now,
        ),
    ])
    db.commit()

    for index, email in enumerate((
        pending_invite_client.email,
        pending_signup_client.email,
        commercial_client.email,
    )):
        with patch.object(EmailService, 'enviar_recuperacao_senha') as blocked:
            assert access.request_password_recovery(
                db,
                PasswordRecoveryRequest(email=email),
                f'pending-source-{index}',
                f'pending-request-{index}',
            ) == expected
        assert blocked.call_count == 0

    invite = db.query(ClienteAcessoModel).filter_by(
        cliente_id=pending_invite_client.id
    ).one()
    signup = db.query(ClienteAcessoModel).filter_by(
        cliente_id=pending_signup_client.id
    ).one()
    assert invite.token_finalidade == 'convite' and invite.token_hash == invite_hash
    assert signup.token_finalidade == 'verificacao' and signup.token_hash == signup_hash
    for index, token in enumerate((invite_token, signup_token)):
        try:
            access.reset_password(
                db,
                PasswordResetRequest(token=token, password='new-secure-password'),
                f'cross-purpose-source-{index}',
                f'cross-purpose-request-{index}',
            )
        except access.ClientAccessInvalid:
            pass
        else:
            raise AssertionError('activation token accepted for recovery')
''')

    def test_expired_revoked_cross_purpose_rate_limit_and_rollback(self):
        self.run_case(r'''
with Session(engine) as db:
    saved_access, user = active_account(db)
    email = saved_access.email_normalizado
    with patch.object(EmailService, 'enviar_recuperacao_senha', return_value={'id':'reset'}) as sent:
        access.request_password_recovery(
            db, PasswordRecoveryRequest(email=email), 'request-source', 'request-id'
        )
    token = recovery_token(sent)

    saved_access = db.query(ClienteAcessoModel).one()
    saved_access.token_expires_at = access._now() - timedelta(seconds=1)
    db.commit()
    try:
        access.reset_password(
            db, PasswordResetRequest(token=token, password='new-secure-password'),
            'expired-source', 'expired-request'
        )
    except access.ClientAccessConflict:
        pass
    else:
        raise AssertionError('expired token accepted')

    saved_access.token_expires_at = access._now() + timedelta(hours=1)
    saved_access.token_revoked_at = access._now()
    db.commit()
    try:
        access.reset_password(
            db, PasswordResetRequest(token=token, password='new-secure-password'),
            'revoked-source', 'revoked-request'
        )
    except access.ClientAccessConflict:
        pass
    else:
        raise AssertionError('revoked token accepted')

    saved_access.token_revoked_at = None
    db.commit()
    before_hash = user.password_hash
    with patch.object(access.audit_service, 'record', side_effect=RuntimeError('synthetic-audit-failure')):
        try:
            access.reset_password(
                db, PasswordResetRequest(token=token, password='new-secure-password'),
                'rollback-source', 'rollback-request'
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError('reset survived audit failure')
    db.expire_all()
    user = db.query(UsuarioModel).filter_by(username='recovery_client').one()
    saved_access = db.query(ClienteAcessoModel).one()
    assert user.password_hash == before_hash
    assert user.auth_version == 0
    assert saved_access.token_consumed_at is None

    saved_access.token_finalidade = 'convite'
    db.commit()
    try:
        access.reset_password(
            db, PasswordResetRequest(token=token, password='new-secure-password'),
            'purpose-source', 'purpose-request'
        )
    except access.ClientAccessInvalid:
        pass
    else:
        raise AssertionError('invite token accepted for recovery')

    for index in range(10):
        access.enforce_rate_limit(
            db, action='recovery', key='same-recovery-origin', limit=10,
            window=timedelta(minutes=15),
        )
    try:
        access.enforce_rate_limit(
            db, action='recovery', key='same-recovery-origin', limit=10,
            window=timedelta(minutes=15),
        )
    except access.ClientAccessRateLimited:
        pass
    else:
        raise AssertionError('recovery rate limit bypassed')
''')


if __name__ == '__main__':
    unittest.main()
