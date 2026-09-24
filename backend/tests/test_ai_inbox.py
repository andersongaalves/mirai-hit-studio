"""Focused Inbox workflows on a disposable SQLite database."""

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


SETUP = """
import sys, types
from pathlib import Path
config = types.ModuleType('core.config')
config.settings = types.SimpleNamespace(
    DATABASE_URL=__DATABASE_URL__, SECRET_KEY='test-only', ALGORITHM='HS256',
    API_NAME='Test', API_VERSION='1', DEBUG=False, HOST='localhost', PORT=8000,
    LOG_LEVEL='WARNING', ACCESS_TOKEN_EXPIRE_MINUTES=10, REFRESH_TOKEN_EXPIRE_DAYS=1,
    ALLOWED_ORIGINS='http://localhost', BACKUP_FOLDER=__TEMP_DIR__, BACKUP_KEEP_DAYS=1,
    RESEND_API_KEY='', EMAIL_FROM='test@example.invalid', ADMIN_EMAIL='test@example.invalid',
    AI_ENABLED=True, AI_MODEL='test', AI_API_KEY='test-only', AI_TIMEOUT_SECONDS=8,
    AI_SESSION_HOURS=24, AI_EMAIL_ENABLED=False, AI_EMAIL_FROM='',
    AI_EMAIL_MAX_BODY_CHARS=8000)
sys.modules['core.config'] = config
from database import Base, SessionLocal, engine
from scripts.bootstrap_database import bootstrap
bootstrap(engine)
from models.ai import AIConversationModel, AIMessageModel
from models.usuario import UsuarioModel
from schemas.ai import ConversationCreate, InboundMessage, ProviderResponse, ConversationMode, HandoffReason
from schemas.ai_inbox import InboxMessageCreate
from services.ai_conversation_service import ConversationService
from services.ai_inbox_service import AIInboxService, InboxError

class FakeAI:
    def generate(self, incoming):
        return ProviderResponse(text='Sugestao segura para o atendente')

core = ConversationService(SessionLocal, FakeAI())
service = AIInboxService(SessionLocal, core)
with SessionLocal.begin() as db:
    db.add(UsuarioModel(id=1, username='admin', password_hash='hash', is_admin=True, ativo=True, role='admin'))
actor = types.SimpleNamespace(id=1, role='admin', ativo=True, is_admin=True)
"""


class AIInboxTests(unittest.TestCase):
    def run_case(self, source):
        with tempfile.TemporaryDirectory(prefix='mirai-ai-inbox-') as directory:
            url = 'sqlite:///' + (Path(directory) / 'test.db').as_posix()
            preamble = SETUP.replace('__DATABASE_URL__', repr(url)).replace('__TEMP_DIR__', repr(directory))
            result = subprocess.run(
                [sys.executable, '-B', '-c', preamble + textwrap.dedent(source)],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_handoff_assign_copilot_suggestion_and_idempotent_reply(self):
        self.run_case("""
            from datetime import datetime, timezone
            conversation_id = core.create(ConversationCreate(
                channel='site', mode=ConversationMode.AUTONOMOUS,
                external_thread_id='site-thread-1', sender_reference='browser-session-1'))
            message_id = core.receive(conversation_id, InboundMessage(
                channel='site', external_message_id='message-1', external_thread_id='site-thread-1',
                sender_reference='browser-session-1', text='Preciso de orientacao sobre o servico',
                received_at=datetime.now(timezone.utc)))
            core.handoff(conversation_id, HandoffReason.OTHER)
            detail = service.assign(conversation_id, actor)
            assert detail['mode'] == 'human'
            detail = service.set_mode(conversation_id, ConversationMode.COPILOT, actor)
            suggestion = service.suggest(conversation_id, actor)
            assert suggestion['text'] == 'Sugestao segura para o atendente'
            sent = service.send_message(conversation_id, InboxMessageCreate(
                text='Resposta revisada', suggestion_id=suggestion['id'], idempotency_key='reply-key-001'), actor)
            repeated = service.send_message(conversation_id, InboxMessageCreate(
                text='Resposta revisada', suggestion_id=suggestion['id'], idempotency_key='reply-key-001'), actor)
            assert sent['delivery'] == 'sent' and repeated['delivery'] == 'already_sent'
            with SessionLocal() as db:
                messages = db.query(AIMessageModel).filter_by(conversation_id=conversation_id).all()
                assert {(row.kind, row.direction) for row in messages} == {('message', 'inbound'), ('message', 'outbound')}
                assert len(messages) == 2
        """)

    def test_stale_suggestion_is_rejected(self):
        self.run_case("""
            from datetime import datetime, timezone
            conversation_id = core.create(ConversationCreate(
                channel='site', mode=ConversationMode.COPILOT,
                external_thread_id='site-thread-2', sender_reference='browser-session-2'))
            first = core.receive(conversation_id, InboundMessage(
                channel='site', external_message_id='message-a', external_thread_id='site-thread-2',
                sender_reference='browser-session-2', text='Preciso de ajuda', received_at=datetime.now(timezone.utc)))
            service.assign(conversation_id, actor)
            service.set_mode(conversation_id, ConversationMode.COPILOT, actor)
            suggestion = service.suggest(conversation_id, actor, first)
            core.receive(conversation_id, InboundMessage(
                channel='site', external_message_id='message-b', external_thread_id='site-thread-2',
                sender_reference='browser-session-2', text='Outra mensagem', received_at=datetime.now(timezone.utc)))
            try:
                service.send_message(conversation_id, InboxMessageCreate(
                    text='Resposta antiga', suggestion_id=suggestion['id'], idempotency_key='reply-key-002'), actor)
            except InboxError as error:
                assert str(error) == 'stale_suggestion'
            else:
                raise AssertionError('stale suggestion accepted')
        """)

    def test_list_filters_privacy_assignment_and_modes(self):
        self.run_case("""
            from datetime import datetime, timezone
            from sqlalchemy import select
            with SessionLocal.begin() as db:
                db.add(UsuarioModel(id=2, username='produtor', password_hash='hash', is_admin=False, ativo=True, role='produtor'))
            other = types.SimpleNamespace(id=2, role='produtor', ativo=True)
            first = core.create(ConversationCreate(channel='site', mode='autonomous',
                external_thread_id='site-list-1', sender_reference='site-session:private-hash'))
            second = core.create(ConversationCreate(channel='email', mode='autonomous',
                external_thread_id='email-thread:private-hash', sender_reference='client@example.invalid'))
            core.handoff(first, HandoffReason.OTHER)
            page = service.list(status=None, mode=None, channel=None, handoff=True)
            assert page['total'] == 1 and page['items'][0]['id'] == first
            assert service.list(channel='email')['items'][0]['id'] == second
            assert service.list(page_size=1)['pages'] == 2
            assert service.detail(first)['sender_reference'] is None
            service.assign(first, actor)
            try: service.assign(first, other)
            except InboxError as error: assert str(error) == 'conversation_already_assigned'
            else: raise AssertionError('another operator took the conversation')
            try: service.send_message(first, InboxMessageCreate(text='Intrusao', idempotency_key='test-other-001'), other)
            except InboxError as error: assert str(error) == 'conversation_not_assigned'
            else: raise AssertionError('other operator sent')
            try: service.set_mode(first, ConversationMode.AUTONOMOUS, actor)
            except InboxError as error: assert str(error) == 'autonomous_mode_admin_locked'
            else: raise AssertionError('unsafe autonomous transition')
            service.close(first, actor)
            assert service.detail(first)['status'] == 'closed'
            assert service.list(status=__import__('schemas.ai', fromlist=['ConversationStatus']).ConversationStatus.OPEN)['total'] == 1
        """)

    def test_email_delivery_failure_retry_thread_and_manual_without_ai(self):
        self.run_case("""
            from datetime import datetime, timezone
            from models.ai import AIEmailThreadModel
            from services.ai_email_service import AIEmailService
            class FakeEmail:
                calls = []
                fail = True
                def send_reply(self, **payload):
                    self.calls.append(payload)
                    if self.fail: raise RuntimeError('private provider error')
                    return 'provider-id-1'
            email = FakeEmail()
            delivery = AIEmailService(ConversationService(SessionLocal), email,
                sender_address='assistente@example.invalid')
            offline = AIInboxService(SessionLocal, ConversationService(SessionLocal), delivery)
            conversation_id = core.create(ConversationCreate(channel='email', mode='human',
                external_thread_id='email-thread:test', sender_reference='client@example.invalid'))
            with SessionLocal.begin() as db:
                db.add(AIEmailThreadModel(conversation_id=conversation_id,
                    sender_email='client@example.invalid', subject='Assunto',
                    root_message_id='root@example.invalid', last_inbound_message_id='last@example.invalid'))
            offline.assign(conversation_id, actor)
            payload = InboxMessageCreate(text='Resposta humana', idempotency_key='email-human-001')
            try: offline.send_message(conversation_id, payload, actor)
            except InboxError as error: assert str(error) == 'delivery_unavailable'
            else: raise AssertionError('provider failure hidden')
            pending = offline.detail(conversation_id)['messages'][0]
            assert pending['delivery'] == 'pending' and pending['content'] == 'Resposta humana'
            email.fail = False
            result = offline.retry_message(conversation_id, pending['id'], actor)
            assert result['delivery'] == 'sent'
            assert offline.retry_message(conversation_id, pending['id'], actor)['delivery'] == 'already_sent'
            assert len(email.calls) == 2
            assert email.calls[0]['recipient'] == 'client@example.invalid'
            assert email.calls[0]['headers']['In-Reply-To'] == '<last@example.invalid>'
            assert '<root@example.invalid>' in email.calls[0]['headers']['References']
            assert email.calls[0]['idempotency_key'] == email.calls[1]['idempotency_key']
            assert offline.detail(conversation_id)['messages'][0]['delivery'] == 'sent'
        """)

    def test_routes_require_auth_and_reject_unauthorized_role(self):
        self.run_case("""
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from core.dependencies import get_current_user
            from routers.ai_inbox import router, get_inbox_service
            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_inbox_service] = lambda: service
            client = TestClient(app)
            assert client.get('/admin/ai/conversations').status_code == 401
            app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(
                id=3, role='visitor', ativo=True, is_admin=False)
            assert client.get('/admin/ai/conversations').status_code == 403
            app.dependency_overrides[get_current_user] = lambda: actor
            response = client.get('/admin/ai/conversations')
            assert response.status_code == 200 and response.json()['items'] == []
            assert client.post('/admin/ai/conversations/missing/messages', json={
                'text':'ok', 'channel':'email', 'to':'attacker@example.invalid',
                'idempotency_key':'test-extra-001'}).status_code == 422
        """)

    def test_site_human_reply_stays_in_own_guest_history_without_provider(self):
        self.run_case("""
            from services.ai_site_service import SiteChatService
            from sqlalchemy import select
            site = SiteChatService(ConversationService(SessionLocal))
            session_a = site.create_session()
            session_b = site.create_session()
            conversation_a = site.resolve(session_a.session_token)
            service.assign(conversation_a.id, actor)
            sent = service.send_message(conversation_a.id, InboxMessageCreate(
                text='Atendimento humano', idempotency_key='site-human-001'), actor)
            assert sent['delivery'] == 'sent'
            history_a = site.history(session_a.session_token)
            history_b = site.history(session_b.session_token)
            assert history_a.awaiting_human is True
            assert len(history_a.messages) == 1 and history_a.messages[0].sender == 'human'
            assert history_a.messages[0].message_id == str(sent['message']['id'])
            assert history_b.messages == []
        """)

    def test_regenerate_ignore_and_message_history_window(self):
        self.run_case("""
            from datetime import datetime, timezone
            conversation_id = core.create(ConversationCreate(channel='site', mode='human',
                external_thread_id='site-history', sender_reference='site-session:test'))
            first = core.receive(conversation_id, InboundMessage(channel='site',
                external_message_id='history-1', external_thread_id='site-history',
                sender_reference='site-session:test', text='Informacao do servico',
                received_at=datetime.now(timezone.utc)))
            service.assign(conversation_id, actor)
            service.set_mode(conversation_id, ConversationMode.COPILOT, actor)
            draft_a = service.suggest(conversation_id, actor)
            draft_b = service.suggest(conversation_id, actor)
            assert draft_a['id'] == draft_b['id']
            assert service.detail(conversation_id)['messages'][-1]['delivery'] == 'draft'
            service.ignore_suggestion(conversation_id, draft_a['id'], actor)
            assert len(service.detail(conversation_id)['messages']) == 1
            second = core.receive(conversation_id, InboundMessage(channel='site',
                external_message_id='history-2', external_thread_id='site-history',
                sender_reference='site-session:test', text='Nova pergunta',
                received_at=datetime.now(timezone.utc)))
            latest = service.detail(conversation_id, limit=1)
            assert len(latest['messages']) == 1 and latest['has_more_messages']
            older = service.detail(conversation_id, before=latest['next_before'], limit=1)
            assert len(older['messages']) == 1
            assert {latest['messages'][0]['id'], older['messages'][0]['id']} == {first, second}
        """)


if __name__ == '__main__':
    unittest.main()
