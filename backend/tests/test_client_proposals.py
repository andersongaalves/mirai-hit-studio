"""Client proposal portal contracts on a disposable database."""
import unittest

import test_bootstrap_database as isolated
from test_proposta_comercial import SETUP as COMMERCIAL_SETUP

SETUP = COMMERCIAL_SETUP + r'''
import types
from urllib.parse import parse_qs, urlparse
from datetime import timezone

from core.security import get_password_hash
from models import ClienteModel, ClienteAcessoModel
from services import client_access_service as access
from services import portal_cliente_proposta_service as portal_proposals

config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
config.settings.PUBLIC_FRONTEND_URL = 'http://localhost:4173'

def sent_proposal(db, budget_id, client=None):
    budget = db.get(OrcamentoModel, budget_id)
    if client is None:
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
    proposal = service.criar_por_orcamento(db, budget_id)
    with patch.object(resend.Emails, 'send', return_value={'id':'proposal-message'}):
        commercial.enviar(db, proposal.id)
    return db.get(PropostaModel, proposal.id), client
'''


class ClientProposalTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_projection_ownership_and_persisted_pdf(self):
        self.run_case(r'''
with Session(engine) as db:
    own, client_a = sent_proposal(db, 1)
    other, client_b = sent_proposal(db, 2)
    listed = portal_proposals.list_for_client(db, client_a.id)
    assert [item['id'] for item in listed] == [own.id]
    assert set(listed[0]) == {
        'id', 'numero', 'versao', 'status', 'servico', 'objeto', 'descricao',
        'itens', 'totais', 'politica_pagamento', 'condicoes',
        'documento_disponivel', 'situacao_comercial', 'cobranca_status',
        'enviada_em', 'aprovada_em', 'created_at', 'updated_at',
    }
    assert listed[0]['status'] == 'enviada'
    assert listed[0]['situacao_comercial'] == 'aguardando_aceite'
    assert 'pdf_path' not in listed[0] and 'pagamentos' not in listed[0]
    try:
        portal_proposals.get_for_client(db, other.id, client_a.id)
    except portal_proposals.PropostaClienteNotFound:
        pass
    else:
        raise AssertionError('foreign proposal exposed')
    data, filename = portal_proposals.document_for_client(db, own.id, client_a.id)
    assert data.startswith(b'%PDF-') and filename.endswith('.pdf')
    path = LocalDocumentoStorage()._path(own.pdf_path)
    path.write_bytes(b'corrupted-pdf')
    try:
        portal_proposals.document_for_client(db, own.id, client_a.id)
    except portal_proposals.PropostaClienteUnavailable as error:
        assert 'corrupted-pdf' not in str(error)
    else:
        raise AssertionError('corrupt proposal document served')
''')

    def test_accept_refuse_version_and_legacy_flag(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal, client = sent_proposal(db, 1)
    user = UsuarioModel(username='client-a', password_hash=get_password_hash('client-pass'),
                        role='cliente', is_admin=False, ativo=True, cliente_id=client.id)
    db.add(user)
    db.commit()
    accepted = portal_proposals.accept(db, proposal.id, client.id, proposal.versao,
                                       user, 'client-accept-1')
    assert accepted['status'] == 'aceita'
    assert accepted['situacao_comercial'] == 'aguardando_pagamento'
    assert db.query(CobrancaModel).filter_by(proposta_id=proposal.id).count() == 1
    assert db.query(ProducaoModel).count() == 0
    repeated = portal_proposals.accept(db, proposal.id, client.id, proposal.versao,
                                       user, 'client-accept-2')
    assert repeated['status'] == 'aceita'
    assert db.query(CobrancaModel).filter_by(proposta_id=proposal.id).count() == 1
    try:
        portal_proposals.accept(db, proposal.id, client.id, proposal.versao + 1,
                                user, 'client-stale')
    except portal_proposals.PropostaClienteConflict as error:
        assert 'versao atual' in str(error)
    else:
        raise AssertionError('stale proposal accepted')
    assert db.query(AuditLogModel).filter_by(action='proposal.accepted_by_client').count() == 1

with Session(engine) as db:
    refused, client_b = sent_proposal(db, 2)
    user_b = UsuarioModel(username='client-b', password_hash=get_password_hash('client-pass'),
                          role='cliente', is_admin=False, ativo=True, cliente_id=client_b.id)
    db.add(user_b)
    db.commit()
    result = portal_proposals.refuse(db, refused.id, client_b.id, refused.versao,
                                     user_b, 'client-refuse')
    assert result['status'] == 'recusada'
    assert db.get(OrcamentoModel, refused.orcamento_id).status == 'recusado'
    assert db.query(CobrancaModel).filter_by(proposta_id=refused.id).count() == 0
    assert db.query(ProducaoModel).filter_by(orcamento_id=refused.orcamento_id).count() == 0

    config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = False
    try:
        portal_proposals.list_for_client(db, client_b.id)
    except portal_proposals.PropostaClienteNotFound:
        pass
    else:
        raise AssertionError('V2 endpoint available with flag off')
''')

    def test_invite_sent_existing_account_and_identity_conflict(self):
        self.run_case(r'''
with Session(engine) as db:
    proposal, client = sent_proposal(db, 1)
    actor = db.get(UsuarioModel, 1)
    with patch.object(EmailService, 'enviar_convite_cliente', return_value={'id':'invite'}) as email:
        state = access.invite(db, proposal.id, actor, 'invite-request', 'invite-source')
    activation_url = email.call_args.args[1]
    query = parse_qs(urlparse(activation_url).query)
    assert query['token'][0]
    assert query['next'] == [f'/cliente/propostas/{proposal.id}']
    assert state.estado == 'convite_pendente'

with Session(engine) as db:
    proposal = db.get(PropostaModel, proposal.id)
    client = db.get(ClienteModel, client.id)
    access_row = db.query(ClienteAcessoModel).one()
    access_row.token_consumed_at = datetime.now(timezone.utc)
    user = UsuarioModel(username='existing-client', password_hash=get_password_hash('client-pass'),
                        role='cliente', is_admin=False, ativo=True, cliente_id=client.id)
    db.add(user)
    db.flush()
    access_row.usuario_id = user.id
    access_row.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    actor = db.get(UsuarioModel, 1)
    with patch.object(EmailService, 'enviar_proposta_disponivel', return_value={'id':'notice'}) as notice:
        state = access.invite(db, proposal.id, actor, 'notice-request', 'notice-source')
    assert state.estado == 'conta_ativa'
    assert '/acesso?next=' in notice.call_args.args[1]
    assert notice.call_args.kwargs['idempotency_key'].startswith(f'client-proposal/{proposal.id}/v')
    assert db.query(UsuarioModel).filter_by(cliente_id=client.id).count() == 1

    client.email = 'different@example.com'
    db.commit()
    try:
        access.status(db, proposal.id)
    except access.ClientAccessConflict:
        pass
    else:
        raise AssertionError('commercial identity conflict accepted')
''')

    def test_router_auth_roles_headers_and_safe_not_found(self):
        self.run_case(r'''
import asyncio
import httpx
from fastapi import FastAPI
from core.dependencies import get_current_user
from database import get_db
from routers.portal_cliente import router

with Session(engine) as db:
    proposal, client_a = sent_proposal(db, 1)
    other, client_b = sent_proposal(db, 2)
    client_user = UsuarioModel(username='client-router', password_hash='hash', role='cliente',
                               is_admin=False, ativo=True, cliente_id=client_a.id)
    db.add(client_user)
    db.commit()
    client_user_id = client_user.id
    client_a_id = client_a.id
    proposal_id = proposal.id
    proposal_version = proposal.versao
    other_id = other.id

app = FastAPI()
app.include_router(router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session

async def check():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as http:
        assert (await http.get('/portal/cliente/propostas')).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(
            id=1, role='admin', is_admin=True, ativo=True, cliente_id=None)
        assert (await http.get('/portal/cliente/propostas')).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(
            id=client_user_id, role='cliente', is_admin=False, ativo=True, cliente_id=client_a_id)
        listed = await http.get('/portal/cliente/propostas')
        assert listed.status_code == 200 and [item['id'] for item in listed.json()] == [proposal_id]
        foreign = await http.get(f'/portal/cliente/propostas/{other_id}')
        missing = await http.get('/portal/cliente/propostas/999999')
        assert foreign.status_code == missing.status_code == 404
        assert foreign.json() == missing.json()
        document = await http.get(f'/portal/cliente/propostas/{proposal_id}/documento')
        assert document.status_code == 200
        assert document.headers['cache-control'] == 'private, no-store'
        assert document.headers['x-content-type-options'] == 'nosniff'
        accepted = await http.post(f'/portal/cliente/propostas/{proposal_id}/aceitar',
                                   json={'versao': proposal_version})
        assert accepted.status_code == 200 and accepted.json()['status'] == 'aceita'
network_guard.stop()
asyncio.run(check())
''')


if __name__ == "__main__":
    unittest.main()
