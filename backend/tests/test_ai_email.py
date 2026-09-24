"""AI email channel tests use SQLite and provider fakes only."""

import textwrap
import unittest

import test_bootstrap_database


SETUP = """
from datetime import datetime, timezone
from uuid import uuid4
from database import SessionLocal
from models import ClienteModel
from models.ai import AIConversationModel, AIEmailThreadModel, AIMessageModel
from schemas.ai import HandoffReason, ProviderResponse
from services.ai_conversation_service import ConversationService
from services.ai_email_service import AIEmailError, AIEmailService
from sqlalchemy import select, func
bootstrap(engine)

class FakeAI:
    calls = 0
    handoff = False
    def generate(self, incoming):
        self.calls += 1
        if self.handoff:
            return ProviderResponse(handoff_reason=HandoffReason.MANUAL_REQUEST)
        return ProviderResponse(text='Resposta segura da Mirai')

class FakeEmail:
    sent = []
    retrieved = []
    fail_send = False
    def retrieve_received(self, email_id):
        self.retrieved.append(email_id)
        return {'text': 'Conteudo recuperado', 'message_id': '<retrieved@example.invalid>'}
    def send_reply(self, **payload):
        if self.fail_send:
            raise RuntimeError('provider details must stay private')
        self.sent.append(payload)
        return f'resend-provider-{len(self.sent) + 1}'

ai = FakeAI()
email = FakeEmail()
core = ConversationService(SessionLocal, ai)
service = AIEmailService(core, email, sender_address='assistente@example.invalid',
                         limiter=lambda identity, limit, window: (True, 0))

def event(email_id, message_id, sender='cliente@example.invalid', text='Ola', subject='Ajuda', **extra):
    data = {'email_id': email_id, 'from': sender, 'to': ['assistente@example.invalid'],
            'subject': subject, 'message_id': message_id, 'text': text,
            'created_at': '2026-09-24T12:00:00Z'}
    data.update(extra)
    return {'type': 'email.received', 'data': data}
"""


class AIEmailTests(unittest.TestCase):
    def run_case(self, source):
        test_bootstrap_database.BootstrapTests.run_case(self, SETUP + textwrap.dedent(source[len(SETUP):]))

    def test_duplicate_delivery_has_one_message_and_one_logical_reply(self):
        self.run_case(SETUP + """
            payload = event('email-1', '<one@example.invalid>')
            first = service.handle(payload, request_id='svix-req-1')
            second = service.handle(payload, request_id='svix-req-1')
            same_rfc_id = service.handle(event('email-1-retry', '<one@example.invalid>'))
            assert first.status == second.status == 'accepted'
            assert second.duplicate is True
            assert same_rfc_id.duplicate is True
            assert ai.calls == 1
            assert len(email.sent) == 1
            with SessionLocal() as db:
                assert db.scalar(select(func.count()).select_from(AIMessageModel).where(
                    AIMessageModel.channel == 'email')) == 2
        """)

    def test_rfc_threading_and_subject_is_not_a_thread_key(self):
        self.run_case(SETUP + """
            first = service.handle(event('email-1', '<one@example.invalid>', subject='Mesmo assunto'))
            with SessionLocal() as db:
                conversation_a = db.scalar(select(AIConversationModel).where(
                    AIConversationModel.channel == 'email')).id
            second = service.handle(event('email-2', '<two@example.invalid>', subject='Mesmo assunto',
                                          in_reply_to='<one@example.invalid>',
                                          references=['<one@example.invalid>']))
            third = service.handle(event('email-3', '<three@example.invalid>', subject='Mesmo assunto'))
            with SessionLocal() as db:
                conversations = db.scalars(select(AIConversationModel).where(
                    AIConversationModel.channel == 'email')).all()
                assert second.conversation_id == conversation_a
                assert third.conversation_id != conversation_a
                assert len(conversations) == 2
                thread = db.get(AIEmailThreadModel, conversation_a)
                assert thread.last_inbound_message_id == 'two@example.invalid'
            assert len(email.sent) == 3
            assert email.sent[1]['headers']['In-Reply-To'] == '<two@example.invalid>'
            assert '<one@example.invalid>' in email.sent[1]['headers']['References']
        """)

    def test_sender_link_does_not_verify_identity_and_unknown_sender_does_not_create_client(self):
        self.run_case(SETUP + """
            with SessionLocal.begin() as db:
                db.add(ClienteModel(id=10, nome='Cliente', email='known@example.invalid'))
            known = service.handle(event('email-1', '<known@example.invalid>', sender='Known <known@example.invalid>'))
            unknown = service.handle(event('email-2', '<unknown@example.invalid>', sender='unknown@example.invalid'))
            with SessionLocal() as db:
                known_conversation = db.get(AIConversationModel, known.conversation_id)
                unknown_conversation = db.get(AIConversationModel, unknown.conversation_id)
                assert known_conversation.cliente_id == 10
                assert unknown_conversation.cliente_id is None
                assert db.scalar(select(func.count()).select_from(ClienteModel)) == 1
        """)

    def test_html_is_text_only_and_attachments_are_not_retrieved(self):
        self.run_case(SETUP + """
            service.handle(event('email-1', '<html@example.invalid>', text='',
                html='<p>Ola</p><script>window.bad=true</script><img src="javascript:bad">',
                attachments=[{'filename': 'arquivo.zip', 'content_type': 'application/zip'}]))
            assert email.retrieved == []
            with SessionLocal() as db:
                row = db.scalar(select(AIMessageModel).where(AIMessageModel.direction == 'inbound'))
                assert row.content == 'Ola'
                assert '<script>' not in row.content
        """)

    def test_self_and_autoresponder_are_ignored(self):
        self.run_case(SETUP + """
            assert service.handle(event('email-1', '<self@example.invalid>',
                sender='assistente@example.invalid')).status == 'ignored'
            assert service.handle(event('email-2', '<auto@example.invalid>',
                headers={'Auto-Submitted': 'auto-replied'})).status == 'ignored'
            assert ai.calls == 0 and email.sent == []
            with SessionLocal() as db:
                assert db.scalar(select(func.count()).select_from(AIConversationModel)) == 0
        """)

    def test_delivery_retry_reuses_existing_ai_reply_and_idempotency_key(self):
        self.run_case(SETUP + """
            email.fail_send = True
            try:
                service.handle(event('email-1', '<retry@example.invalid>'))
            except AIEmailError as error:
                assert str(error) == 'delivery_unavailable'
            else:
                raise AssertionError('delivery failure hidden')
            email.fail_send = False
            service.handle(event('email-1', '<retry@example.invalid>'))
            assert ai.calls == 1
            assert len(email.sent) == 1
            assert email.sent[0]['idempotency_key'].startswith('ai-email/reply/')
        """)

    def test_waiting_human_persists_without_repeated_provider_or_reply(self):
        self.run_case(SETUP + """
            ai.handoff = True
            first = service.handle(event('email-1', '<handoff@example.invalid>'))
            second = service.handle(event('email-2', '<handoff-2@example.invalid>',
                                          in_reply_to='<handoff@example.invalid>'))
            assert first.status == second.status == 'accepted'
            assert ai.calls == 1
            assert email.sent == []
            with SessionLocal() as db:
                conversation = db.get(AIConversationModel, first.conversation_id)
                assert conversation.status == 'waiting_human'
                assert db.scalar(select(func.count()).select_from(AIMessageModel).where(
                    AIMessageModel.direction == 'inbound')) == 2
        """)

    def test_closed_thread_reply_starts_new_conversation(self):
        self.run_case(SETUP + """
            first = service.handle(event('email-1', '<closed@example.invalid>'))
            core.close(first.conversation_id)
            second = service.handle(event('email-2', '<closed-reply@example.invalid>',
                                          in_reply_to='<closed@example.invalid>'))
            assert second.conversation_id != first.conversation_id
            with SessionLocal() as db:
                assert db.scalar(select(func.count()).select_from(AIConversationModel).where(
                    AIConversationModel.channel == 'email')) == 2
        """)

    def test_webhook_signature_valid_invalid_missing_and_modified_body(self):
        self.run_case(SETUP + """
            import asyncio
            import base64
            import hashlib
            import hmac
            import json
            import time
            import httpx
            from main import app
            from routers.webhooks import get_ai_email_service
            from core.config import settings
            secret = b'synthetic-resend-secret'
            settings.RESEND_WEBHOOK_SECRET = 'whsec_' + base64.b64encode(secret).decode()
            app.dependency_overrides[get_ai_email_service] = lambda: service
            payload = event('route-1', '<route@example.invalid>')
            body = json.dumps(payload, separators=(',', ':')).encode()
            svix_id, timestamp = 'svix-route-1', str(int(time.time()))
            signed = f'{svix_id}.{timestamp}.{body.decode()}'.encode()
            signature = base64.b64encode(hmac.new(secret, signed, hashlib.sha256).digest()).decode()
            headers = {'svix-id': svix_id, 'svix-timestamp': timestamp, 'svix-signature': 'v1,' + signature}
            async def check():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post('/webhooks/resend', content=body, headers=headers)
                    assert response.status_code == 200, response.text
                    before = len(email.sent)
                    bad = dict(headers, **{'svix-signature': 'v1,invalid'})
                    assert (await client.post('/webhooks/resend', content=json.dumps(event('route-2', '<route-2@example.invalid>')).encode(), headers=bad)).status_code == 401
                    assert len(email.sent) == before
                    modified = body.replace(b'Ola', b'Tampered')
                    assert (await client.post('/webhooks/resend', content=modified, headers=headers)).status_code == 401
                    assert (await client.post('/webhooks/resend', content=body, headers={'svix-id': svix_id})).status_code == 401
                    settings.RESEND_WEBHOOK_SECRET = ''
                    assert (await client.post('/webhooks/resend', content=body, headers=headers)).status_code == 503
            asyncio.run(check())
            with SessionLocal() as db:
                assert db.scalar(select(func.count()).select_from(AIMessageModel).where(
                    AIMessageModel.direction == 'inbound')) == 1
        """)


if __name__ == '__main__':
    unittest.main()
