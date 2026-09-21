"""AI core contracts using the existing isolated SQLite subprocess harness."""

import unittest

import test_bootstrap_database as isolated


SETUP = r'''
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker, configure_mappers
from pydantic import ValidationError
from models import AIConversationModel as Conversation, AIMessageModel as Message, ClienteModel, UsuarioModel
from schemas.ai import ConversationCreate, InboundMessage, ProviderResponse, HandoffReason, ConversationMode, DecisionAction
from services.ai_conversation_service import ConversationService, ConversationError
from services.ai_orchestrator import Decision
from services.ai_provider import ProviderError

@event.listens_for(engine, 'connect')
def foreign_keys(connection, record):
    connection.execute('PRAGMA foreign_keys=ON')

bootstrap(engine)
configure_mappers()
sessions = sessionmaker(engine)

class FakeProvider:
    def __init__(self):
        self.calls = []
    def generate(self, incoming):
        assert engine.pool.checkedout() == 0, 'provider called with an open database connection'
        self.calls.append(incoming)
        return ProviderResponse(text='Informacao de teste')

provider = FakeProvider()
service = ConversationService(sessions, provider)
def conversation(mode='autonomous', **kwargs):
    return service.create(ConversationCreate(channel='site', mode=mode, **kwargs))
def inbound(text='Como funciona?', key=None, **kwargs):
    return InboundMessage(channel='site', external_message_id=key or str(uuid4()), text=text,
                          received_at=datetime.now(timezone.utc), **kwargs)
def expect_error(code, callback):
    try:
        callback()
    except ConversationError as error:
        assert str(error) == code, str(error)
    else:
        raise AssertionError('expected ' + code)
'''


class AICoreTests(unittest.TestCase):
    def run_case(self, source):
        isolated.BootstrapTests().run_case(SETUP + source)

    def test_identity_models_and_constraints(self):
        self.run_case(r'''
cid = conversation()
with sessions() as db:
    anonymous = db.get(Conversation, cid)
    assert anonymous.cliente_id is None and anonymous.anonymous_session_id
    db.add(ClienteModel(id=1, nome='Cliente', email='test@example.invalid'))
    db.add(UsuarioModel(id=1, username='operador', password_hash='unused', ativo=True))
    db.commit()
linked = conversation(cliente_id=1, assigned_user_id=1)
with sessions() as db:
    item = db.get(Conversation, linked)
    assert item.cliente.nome == 'Cliente' and item.assigned_user.username == 'operador'
    assert item.anonymous_session_id is None
expect_error('cliente_not_found', lambda: conversation(cliente_id=999))
expect_error('assigned_user_invalid', lambda: conversation(assigned_user_id=999))
for column in ['status', 'mode', 'channel']:
    with sessions() as db:
        try:
            db.execute(update(Conversation).where(Conversation.id == cid).values(**{column:'invalid'}))
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError('DB accepted invalid ' + column)
''')

    def test_inbound_outbound_idempotency_and_payload_conflict(self):
        self.run_case(r'''
cid = conversation()
incoming = inbound(key='stable-adapter-key')
mid = service.receive(cid, incoming)
assert service.receive(cid, incoming) == mid
expect_error('idempotency_conflict', lambda: service.receive(cid, incoming.model_copy(update={'text':'changed'})))
result = service.process(cid, mid)
assert result.action == 'reply' and result.outbound.kind == 'reply'
replayed = service.process(cid, mid)
assert replayed == result and len(provider.calls) == 1
with sessions() as db:
    assert db.scalar(select(func.count()).select_from(Message)) == 2
    original = db.get(Message, mid)
    duplicate = Message(conversation_id=cid, direction='inbound', role='user', channel='site',
                        content=original.content, external_message_id=original.external_message_id)
    db.add(duplicate)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError('DB accepted duplicate inbound')
    db.add(Message(conversation_id=cid, direction='outbound', role='assistant', channel='site',
                   content='duplicate', kind='reply', reply_to_id=mid))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    else:
        raise AssertionError('DB accepted duplicate reply')
''')

    def test_handoff_is_deterministic_idempotent_and_blocks_automation(self):
        self.run_case(r'''
for text, reason in [
    ('Quero desconto', 'discount'), ('Podemos negociar?', 'negotiation'),
    ('Preciso de preco personalizado', 'custom_pricing'), ('Quero estorno', 'payment_issue'),
    ('Tenho uma reclamacao', 'complaint'), ('Quero falar com atendente', 'manual_request'),
    ('Quero fechar essa proposta', 'negotiation'), ('Problema com o pagamento', 'payment_issue'),
    ('Quero falar com uma pessoa', 'manual_request'),
]:
    cid = conversation()
    mid = service.receive(cid, inbound(text))
    result = service.process(cid, mid)
    assert result.action == 'handoff' and result.reason == reason
    assert service.process(cid, mid) == result
    with sessions() as db:
        before = db.get(Conversation, cid).version
    assert service.handoff(cid, HandoffReason.OTHER) == reason
    with sessions() as db:
        current = db.get(Conversation, cid)
        assert current.version == before and current.status == 'waiting_human' and current.mode == 'human'
    later = service.receive(cid, inbound('Ola novamente'))
    assert service.process(cid, later).action == 'no_action'
assert provider.calls == []
''')

    def test_modes_closed_and_drafts_are_not_spoken_history(self):
        self.run_case(r'''
human = conversation('human')
mid = service.receive(human, inbound())
assert service.process(human, mid).action == 'no_action' and not provider.calls
copilot = conversation('copilot')
first = service.receive(copilot, inbound('Pergunta um'))
result = service.process(copilot, first)
assert result.action == 'suggestion' and result.outbound.kind == 'suggestion'
second = service.receive(copilot, inbound('Pergunta dois'))
service.process(copilot, second)
assert all(item.role == 'user' for item in provider.calls[-1].history)
service.close(copilot)
service.close(copilot)
expect_error('conversation_closed', lambda: service.receive(copilot, inbound()))
expect_error('conversation_closed', lambda: service.process(copilot, second))
with sessions() as db:
    assert db.get(Conversation, copilot).closed_at is not None
''')

    def test_identity_isolation_and_safe_dtos(self):
        self.run_case(r'''
cid = conversation(external_thread_id='opaque-thread', sender_reference='opaque-sender')
expect_error('conversation_identity_mismatch', lambda: service.receive(cid, inbound()))
right = inbound(external_thread_id='opaque-thread', sender_reference='opaque-sender')
mid = service.receive(cid, right)
other = conversation()
expect_error('message_not_found', lambda: service.process(other, mid))
expect_error('conversation_not_found', lambda: service.receive(str(uuid4()), inbound()))
for change in [{'metadata':{'email':'private@example.invalid'}}, {'external_message_id':''},
               {'text':' '}, {'text':'x'*8001}, {'channel':'whatsapp'}, {'received_at':'2026-01-01T00:00:00'}]:
    try:
        InboundMessage.model_validate({**right.model_dump(), **change})
    except ValidationError:
        pass
    else:
        raise AssertionError('unsafe inbound accepted')
''')

    def test_history_order_and_context_bounds(self):
        self.run_case(r'''
cid = conversation()
for number in range(13):
    mid = service.receive(cid, inbound('Pergunta ' + str(number)))
    service.process(cid, mid, context=('Conhecimento aprovado',))
assert len(provider.calls[-1].history) == 20
assert provider.calls[-1].context[0] == 'Conhecimento aprovado'
assert any('"kind": "brand"' in item for item in provider.calls[-1].context)
assert provider.calls[-1].system != provider.calls[-1].message
rows = service.history(cid, limit=100)
assert len(rows) == 26
assert [(row.created_at, row.id) for row in rows] == sorted((row.created_at, row.id) for row in rows)
mid = service.receive(cid, inbound())
try:
    service.claim(cid, mid, context=tuple('item' for _ in range(9)))
except ValidationError:
    pass
else:
    raise AssertionError('unbounded context accepted')
with sessions() as db:
    assert db.get(Conversation, cid).claim_token is None
''')

    def test_timeout_retry_and_exhaustion_keep_inbound(self):
        self.run_case(r'''
class TimeoutProvider:
    def generate(self, incoming):
        raise TimeoutError('private@example.invalid secret phone')
timed = ConversationService(sessions, TimeoutProvider(), max_attempts=2)
cid = conversation()
mid = timed.receive(cid, inbound())
result = timed.process(cid, mid)
assert result.action == 'error' and result.retryable and result.error_code == 'provider_timeout'
assert result.outbound is None
result = timed.process(cid, mid)
assert result.action == 'handoff' and result.error_code == 'retry_exhausted' and not result.retryable
assert timed.process(cid, mid) == result
assert len(timed.history(cid)) == 1

cid = conversation()
mid = timed.receive(cid, inbound())
assert timed.process(cid, mid).retryable
assert service.process(cid, mid).action == 'reply'
assert len(service.history(cid)) == 2
''')

    def test_provider_errors_low_confidence_and_disabled_default(self):
        self.run_case(r'''
class BrokenProvider:
    def __init__(self, value): self.value = value
    def generate(self, incoming):
        if isinstance(self.value, Exception): raise self.value
        return self.value
for value, code, reason in [
    (ProviderError('provider_unavailable'), 'provider_unavailable', 'provider_failure'),
    ({'text':''}, 'provider_invalid_response', 'provider_failure'),
    (RuntimeError('secret'), 'provider_unavailable', 'provider_failure'),
    (ProviderResponse(handoff_reason=HandoffReason.LOW_CONFIDENCE), None, 'low_confidence'),
    (ProviderResponse(text='partial', finish_reason='length'), None, 'low_confidence'),
]:
    current = ConversationService(sessions, BrokenProvider(value))
    cid = conversation()
    mid = current.receive(cid, inbound())
    result = current.process(cid, mid)
    assert result.action == 'handoff' and result.reason == reason and result.error_code == code
    assert result.outbound is None
disabled = ConversationService(sessions)
cid = conversation()
assert disabled.process(cid, disabled.receive(cid, inbound())).error_code == 'provider_unavailable'
''')

    def test_lease_expiry_recovery_and_fencing(self):
        self.run_case(r'''
now = [datetime.now(timezone.utc)]
leased = ConversationService(sessions, provider, clock=lambda: now[0], lease_seconds=10)
cid = conversation()
mid = leased.receive(cid, inbound())
claim_a = leased.claim(cid, mid)
expect_error('processing_conflict', lambda: leased.claim(cid, mid))
now[0] += timedelta(seconds=11)
claim_b = leased.claim(cid, mid)
assert claim_a.token != claim_b.token
expect_error('processing_conflict', lambda: leased.complete(claim_a, Decision(DecisionAction.REPLY, text='stale')))
reply = leased.complete(claim_b, Decision(DecisionAction.REPLY, text='valid'))
assert leased.process(cid, mid) == reply
expect_error('processing_conflict', lambda: leased.complete(claim_b, Decision(DecisionAction.REPLY, text='duplicate')))
assert len(leased.history(cid)) == 2
''')

    def test_human_takeover_during_provider_discards_late_reply(self):
        self.run_case(r'''
cid = conversation()
class TakeoverProvider:
    def generate(self, incoming):
        service.handoff(cid, HandoffReason.MANUAL_REQUEST)
        return ProviderResponse(text='late response')
current = ConversationService(sessions, TakeoverProvider())
mid = current.receive(cid, inbound())
expect_error('processing_conflict', lambda: current.process(cid, mid))
assert current.process(cid, mid).action == 'no_action'
assert len(current.history(cid)) == 1

cid = conversation()
mid = service.receive(cid, inbound())
claim = service.claim(cid, mid)
service.set_mode(cid, ConversationMode.COPILOT)
expect_error('processing_conflict', lambda: service.complete(claim, Decision(DecisionAction.REPLY, text='late')))
assert service.process(cid, mid).action == 'suggestion'
''')

    def test_interrupted_workers_exhaust_budget_and_closed_claim_is_fenced(self):
        self.run_case(r'''
now = [datetime.now(timezone.utc)]
current = ConversationService(sessions, provider, clock=lambda: now[0], lease_seconds=10, max_attempts=2)
cid = conversation()
mid = current.receive(cid, inbound())
current.claim(cid, mid)
now[0] += timedelta(seconds=11)
current.claim(cid, mid)
now[0] += timedelta(seconds=11)
result = current.process(cid, mid)
assert result.action == 'handoff' and result.error_code == 'retry_exhausted'
assert current.process(cid, mid) == result and not provider.calls

cid = conversation()
mid = service.receive(cid, inbound())
claim = service.claim(cid, mid)
service.close(cid)
expect_error('processing_conflict', lambda: service.complete(claim, Decision(DecisionAction.REPLY, text='late')))
assert len(service.history(cid)) == 1

cid = conversation()
mid = service.receive(cid, inbound())
service.process(cid, mid)
service.handoff(cid, HandoffReason.MANUAL_REQUEST)
assert service.process(cid, mid).action == 'no_action'
''')

    def test_parallel_receives_claims_and_message_order(self):
        self.run_case(r'''
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
cid = conversation()
incoming = inbound()
with ThreadPoolExecutor(max_workers=2) as pool:
    ids = list(pool.map(lambda _: service.receive(cid, incoming), range(2)))
assert ids[0] == ids[1] and len(service.history(cid)) == 1
barrier = Barrier(2)
def compete(_):
    barrier.wait(timeout=5)
    try: return service.claim(cid, ids[0])
    except ConversationError as error: return str(error)
with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(compete, range(2)))
assert sum(isinstance(result, str) for result in results) == 1
assert 'processing_conflict' in results
winner = next(result for result in results if not isinstance(result, str))
second = service.receive(cid, inbound('Segunda'))
expect_error('processing_conflict', lambda: service.claim(cid, second))
service.complete(winner, Decision(DecisionAction.REPLY, text='Primeira'))
assert service.process(cid, second).action == 'reply'
assert any(entry.text == 'Primeira' for entry in provider.calls[-1].history)
''')

    def test_persistence_failure_keeps_inbound_and_recovers_after_lease(self):
        self.run_case(r'''
from sqlalchemy.exc import OperationalError
now = [datetime.now(timezone.utc)]
current = ConversationService(sessions, provider, clock=lambda: now[0], lease_seconds=10)
cid = conversation()
mid = current.receive(cid, inbound())
claim = current.claim(cid, mid)
def fail_reply(conn, cursor, statement, parameters, context, many):
    if statement.lstrip().upper().startswith('INSERT INTO AI_MESSAGES'):
        raise OperationalError('private statement', {}, Exception('private secret'))
event.listen(engine, 'before_cursor_execute', fail_reply)
expect_error('storage_unavailable', lambda: current.complete(claim, Decision(DecisionAction.REPLY, text='attempt')))
event.remove(engine, 'before_cursor_execute', fail_reply)
assert len(current.history(cid)) == 1
now[0] += timedelta(seconds=11)
assert current.process(cid, mid).action == 'reply'
assert len(current.history(cid)) == 2
''')

    def test_tools_are_explicit_and_errors_sanitized(self):
        self.run_case(r'''
from pydantic import BaseModel, ConfigDict
from services.ai_tools import Tool, ToolCategory, ToolExecutionContext, ToolRegistry, ToolError
class Args(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: int
context = ToolExecutionContext(conversation_id=uuid4(), mode='autonomous', source='site')
registry = ToolRegistry([Tool('test_echo', 'Echo test', ToolCategory.PUBLIC_READ,
                              Args, Args, lambda context, data: data)])
assert registry.execute('test_echo', {'value':2}, context).value == 2
for name, args, code in [('eval', {'value':1}, 'tool_not_allowed'),
                         ('test_echo', {'value':1,'secret':'private'}, 'tool_invalid_arguments')]:
    try: registry.execute(name, args, context)
    except ToolError as error: assert str(error) == code
    else: raise AssertionError('unsafe tool accepted')
def fail(context, data): raise RuntimeError('private@example.invalid')
registry = ToolRegistry([Tool('test_fail', 'Failure test', ToolCategory.PUBLIC_READ,
                              Args, Args, fail)])
try: registry.execute('test_fail', {'value':1}, context)
except ToolError as error: assert str(error) == 'tool_temporarily_unavailable'
else: raise AssertionError('tool failure hidden')
''')

    def test_logs_do_not_copy_sensitive_input_or_exceptions(self):
        self.run_case(r'''
import io, logging
output = io.StringIO()
handler = logging.StreamHandler(output)
log = logging.getLogger('services.ai_conversation_service')
log.setLevel(logging.INFO)
log.addHandler(handler)
secret = 'sensitive@example.invalid phone=5511999990000 provider-token=TEST_SECRET'
class Fail:
    def generate(self, incoming): raise RuntimeError(secret)
current = ConversationService(sessions, Fail())
cid = conversation()
current.process(cid, current.receive(cid, inbound(secret, metadata={'request_id':'5511999990000'})))
logged = output.getvalue()
assert 'ai_processed' in logged and cid in logged
for value in ['sensitive@example.invalid', '5511999990000', 'TEST_SECRET', secret]:
    assert value not in logged
assert 'sha256:' in logged
cid = conversation()
mid = service.receive(cid, inbound(metadata={'request_id':'request-user-create-001'}))
assert service.process(cid, mid).outbound.metadata.request_id == 'request-user-create-001'
''')


if __name__ == "__main__":
    unittest.main()
