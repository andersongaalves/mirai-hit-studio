"""Client invitation lifecycle on a disposable database with a fake email provider."""

import unittest

import test_bootstrap_database as isolated
from test_proposta_comercial import SETUP as COMMERCIAL_SETUP

SETUP = COMMERCIAL_SETUP + r'''
from urllib.parse import parse_qs, urlparse
from datetime import timedelta

from core.security import verify_password
from models import ClienteAcessoModel, ClienteModel
from schemas.client_access import ClientInviteActivation
from services import client_access_service as access

config.settings.PUBLIC_FRONTEND_URL = 'http://localhost:4173'

def accepted_proposal(db, budget_id=1):
    budget = db.get(OrcamentoModel, budget_id)
    if budget.cliente_id is None:
        client = ClienteModel(
            nome=budget.nome_cliente,
            email=budget.email,
            telefone=budget.whatsapp,
            observacoes='',
            ativo=True,
        )
        db.add(client)
        db.flush()
        budget.cliente_id = client.id
        db.commit()
    proposal = service.criar_por_orcamento(db, budget_id)
    with patch.object(resend.Emails, 'send', return_value={'id':'proposal-message'}):
        commercial.enviar(db, proposal.id)
    commercial.aprovar(db, proposal.id)
    return db.get(PropostaModel, proposal.id)

def raw_token(call):
    activation_url = call.call_args.args[1]
    return parse_qs(urlparse(activation_url).query)['token'][0]
'''


class ClientAccessTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_invite_activate_and_single_use(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal = accepted_proposal(db)
    actor = db.get(UsuarioModel, 1)
    with patch.object(EmailService, 'enviar_convite_cliente', return_value={'id':'invite-message'}) as email:
        pending = access.invite(db, proposal.id, actor, 'request-1', '127.0.0.1')
    token = raw_token(email)
    saved = db.query(ClienteAcessoModel).one()
    assert saved.token_hash == access._hash(token) and token not in saved.token_hash
    assert pending.estado == 'convite_pendente' and pending.send_count == 1
    assert access.token_state(db, token, 'validation-source') == 'valido'

    user = access.activate(db, ClientInviteActivation(
        token=token, username='cliente_portal', password='secure-password'
    ), 'activation-source', 'request-2')
    assert user.role == 'cliente' and user.is_admin is False and user.ativo is True
    assert user.cliente_id == db.get(OrcamentoModel, proposal.orcamento_id).cliente_id
    assert verify_password('secure-password', user.password_hash)
    saved = db.query(ClienteAcessoModel).one()
    assert saved.usuario_id == user.id and saved.token_consumed_at and saved.email_verified_at
    assert access.token_state(db, token, 'validation-source-2') == 'utilizado'
    try:
        access.activate(db, ClientInviteActivation(
            token=token, username='outro', password='secure-password'
        ), 'activation-source-2', 'request-3')
    except access.ClientAccessConflict:
        pass
    else:
        raise AssertionError('consumed invite reused')
    assert db.query(UsuarioModel).filter_by(cliente_id=user.cliente_id).count() == 1
    assert access.status(db, proposal.id).estado == 'conta_ativa'
    actions = [item.action for item in db.query(AuditLogModel).all()]
    assert 'client_access.invite_created' in actions
    assert 'client_access.activated' in actions
''')

    def test_resend_rotates_token_and_revoke(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal = accepted_proposal(db)
    actor = db.get(UsuarioModel, 1)
    with patch.object(EmailService, 'enviar_convite_cliente', return_value={'id':'first'}) as first:
        access.invite(db, proposal.id, actor, 'request-1', 'source-a')
    old_token = raw_token(first)
    with patch.object(EmailService, 'enviar_convite_cliente', return_value={'id':'second'}) as second:
        state = access.resend(db, proposal.id, actor, 'request-2', 'source-b')
    new_token = raw_token(second)
    assert old_token != new_token and state.send_count == 2
    try:
        access.token_state(db, old_token, 'validation-old')
    except access.ClientAccessInvalid:
        pass
    else:
        raise AssertionError('old token survived rotation')
    assert access.token_state(db, new_token, 'validation-new') == 'valido'
    revoked = access.revoke(db, proposal.id, actor, 'request-3')
    assert revoked.estado == 'convite_revogado'
    assert access.token_state(db, new_token, 'validation-revoked') == 'revogado'
''')

    def test_guards_delivery_failure_and_conflicts(self):
        self.run_case(r'''
with Session(engine) as db:
    draft = service.criar_por_orcamento(db, 1)
    actor = db.get(UsuarioModel, 1)
    try:
        access.invite(db, draft.id, actor, 'request-draft', 'source-draft')
    except access.ClientAccessInvalid:
        pass
    else:
        raise AssertionError('draft accepted for invitation')

    proposal = accepted_proposal(db)
    with patch.object(EmailService, 'enviar_convite_cliente', side_effect=RuntimeError('private-provider-error')):
        try:
            access.invite(db, proposal.id, actor, 'request-failure', 'source-failure')
        except access.ClientAccessDeliveryUnavailable as error:
            assert 'private-provider-error' not in str(error)
        else:
            raise AssertionError('provider failure hidden')
    saved = db.query(ClienteAcessoModel).one()
    assert saved.token_hash and saved.last_sent_at is None and saved.send_count == 0

    client = db.get(ClienteModel, saved.cliente_id)
    client.email = 'email-invalido'
    db.commit()
    try:
        access.resend(db, proposal.id, actor, 'request-no-email', 'source-no-email')
    except access.ClientAccessInvalid:
        pass
    else:
        raise AssertionError('invite without email accepted')
    assert db.query(UsuarioModel).filter_by(cliente_id=client.id).count() == 0
''')

    def test_rate_limit_and_duplicate_username(self):
        self.run_case(r'''
with Session(engine) as db:
    for index in range(10):
        access.enforce_rate_limit(db, action='activation', key='same-origin', limit=10,
                                  window=timedelta(minutes=15))
    try:
        access.enforce_rate_limit(db, action='activation', key='same-origin', limit=10,
                                  window=timedelta(minutes=15))
    except access.ClientAccessRateLimited:
        pass
    else:
        raise AssertionError('rate limit bypassed')

    proposal = accepted_proposal(db)
    actor = db.get(UsuarioModel, 1)
    with patch.object(EmailService, 'enviar_convite_cliente', return_value={'id':'invite'}) as email:
        access.invite(db, proposal.id, actor, 'request-invite', 'other-origin')
    token = raw_token(email)
    try:
        access.activate(db, ClientInviteActivation(
            token=token, username=actor.username, password='secure-password'
        ), 'third-origin', 'request-activate')
    except access.ClientAccessConflict:
        pass
    else:
        raise AssertionError('duplicate username accepted')
    assert db.query(UsuarioModel).filter_by(cliente_id=db.query(ClienteAcessoModel).one().cliente_id).count() == 0
''')


if __name__ == "__main__":
    unittest.main()
