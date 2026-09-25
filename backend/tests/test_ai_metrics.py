"""Technical accounting and aggregate-only API on disposable databases."""
import unittest

import test_bootstrap_database as isolated
from test_ai_core import SETUP


class AIMetricsTests(unittest.TestCase):
    def test_usage_is_recorded_once_and_metrics_are_private(self):
        isolated.BootstrapTests().run_case(SETUP + r'''
from models.ai_usage import AIUsageEventModel as Usage
from schemas.ai_usage import ProviderUsage
from services.ai_metrics_service import metrics
before = metrics(sessions)
assert all(c.conversations_started == 0 and c.total_tokens is None and c.handoff_rate is None for c in before.channels)
class Metered:
    def generate(self, incoming):
        return ProviderResponse(text='Posso ajudar.', usage=ProviderUsage(provider='synthetic',model='test',
            input_tokens=100,output_tokens=20,total_tokens=120,cached_input_tokens=0))
service = ConversationService(sessions, Metered())
cid = conversation()
mid = service.receive(cid, inbound(text='email cliente@example.invalid telefone 11999999999 segredo token'))
service.process(cid, mid)
service.process(cid, mid)
report = metrics(sessions)
site = report.channels[0]
assert site.conversations_started == 1 and site.autonomous_replies == 1
assert site.provider_calls == 1 and site.total_tokens == 120 and site.usage_known_calls == 1
assert site.cost_unknown_calls == 1 and site.costs == []
body = report.model_dump_json()
for forbidden in ('cliente@example.invalid','11999999999','segredo','content','conversation_id'):
    assert forbidden not in body
with sessions() as db:
    assert db.scalar(select(func.count()).select_from(Usage)) == 2
    record = db.scalar(select(Usage).where(Usage.kind == 'provider'))
    assert record.estimated_cost is None and record.latency_ms >= 0
''')

    def test_rates_known_unknown_and_snapshot(self):
        isolated.BootstrapTests().run_case(r'''
from datetime import datetime, timezone
from decimal import Decimal
from schemas.ai_usage import ProviderUsage, UsageRate
from services.ai_usage_service import estimate
now = datetime(2026,9,24,tzinfo=timezone.utc)
usage = ProviderUsage(provider='synthetic',model='test',input_tokens=1000000,
    output_tokens=1000000,total_tokens=2000000,cached_input_tokens=100000)
rate = UsageRate(version='test-v1',provider='synthetic',model='test',effective_from='2026-01-01',
    currency='USD',input_per_million='2',output_per_million='4',cached_input_per_million='1')
assert estimate(usage,[],now) == {}
assert estimate(None,[rate],now) == {}
result = estimate(usage,[rate],now)
assert result['estimated_cost'] == Decimal('5.9') and result['currency'] == 'USD'
assert result['rate_snapshot']['version'] == 'test-v1'
assert estimate(usage.model_copy(update={'cached_input_tokens':None}),[rate],now) == {}
assert estimate(usage,[rate.model_copy(update={'effective_from':now.date().replace(year=2027)})],now) == {}
assert result['rate_snapshot']['input_per_million'] == '2'
''')

    def test_openai_usage_and_error_capture_without_network(self):
        isolated.BootstrapTests().run_case(r'''
import httpx
from schemas.ai import ProviderInput
from services.ai_openai_provider import OpenAIProvider
from services.ai_provider import ProviderError
incoming = ProviderInput(system='safe',message='private text')
for status in ('completed','incomplete'):
    def handler(request):
        return httpx.Response(200,json={'status':status,'model':'synthetic',
            'usage':{'input_tokens':10,'output_tokens':2,'total_tokens':12,'input_tokens_details':{'cached_tokens':0}},
            'output':[{'type':'message','content':[{'type':'output_text','text':'Ola'}]}]})
    adapter = OpenAIProvider('synthetic-secret','synthetic',transport=httpx.MockTransport(handler))
    try:
        result = adapter.generate(incoming)
        assert status == 'completed' and result.usage.total_tokens == 12
    except ProviderError as error:
        assert status == 'incomplete' and error.usage.total_tokens == 12
def no_usage(request):
    return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'Ola'}]}]})
response = OpenAIProvider('secret','test',transport=httpx.MockTransport(no_usage)).generate(incoming)
assert response.usage.total_tokens is None
''')

    def test_metrics_authentication_and_period(self):
        isolated.BootstrapTests().run_case(SETUP + r'''
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.dependencies import require_ai_operator
from routers import ai_inbox
from types import SimpleNamespace
app = FastAPI()
app.include_router(ai_inbox.router)
client = TestClient(app)
assert client.get('/admin/ai/conversations/metrics').status_code == 401
app.dependency_overrides[require_ai_operator] = lambda: SimpleNamespace(id=1)
ai_inbox.SessionLocal = sessions
assert client.get('/admin/ai/conversations/metrics?days=7').status_code == 200
assert client.get('/admin/ai/conversations/metrics?days=30').status_code == 200
assert client.get('/admin/ai/conversations/metrics?days=8').status_code == 422
''')

    def test_cohort_handoff_and_copilot_accounting(self):
        isolated.BootstrapTests().run_case(SETUP + r'''
from services.ai_metrics_service import metrics
from services.ai_inbox_service import AIInboxService
from schemas.ai_inbox import InboxMessageCreate
from types import SimpleNamespace
with sessions.begin() as db:
    db.add(UsuarioModel(id=1,username='operator',password_hash='unused',ativo=True))
cid = conversation(mode='copilot',assigned_user_id=1)
mid = service.receive(cid,inbound())
inbox = AIInboxService(sessions,service)
actor = SimpleNamespace(id=1)
draft = inbox.suggest(cid,actor)
payload = InboxMessageCreate(text='Resposta revisada',suggestion_id=draft['id'],idempotency_key='synthetic-idempotency')
inbox.send_message(cid,payload,actor)
inbox.send_message(cid,payload,actor)
other = conversation()
message = service.receive(other,inbound(text='Quero atendente'))
service.process(other,message)
report = metrics(sessions).channels[0]
assert report.copilot_generated == 1 and report.copilot_used == 1
assert report.human_replies == 1 and report.cohort_handoffs == 1 and report.handoff_rate == 0.5
assert report.handoff_reasons == {'manual_request':1}
''')

    def test_copilot_rate_limit_is_bounded_and_fail_closed(self):
        isolated.BootstrapTests().run_case(SETUP + r'''
import os, tempfile
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.dependencies import require_ai_operator
from routers import ai_inbox
from types import SimpleNamespace
app = FastAPI()
app.include_router(ai_inbox.router)
app.dependency_overrides[require_ai_operator] = lambda: SimpleNamespace(id=99)
app.dependency_overrides[ai_inbox.get_inbox_service] = lambda: SimpleNamespace(suggest=lambda *args: {
    'id':str(uuid4()),'conversation_id':str(uuid4()),'target_message_id':str(uuid4()),
    'text':'synthetic','created_at':datetime.now(timezone.utc)})
with tempfile.TemporaryDirectory() as directory:
    os.environ['RATE_LIMIT_DB'] = str(Path(directory) / 'rate.sqlite')
    client = TestClient(app)
    path = '/admin/ai/conversations/' + str(uuid4()) + '/suggestions'
    for _ in range(20):
        assert client.post(path,json={}).status_code == 200
    response = client.post(path,json={})
    assert response.status_code == 429 and int(response.headers['retry-after']) > 0
    def broken(*args):
        raise RuntimeError('private diagnostic')
    ai_inbox.allow_request = broken
    response = client.post(path,json={})
    assert response.status_code == 503 and 'private diagnostic' not in response.text
''')

    def test_logs_and_technical_rows_exclude_content(self):
        isolated.BootstrapTests().run_case(SETUP + r'''
import io, logging
from schemas.ai import ToolCall
from services.ai_tools import ToolExecutionContext, ToolRegistry
from models.ai_usage import AIUsageEventModel as U
from services.ai_usage_service import UsageRecorder
buffer = io.StringIO()
handler = logging.StreamHandler(buffer)
root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(handler)
cid = conversation()
mid = service.receive(cid,inbound(text='private@example.invalid 11999999999 private-message'))
ctx = ToolExecutionContext(conversation_id=cid,message_id=mid,mode='autonomous',source='site',request_id='private-reference')
recorder = UsageRecorder(sessions,ctx)
ToolRegistry().run(ToolCall(id='private-call',name='private_secret_token',
    arguments={'email':'private@example.invalid','phone':'11999999999'}),ctx,telemetry=recorder)
service.process(cid,mid)
root.removeHandler(handler)
with sessions() as db:
    rows = [dict((column.name,getattr(row,column.name)) for column in U.__table__.columns) for row in db.scalars(select(U))]
combined = buffer.getvalue() + str(rows)
for forbidden in ('private@example.invalid','11999999999','private-message','private_secret_token','private-reference','private-call'):
    assert forbidden not in combined, forbidden
assert 'unregistered' in combined
''')

    def test_cost_snapshot_is_persisted_and_not_repriced(self):
        isolated.BootstrapTests().run_case(SETUP + r'''
from decimal import Decimal
from schemas.ai_usage import ProviderUsage, UsageRate
from services.ai_usage_service import UsageRecorder
from services.ai_tools import ToolExecutionContext
from services.ai_metrics_service import metrics
from models.ai_usage import AIUsageEventModel as U
cid = conversation()
mid = service.receive(cid,inbound())
ctx = ToolExecutionContext(conversation_id=cid,message_id=mid,mode='autonomous',source='site')
usage = ProviderUsage(provider='synthetic',model='test',input_tokens=1000000,output_tokens=1000000,
                      total_tokens=2000000,cached_input_tokens=0)
rate = UsageRate(version='v1',provider='synthetic',model='test',effective_from='2020-01-01',
    currency='USD',input_per_million='1',output_per_million='2',cached_input_per_million='0')
recorder = UsageRecorder(sessions,ctx,rates=[rate])
assert UsageRecorder(sessions,ctx,rates=[rate,rate]).rates == []
recorder.emit(kind='provider',result='success',usage=usage)
recorder.rates = [rate.model_copy(update={'version':'v2','input_per_million':Decimal('5')})]
recorder.emit(kind='provider',result='success',usage=usage)
with sessions() as db:
    rows = db.scalars(select(U).order_by(U.created_at)).all()
    assert rows[0].estimated_cost == Decimal('3') and rows[0].rate_snapshot['version'] == 'v1'
    assert rows[1].estimated_cost == Decimal('7') and rows[1].rate_snapshot['version'] == 'v2'
report = metrics(sessions).channels[0]
assert report.costs[0].amount == Decimal('10') and report.costs[0].currency == 'USD'
assert report.cost_unknown_calls == 0
''')


if __name__ == '__main__':
    unittest.main()
