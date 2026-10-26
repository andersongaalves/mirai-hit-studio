"""Phase D: disposable SQLite, real PDF, mocked email provider."""
import unittest
import test_bootstrap_database as isolated
from test_proposta_documento import DOCUMENT_SETUP

SETUP = DOCUMENT_SETUP + '''
from services import proposta_comercial_service as commercial
from services.email_service import EmailService
from crud import crud_producao
from models import AuditLogModel, CobrancaModel, UsuarioModel
from core import config
import resend
from datetime import datetime
config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = False
def normalized(value):
    # SQLite drops timezone offsets; test instants are all UTC.
    return {k: v.replace(tzinfo=None) if isinstance(v, datetime) else v for k,v in value.model_dump().items()}
'''


class ComercialTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_send_approve_and_repeated_actions(self):
        self.run_case('''
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
    actor = db.get(UsuarioModel, 1)
    p = service.atualizar(db, p.id, PropostaUpdate(objeto='Masterizacao revisada', descricao='Escopo comercial',
        itens=[{'descricao':'Master', 'quantidade':2, 'valor_unitario':'625.00'}]))
    budget = db.get(OrcamentoModel, 1)
    budget.email = 'wrong@example.com'
    budget.nome_cliente = 'NAO USAR'
    budget.valor_total = 1
    budget.observacoes = 'NAO USAR LEGADO'
    db.commit()
    with patch.object(resend.Emails, 'send', return_value={'id':'synthetic-message'}) as send:
        sent = commercial.enviar(db, p.id, actor, 'proposal-request-001')
        assert sent.status == 'enviada' and sent.enviada_em and sent.pdf_path and sent.gerada_em
        assert sent.versao == p.versao
        assert db.get(OrcamentoModel, 1).status == 'proposta_enviada'
        payload, options = send.call_args.args
        assert payload['to'] == 'teste@example.com'
        assert 'R$ 1.250,00' in payload['html'] and 'Masterizacao revisada' in payload['html']
        data = base64.b64decode(payload['attachments'][0]['content'])
        assert data.startswith(b'%PDF-') and len(PdfReader(BytesIO(data)).pages)
        assert options['idempotency_key'].startswith(f'proposal/{p.id}/v{p.versao}/')
        assert normalized(commercial.enviar(db, p.id, actor, 'proposal-request-001')) == normalized(sent)
        assert send.call_count == 1
    approved = commercial.aprovar(db, p.id, actor, 'proposal-request-002')
    assert approved.status == 'aceita' and approved.aprovada_em
    assert approved.versao == p.versao and approved.pdf_path == sent.pdf_path
    assert db.get(OrcamentoModel, 1).status == 'aprovado'
    production = crud_producao.buscar_por_orcamento(db, 1)
    assert production.cliente == 'Cliente Teste' and production.produtor_id == 1
    assert production.titulo == 'Masterizacao revisada'
    assert 'R$ 1.250,00' in production.observacoes and 'NAO USAR' not in production.observacoes
    assert production.status == 'aguardando_inicio'
    assert normalized(commercial.aprovar(db, p.id, actor, 'proposal-request-002')) == normalized(approved)
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1
    assert db.get(OrcamentoModel, 1).proposta_enviada is False
    events = db.query(AuditLogModel).order_by(AuditLogModel.id).all()
    assert [event.action for event in events] == ['proposal.sent', 'proposal.approved']
    assert all(event.actor_user_id == actor.id for event in events)
''')

    def test_zero_value_proposal_starts_production_without_charge(self):
        # A courtesy or internal job (total R$ 0,00) is accepted without a charge;
        # with the V2 pipeline the production starts right away.
        self.run_case('''
config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
with Session(engine) as db:
    actor = db.get(UsuarioModel, 1)
    p = service.criar_por_orcamento(db, 1)
    p = service.atualizar(db, p.id, PropostaUpdate(objeto='Cortesia', itens=[
        {'descricao':'Mix de cortesia', 'quantidade':1, 'valor_unitario':'300.00', 'desconto':'300.00'}]))
    assert p.totais.total == 0
    with patch.object(resend.Emails, 'send', return_value={'id':'zero-message'}):
        commercial.enviar(db, p.id, actor, 'zero-send')
    approved = commercial.aprovar(db, p.id, actor, 'zero-approve')
    assert approved.status == 'aceita'
    assert db.query(CobrancaModel).filter_by(proposta_id=p.id).count() == 0
    production = crud_producao.buscar_por_orcamento(db, 1)
    assert production is not None and production.titulo == 'Cortesia'
    assert db.query(AuditLogModel).filter_by(action='production.released_without_charge').count() == 1
    # Repeating the approval is idempotent: still no charge, one production.
    commercial.aprovar(db, p.id, actor, 'zero-approve')
    assert db.query(CobrancaModel).count() == 0
    assert db.query(AuditLogModel).filter_by(action='production.released_without_charge').count() == 1

    # Paid items keep generating the charge as before.
    q = service.criar_por_orcamento(db, 2)
    q = service.atualizar(db, q.id, PropostaUpdate(itens=[{'descricao':'Master', 'quantidade':1, 'valor_unitario':'100.00'}]))
    with patch.object(resend.Emails, 'send', return_value={'id':'paid-message'}):
        commercial.enviar(db, q.id, actor, 'paid-send')
    commercial.aprovar(db, q.id, actor, 'paid-approve')
    assert db.query(CobrancaModel).filter_by(proposta_id=q.id).count() == 1
    assert crud_producao.buscar_por_orcamento(db, 2) is None  # waits for payment
''')

    def test_proposal_for_directly_created_production_links_instead_of_failing(self):
        # The Admin created the production first ("Nova produção") and the proposal later:
        # approving it links the proposal to that production instead of blocking.
        self.run_case('''
from services import audit_service
from models import ProducaoModel
config.settings.COMMERCIAL_PIPELINE_V2_ENABLED = True
with Session(engine) as db:
    actor = db.get(UsuarioModel, 1)
    direct = ProducaoModel(titulo='Direta', cliente='Cliente Teste', servico='Mixagem', orcamento_id=1,
                           status='em_producao', etapas='[]')
    other = ProducaoModel(titulo='Sem origem', cliente='Cliente Teste', servico='Mixagem', orcamento_id=2,
                          status='em_producao', etapas='[]')
    db.add_all([direct, other]); db.flush()
    audit_service.record(db, actor=actor, action='production.created_directly', entity_type='production',
                         entity_id=direct.id, metadata={'orcamento_id': 1})
    db.commit()
    for budget_id in (1, 2):
        p = service.criar_por_orcamento(db, budget_id)
        service.atualizar(db, p.id, PropostaUpdate(itens=[{'descricao':'Mix', 'quantidade':1, 'valor_unitario':'200.00'}]))
        with patch.object(resend.Emails, 'send', return_value={'id': f'direct-{budget_id}'}):
            commercial.enviar(db, p.id, actor, f'direct-send-{budget_id}')
    first = service.buscar_por_orcamento(db, 1)
    approved = commercial.aprovar(db, first.id, actor, 'direct-approve')
    assert approved.status == 'aceita'
    assert db.query(ProducaoModel).filter_by(orcamento_id=1).count() == 1
    assert db.get(ProducaoModel, direct.id).status == 'em_producao'  # the running work is kept
    assert db.query(CobrancaModel).filter_by(proposta_id=first.id).count() == 1
    assert db.query(AuditLogModel).filter_by(action='production.linked_to_proposal', entity_id=str(direct.id)).count() == 1
    # A production with no known origin still needs a human decision.
    second = service.buscar_por_orcamento(db, 2)
    try:
        commercial.aprovar(db, second.id, actor, 'other-approve')
    except service.PropostaConflito as error:
        assert 'requer conciliacao' in str(error)
    else:
        raise AssertionError('unknown production was linked')
''')

    def test_email_failure_and_commit_failure_rollback(self):
        self.run_case('''
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
    for result in [None, {}, {'error':'failure'}]:
        with patch.object(resend.Emails, 'send', return_value=result):
            try:
                commercial.enviar(db, p.id)
            except commercial.EnvioIndisponivel:
                pass
            else:
                raise AssertionError('email failure hidden')
        assert service.buscar(db, p.id) == p
        assert db.get(OrcamentoModel, 1).status == 'novo'
    with patch.object(resend.Emails, 'send', side_effect=RuntimeError('sensitive-sentinel')):
        try:
            commercial.enviar(db, p.id)
        except commercial.EnvioIndisponivel as error:
            assert 'sensitive-sentinel' not in str(error)
    assert service.buscar(db, p.id) == p
    with patch.object(resend.Emails, 'send', return_value={'id':'synthetic-message'}), \\
         patch.object(db, 'commit', side_effect=SQLAlchemyError('synthetic commit failure')):
        try:
            commercial.enviar(db, p.id)
        except commercial.EnvioIndisponivel as error:
            assert 'Concilie' in str(error)
            pass
    assert service.buscar(db, p.id) == p
    assert db.get(OrcamentoModel, 1).status == 'novo'
''')

    def test_current_missing_and_corrupt_pdf(self):
        self.run_case('''
with Session(engine) as db:
    for budget_id in [1, 2, 3]:
        p = service.criar_por_orcamento(db, budget_id)
        p = documents.gerar_documento(db, p.id)
        path = LocalDocumentoStorage()._path(p.pdf_path)
        if budget_id == 2:
            path.unlink()  # Disposable test artifact only.
        if budget_id == 3:
            path.write_bytes(b'not a PDF')
        with patch.object(resend.Emails, 'send', return_value={'id':'synthetic-message'}), \\
             patch.object(documents, 'gerar_sem_commit', wraps=documents.gerar_sem_commit) as generate:
            sent = commercial.enviar(db, p.id)
            assert generate.call_count == (0 if budget_id == 1 else 1)
            assert sent.status == 'enviada'
            assert (sent.pdf_path == p.pdf_path) == (budget_id == 1)
''')

    def test_invalid_transitions_and_approval_rollback(self):
        self.run_case('''
with Session(engine) as db:
    for action in [commercial.enviar, commercial.aprovar]:
        try:
            action(db, 999)
        except service.PropostaNaoEncontrada:
            pass
        else:
            raise AssertionError('missing proposal accepted')
    p = service.criar_por_orcamento(db, 1)
    for status in ['rascunho', 'pronta', 'recusada', 'cancelada']:
        model = db.get(PropostaModel, p.id)
        model.status = status
        db.commit()
        try:
            commercial.aprovar(db, p.id)
        except service.PropostaConflito:
            pass
        else:
            raise AssertionError(status)
    for status in ['aceita', 'recusada', 'cancelada']:
        model.status = status
        db.commit()
        try:
            commercial.enviar(db, p.id)
        except service.PropostaConflito:
            pass
        else:
            raise AssertionError(status)
    model.status = 'pronta'
    db.commit()
    with patch.object(resend.Emails, 'send', return_value={'id':'synthetic-message'}):
        sent = commercial.enviar(db, p.id)
    with patch.object(crud_producao, 'criar_sem_commit', side_effect=SQLAlchemyError('synthetic failure')):
        try:
            commercial.aprovar(db, p.id)
        except SQLAlchemyError:
            pass
    assert normalized(service.buscar(db, p.id)) == normalized(sent)
    assert db.get(OrcamentoModel, 1).status == 'proposta_enviada'
    assert crud_producao.buscar_por_orcamento(db, 1) is None
    with patch.object(db, 'commit', side_effect=SQLAlchemyError('synthetic failure')):
        try:
            commercial.aprovar(db, p.id)
        except SQLAlchemyError:
            pass
    assert normalized(service.buscar(db, p.id)) == normalized(sent)
    assert crud_producao.buscar_por_orcamento(db, 1) is None
    commercial.aprovar(db, p.id)
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1
''')

    def test_database_guard_and_legacy_status(self):
        self.run_case('''
from sqlalchemy.exc import IntegrityError
from crud import crud_orcamento
from core.enums import OrcamentoStatus
from sqlalchemy.dialects import postgresql
class Recorder:
    def scalar(self, query):
        self.query = query
recorder = Recorder()
crud_proposta.buscar_por_id(recorder, 1, bloquear=True)
assert 'FOR UPDATE' in str(recorder.query.compile(dialect=postgresql.dialect()))
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
    for status in [OrcamentoStatus.APROVADO, OrcamentoStatus.PROPOSTA_ENVIADA]:
        try:
            crud_orcamento.atualizar_status(db, 1, status)
        except ValueError:
            db.rollback()
        else:
            raise AssertionError('legacy bypass allowed')
    with patch.object(resend.Emails, 'send', return_value={'id':'synthetic-message'}):
        commercial.enviar(db, p.id)
    commercial.aprovar(db, p.id)
    try:
        crud_producao.criar_sem_commit(db, commercial._dados_producao(service.buscar(db, p.id)))
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError('duplicate production accepted by database')
    assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1
''')

    def test_http_endpoints(self):
        self.run_case('''
import asyncio, json
from fastapi import FastAPI
from core.dependencies import get_current_user
from routers.propostas import router, get_db
from routers.orcamentos import router as budgets_router
app = FastAPI()
app.include_router(router)
app.include_router(budgets_router)
def session():
    with Session(engine) as db:
        yield db
app.dependency_overrides[get_db] = session
app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(
    id=1, username='admin', role='admin', is_admin=True, ativo=True)
with Session(engine) as db:
    p = service.criar_por_orcamento(db, 1)
async def request(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else b''
    messages = []
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
             'method': method, 'scheme': 'http', 'path': path, 'raw_path': path.encode(),
             'query_string': b'', 'root_path': '', 'headers': [(b'content-type', b'application/json')],
             'client': ('127.0.0.1', 1234), 'server': ('test', 80)}
    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': False}
    async def send(message):
        messages.append(message)
    await app(scope, receive, send)
    start = next(m for m in messages if m['type'] == 'http.response.start')
    content = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
    return start['status'], json.loads(content)
async def check():
    network_guard.start()
    for action in ['enviar','aprovar']:
        status, _ = await request('POST', '/propostas/999/' + action)
        assert status == 404
    status, _ = await request('POST', f'/propostas/{p.id}/aprovar')
    assert status == 409
    status, _ = await request('POST', '/orcamentos/1/enviar-proposta')
    assert status == 409
    status, _ = await request('PATCH', '/orcamentos/1/status', {'status':'aprovado'})
    assert status == 409
    with patch.object(resend.Emails, 'send', side_effect=RuntimeError('secret-sentinel')):
        status, body = await request('POST', f'/propostas/{p.id}/enviar')
        assert status == 503 and 'secret-sentinel' not in str(body)
    with patch.object(resend.Emails, 'send', return_value={'id':'synthetic-message'}) as email:
        status, sent = await request('POST', f'/propostas/{p.id}/enviar')
        assert status == 200 and sent['status'] == 'enviada'
        status, repeated = await request('POST', f'/propostas/{p.id}/enviar')
        assert status == 200 and email.call_count == 1
        assert repeated['versao'] == sent['versao']
    status, accepted = await request('POST', f'/propostas/{p.id}/aprovar')
    assert status == 200 and accepted['status'] == 'aceita'
    status, again = await request('POST', f'/propostas/{p.id}/aprovar')
    assert status == 200 and again['aprovada_em'][:19] == accepted['aprovada_em'][:19]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ProducaoModel)) == 1
        assert db.scalar(select(func.count()).select_from(CobrancaModel)) == 1
network_guard.stop()  # Windows creates its private event-loop socket pair here.
asyncio.run(check())
''')


if __name__ == '__main__':
    unittest.main()
