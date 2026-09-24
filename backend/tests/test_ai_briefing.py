"""Briefing/CRM contracts on the existing disposable database harness."""

import unittest

import test_bootstrap_database as isolated


SETUP = r'''
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import ValidationError
from sqlalchemy import func, select
from database import SessionLocal
from models import AIBriefingModel, AIConversationModel, ClienteModel, OrcamentoModel, ServicoModel
from models.ai import AIEmailThreadModel
from schemas.ai import ConversationCreate, ConversationMode, InboundMessage, ProviderResponse, ToolCall
from schemas.ai_briefing import BriefingUpdateInput
from services.ai_briefing_service import AIBriefingService
from services.ai_conversation_service import ConversationService
from services.ai_knowledge_service import build_tool_registry
from services.ai_tools import ToolExecutionContext, ToolError
bootstrap(engine)
with SessionLocal.begin() as db:
    db.add(ServicoModel(id=1, nome='Mixagem', subtitulo='', valor_base=300, categoria='avulso'))
core = ConversationService(SessionLocal)
briefing = AIBriefingService(SessionLocal)
registry = build_tool_registry(SessionLocal)
def incoming(cid, text, channel='site'):
    with SessionLocal() as db:
        conversation = db.get(AIConversationModel, cid)
        thread, sender = conversation.external_thread_id, conversation.sender_reference
    mid = core.receive(cid, InboundMessage(
        channel=channel, external_message_id=str(uuid4()), text=text,
        external_thread_id=thread, sender_reference=sender,
        received_at=datetime.now(timezone.utc)))
    return ToolExecutionContext(conversation_id=UUID(cid), message_id=UUID(mid),
                                mode=ConversationMode.AUTONOMOUS, source=channel)
def run(name, context, args):
    return registry.run(ToolCall(id=str(uuid4()), name=name, arguments=args), context)
'''


class AIBriefingTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_strict_schema_evidence_merge_and_correction(self):
        self.run_case(r'''
cid = core.create(ConversationCreate(channel='site', mode='autonomous'))
ctx = incoming(cid, 'Quero Mixagem da minha musica')
assert run('update_briefing', ctx, {'service_id':1, 'interest':'Mixagem'}).success
assert briefing.admin_view(cid).missing_fields == ('contact_name', 'contact_email')
assert run('update_briefing', ctx, {'details':{'style':'trap'}}).error_code == 'invalid_input'
assert run('update_briefing', ctx, {'price':50}).error_code == 'invalid_input'
assert run('update_briefing', ctx, {'cliente_id':1}).error_code == 'invalid_input'
assert run('update_briefing', ctx, {'details':{}}).error_code == 'invalid_input'
assert run('update_briefing', ctx, {'details':{'references':[]}}).error_code == 'invalid_input'
assert run('update_briefing', ctx, {'contact_phone':'abcdefg'}).error_code == 'invalid_input'
assert run('update_briefing', ctx, {'details':{'references':['javascript:alert(1)']}}).error_code == 'invalid_input'
ctx = incoming(cid, 'E trap, com 18 stems')
assert run('update_briefing', ctx, {'details':{'style':'trap','track_count':18}}).success
ctx = incoming(cid, 'Na verdade sao 24 stems; prazo desejado 2026-10-20')
assert run('update_briefing', ctx, {'details':{'track_count':24,'requested_deadline':'2026-10-20'}}).success
data = briefing.admin_view(cid)
assert data.details.style == 'trap' and data.details.track_count == 24
assert data.details.requested_deadline.isoformat() == '2026-10-20'
assert not hasattr(data.details, 'price') and data.orcamento_id is None
''')

    def test_site_submit_is_atomic_idempotent_and_unpriced(self):
        self.run_case(r'''
from models.newsletter import NewsletterModel
cid = core.create(ConversationCreate(channel='site', mode='autonomous'))
ctx = incoming(cid, 'Quero Mixagem da minha musica')
assert run('update_briefing', ctx, {'interest':'Mixagem','service_id':1}).success
ctx = incoming(cid, 'Me chamo Ana, email ana@example.com')
assert run('update_briefing', ctx, {'contact_name':'Ana','contact_email':'ana@example.com'}).success
preliminary = run('submit_briefing', ctx, {})
assert preliminary.error_code == 'invalid_input', preliminary.model_dump()
ctx = incoming(cid, 'Pode enviar o orcamento')
first = run('submit_briefing', ctx, {})
second = run('submit_briefing', ctx, {})
assert first.success and second.success and first.data['submitted']
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(OrcamentoModel)) == 1
    assert db.scalar(select(func.count()).select_from(ClienteModel)) == 1
    assert db.scalar(select(func.count()).select_from(NewsletterModel)) == 0
    budget = db.scalar(select(OrcamentoModel))
    assert budget.valor_total is None and budget.cliente_id is not None
    assert budget.servico == 'Mixagem' and 'Interesse: Mixagem' in budget.detalhes
    assert db.get(AIConversationModel, cid).cliente_id == budget.cliente_id
    assert db.get(AIBriefingModel, cid).orcamento_id == budget.id
assert not ctx.identity_verified
assert 'get_payment_status' not in {item.name for item in registry.definitions(ctx)}
''')

    def test_custom_interest_does_not_create_service_or_price(self):
        self.run_case(r'''
cid = core.create(ConversationCreate(channel='site', mode='autonomous'))
ctx = incoming(cid, 'Quero trilha para jogo')
assert run('update_briefing', ctx, {'service_id':999}).error_code == 'not_found'
assert run('update_briefing', ctx, {'interest':'trilha para jogo'}).success
ctx = incoming(cid, 'Sou Lia, email lia@example.com')
assert run('update_briefing', ctx, {'contact_name':'Lia','contact_email':'lia@example.com'}).success
ctx = incoming(cid, 'Pode enviar o orcamento')
assert run('submit_briefing', ctx, {}).success
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(ServicoModel)) == 1
    budget = db.scalar(select(OrcamentoModel))
    assert budget.servico == 'trilha para jogo' and budget.valor_total is None
    assert db.get(AIBriefingModel, cid).service_id is None
''')

    def test_client_conflict_does_not_merge_or_create_budget(self):
        self.run_case(r'''
with SessionLocal.begin() as db:
    db.add_all([
        ClienteModel(id=1,nome='Ana',email='ana@example.com',telefone=None),
        ClienteModel(id=2,nome='Outro',email=None,telefone='5511999999999'),
    ])
cid = core.create(ConversationCreate(channel='site', mode='autonomous'))
ctx = incoming(cid, 'Quero Mixagem')
assert run('update_briefing', ctx, {'interest':'Mixagem'}).success
ctx = incoming(cid, 'Sou Ana, email ana@example.com, telefone +55 11 99999-9999')
assert run('update_briefing', ctx, {'contact_name':'Ana','contact_email':'ana@example.com',
                                    'contact_phone':'+55 11 99999-9999'}).success
ctx = incoming(cid, 'Pode enviar o orcamento')
result = run('submit_briefing', ctx, {})
assert result.error_code == 'conflict', result.model_dump()
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(OrcamentoModel)) == 0
    assert db.scalar(select(func.count()).select_from(ClienteModel)) == 2
    assert db.get(AIBriefingModel, cid).status == 'draft'
''')

    def test_client_conflict_handoffs_and_preserves_draft(self):
        self.run_case(r'''
with SessionLocal.begin() as db:
    db.add_all([
        ClienteModel(id=1,nome='Ana',email='ana@example.com'),
        ClienteModel(id=2,nome='Outra',telefone='5511999999999'),
    ])
class Scripted:
    def generate(self, data):
        if data.tool_results:
            return ProviderResponse(text='Entendi seu pedido.')
        if 'Quero Mixagem' in data.message:
            args = {'interest':'Mixagem'}; name = 'update_briefing'
        elif 'Sou Ana' in data.message:
            args = {'contact_name':'Ana','contact_email':'ana@example.com',
                    'contact_phone':'+55 11 99999-9999'}; name = 'update_briefing'
        else:
            args = {}; name = 'submit_briefing'
        return ProviderResponse(tool_calls=(ToolCall(id=str(uuid4()),name=name,arguments=args),))
from schemas.ai_site import SiteMessage
from services.ai_site_service import SiteChatService
site = SiteChatService(ConversationService(SessionLocal, Scripted()))
session = site.create_session()
def send(body):
    return site.message(session.session_token, SiteMessage(message_id=uuid4(), message=body))
send('Quero Mixagem')
send('Sou Ana, email ana@example.com, telefone +55 11 99999-9999')
result = send('Pode enviar o orcamento')
assert result.action == 'handoff' and result.status == 'waiting_human'
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(OrcamentoModel)) == 0
    assert db.scalar(select(AIBriefingModel)).status == 'draft'
''')

    def test_existing_client_matches_email_or_phone_without_duplicate(self):
        self.run_case(r'''
with SessionLocal.begin() as db:
    db.add_all([
        ClienteModel(id=1,nome='Ana',email='ana@example.com',telefone=None),
        ClienteModel(id=2,nome='Bia',email=None,telefone='5511888888888'),
    ])
def submit(contact):
    cid = core.create(ConversationCreate(channel='site', mode='autonomous'))
    ctx = incoming(cid, 'Quero Mixagem')
    assert run('update_briefing', ctx, {'interest':'Mixagem'}).success
    ctx = incoming(cid, contact['message'])
    assert run('update_briefing', ctx, contact['fields']).success
    ctx = incoming(cid, 'Pode enviar o orcamento')
    assert run('submit_briefing', ctx, {}).success
    return cid
first = submit({'message':'Sou Ana, email ana@example.com',
                'fields':{'contact_name':'Ana','contact_email':'ana@example.com'}})
second = submit({'message':'Sou Bia, email bia@example.com, telefone +55 11 88888-8888',
                 'fields':{'contact_name':'Bia','contact_email':'bia@example.com',
                           'contact_phone':'+55 11 88888-8888'}})
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(ClienteModel)) == 2
    assert db.scalar(select(func.count()).select_from(OrcamentoModel)) == 2
    assert db.get(AIConversationModel, first).cliente_id == 1
    assert db.get(AIConversationModel, second).cliente_id == 2
    assert db.get(ClienteModel, 2).email == 'bia@example.com'
''')

    def test_email_sender_contact_and_isolated_conversations(self):
        self.run_case(r'''
def email_conversation(key):
    cid = core.create(ConversationCreate(channel='email', mode='autonomous',
        external_thread_id=key, sender_reference='bia@example.com'))
    with SessionLocal.begin() as db:
        db.add(AIEmailThreadModel(conversation_id=cid,sender_email='bia@example.com',
            subject='Pedido',root_message_id=key+'@example.com'))
    return cid
first, second = email_conversation('thread-1'), email_conversation('thread-2')
ctx = incoming(first, 'Sou Bia, quero Mixagem', channel='email')
assert run('update_briefing', ctx, {'contact_name':'Bia','interest':'Mixagem'}).success
assert briefing.admin_view(first).contact_email == 'bia@example.com'
assert briefing.admin_view(second) is None
ctx = incoming(first, 'Pode enviar o orcamento', channel='email')
result = run('submit_briefing', ctx, {})
assert result.success, result.model_dump()
assert briefing.admin_view(first).orcamento_id is not None
assert not ctx.identity_verified
assert 'get_budget_status' not in {item.name for item in registry.definitions(ctx)}
''')

    def test_email_thread_provider_flow_creates_one_budget(self):
        self.run_case(r'''
from services.ai_email_service import AIEmailService
class Scripted:
    def generate(self, data):
        if data.tool_results:
            assert data.tool_results[-1].success
            return ProviderResponse(text='Pedido recebido pela equipe Mirai.')
        if 'Sou Bia' in data.message:
            args = {'contact_name':'Bia','interest':'Mixagem'}; name = 'update_briefing'
        else:
            args = {}; name = 'submit_briefing'
        return ProviderResponse(tool_calls=(ToolCall(id=str(uuid4()),name=name,arguments=args),))
class Mailer:
    sent = []
    def send_reply(self, **payload):
        self.sent.append(payload)
        return 'sent-' + str(len(self.sent))
mailer = Mailer()
email_service = AIEmailService(ConversationService(SessionLocal, Scripted()), mailer,
    sender_address='mirai@example.com', limiter=lambda *args: (True, 0))
def event(key, message_id, body, **extra):
    data = {'email_id':key,'from':'bia@example.com','to':['mirai@example.com'],
            'subject':'Pedido','message_id':message_id,'text':body,
            'created_at':'2026-09-24T12:00:00Z'}
    data.update(extra)
    return {'type':'email.received','data':data}
first = email_service.handle(event('email-one','<one@example.com>',
    'Sou Bia, quero Mixagem'))
second_event = event('email-two','<two@example.com>',
    'Pode enviar o orcamento', in_reply_to='<one@example.com>',
    references=['<one@example.com>'])
second = email_service.handle(second_event)
retry = email_service.handle(second_event)
assert first.conversation_id == second.conversation_id == retry.conversation_id
assert retry.duplicate and len(mailer.sent) == 2
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(OrcamentoModel)) == 1
    assert db.get(AIConversationModel, first.conversation_id).cliente_id is not None
    assert db.get(AIBriefingModel, first.conversation_id).orcamento_id is not None
''')

    def test_tool_visibility_copilot_context_and_no_write(self):
        self.run_case(r'''
cid = core.create(ConversationCreate(channel='site', mode='autonomous'))
ctx = incoming(cid, 'Quero Mixagem com 24 stems')
assert run('update_briefing', ctx, {'interest':'Mixagem','details':{'track_count':24}}).success
copilot = ctx.model_copy(update={'mode':ConversationMode.COPILOT,'actor':'operator','source':'internal'})
assert 'update_briefing' not in {item.name for item in registry.definitions(copilot)}
assert run('update_briefing', copilot, {'interest':'Outro'}).error_code == 'not_authorized'
core.set_mode(cid, ConversationMode.COPILOT)
class Fake:
    def generate(self, data):
        assert any('24' in item and 'Mixagem' in item for item in data.context)
        assert 'update_briefing' not in {tool.name for tool in data.tools}
        return ProviderResponse(text='Voce informou 24 stems. Qual o estilo?')
copilot_core = ConversationService(SessionLocal, Fake())
result = copilot_core.suggest(cid, ctx.message_id)
assert result['text'].startswith('Voce informou')
assert briefing.admin_view(cid).details.track_count == 24
assert briefing.admin_view(cid).orcamento_id is None
''')

    def test_site_provider_flow_and_conversion_flags(self):
        self.run_case(r'''
from schemas.ai_site import SiteMessage
from services.ai_site_service import SiteChatService
class Scripted:
    def generate(self, data):
        if data.tool_results:
            assert data.tool_results[-1].success
            return ProviderResponse(text='Registro atualizado. Qual a proxima informacao?')
        if 'Quero Mixagem' in data.message:
            args = {'interest':'Mixagem'}; name = 'update_briefing'
        elif 'Sou Ana' in data.message:
            args = {'contact_name':'Ana','contact_email':'ana@example.com'}; name = 'update_briefing'
        else:
            args = {}; name = 'submit_briefing'
        return ProviderResponse(tool_calls=(ToolCall(id=str(uuid4()),name=name,arguments=args),))
site = SiteChatService(ConversationService(SessionLocal, Scripted()))
session = site.create_session()
def send(text):
    return site.message(session.session_token, SiteMessage(message_id=uuid4(),message=text))
first = send('Quero Mixagem da minha musica')
assert first.briefing_started and not first.lead_created
send('Sou Ana, email ana@example.com')
confirmation = SiteMessage(message_id=uuid4(), message='Pode enviar o orcamento')
last = site.message(session.session_token, confirmation)
assert last.lead_created and site.history(session.session_token).lead_created
assert site.message(session.session_token, confirmation).lead_created
assert len(site.history(session.session_token).messages) == 6
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(OrcamentoModel)) == 1
''')


if __name__ == "__main__":
    unittest.main()
