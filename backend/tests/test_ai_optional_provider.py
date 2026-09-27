"""Optional-provider behavior with disposable SQLite and no external calls."""

import textwrap
import unittest

import test_bootstrap_database


SETUP = """
from uuid import uuid4
from database import SessionLocal
from models import ProjetoModel, ServicoModel
from models.ai_usage import AIUsageEventModel
from schemas.ai_site import SiteMessage
from services.ai_conversation_service import ConversationError, ConversationService
from services.ai_site_service import SiteChannelAdapter, SiteChatService
from sqlalchemy import func, select
bootstrap(engine)

class DisabledSpy:
    available = False
    calls = 0
    def generate(self, incoming):
        self.calls += 1
        raise AssertionError('disabled provider called')

provider = DisabledSpy()
core = ConversationService(SessionLocal, provider)
site = SiteChatService(core)

def send(token, text):
    return site.message(token, SiteMessage(message_id=uuid4(), message=text))
"""


class OptionalProviderTests(unittest.TestCase):
    def run_case(self, source):
        test_bootstrap_database.BootstrapTests.run_case(
            self,
            SETUP + textwrap.dedent(source[len(SETUP):]),
        )

    def test_session_and_deterministic_public_capabilities_need_no_provider(self):
        self.run_case(SETUP + """
            with SessionLocal.begin() as db:
                db.add(ServicoModel(id=1, nome='Mixagem', subtitulo='Equilibrio e acabamento',
                    valor_base=300, categoria='audio'))
                db.add(ProjetoModel(id=1, titulo='Aurora', artista='Mirai', categoria='Trilha',
                    link_audio='https://example.invalid/audio.mp3',
                    link_capa='https://example.invalid/cover.webp', vertical='media_games',
                    segmentos_json=['games'], case_type='demo'))
            faq = send(site.create_session().session_token, 'Qual o prazo de entrega?')
            services = send(site.create_session().session_token, 'Quais servicos voces oferecem?')
            portfolio = send(site.create_session().session_token, 'Quero conhecer o portfolio')
            assert faq.action == services.action == portfolio.action == 'reply'
            assert 'proposta comercial' in faq.text
            assert 'Mixagem' in services.text and 'referências de base' in services.text
            assert 'Aurora' in portfolio.text and 'demo' in portfolio.text
            assert provider.calls == 0
            with SessionLocal() as db:
                assert db.scalar(select(func.count()).select_from(AIUsageEventModel).where(
                    AIUsageEventModel.kind == 'provider')) == 0
                assert db.scalar(select(func.count()).select_from(AIUsageEventModel).where(
                    AIUsageEventModel.kind == 'turn',
                    AIUsageEventModel.result == 'deterministic_reply')) == 3
        """)

    def test_unknown_message_falls_back_to_human_without_hallucination(self):
        self.run_case(SETUP + """
            token = site.create_session().session_token
            conversation = site.resolve(token)
            from models.ai_briefing import AIBriefingModel
            with SessionLocal.begin() as db:
                db.add(AIBriefingModel(
                    conversation_id=conversation.id, interest='Trilha original', data_json={},
                ))
            result = send(token, 'Explique uma ideia totalmente aberta para minha campanha')
            assert result.action == 'handoff' and result.text is None
            assert result.status == 'waiting_human' and provider.calls == 0
            history = site.history(token)
            assert history.awaiting_human and len(history.messages) == 1
            with SessionLocal() as db:
                turns = db.scalars(select(AIUsageEventModel).where(
                    AIUsageEventModel.kind == 'turn')).all()
                assert any(item.result == 'handoff' and item.error_code == 'provider_disabled' for item in turns)
                assert any(item.result == 'provider_disabled' and item.error_code == 'provider_disabled' for item in turns)
                assert db.scalar(select(func.count()).select_from(AIUsageEventModel).where(
                    AIUsageEventModel.kind == 'provider')) == 0
                briefing = db.get(AIBriefingModel, conversation.id)
                assert briefing.status == 'draft' and briefing.interest == 'Trilha original'
        """)

    def test_explicit_handoff_and_copilot_disabled_are_controlled(self):
        self.run_case(SETUP + """
            token = site.create_session().session_token
            assert send(token, 'Quero falar com uma pessoa').status == 'waiting_human'
            assert provider.calls == 0
            copilot_token = site.create_session().session_token
            conversation = site.resolve(copilot_token)
            core.set_mode(conversation.id, 'copilot')
            message_id = core.receive(conversation.id, SiteChannelAdapter(conversation).normalize(
                SiteMessage(message_id=uuid4(), message='Crie uma resposta livre'), site.clock()))
            try:
                core.suggest(conversation.id, message_id)
            except ConversationError as error:
                assert str(error) == 'provider_disabled'
            else:
                raise AssertionError('copilot generated without provider')
            from types import SimpleNamespace
            from models.usuario import UsuarioModel
            from schemas.ai_inbox import InboxMessageCreate
            from services.ai_inbox_service import AIInboxService
            with SessionLocal.begin() as db:
                db.add(UsuarioModel(id=1, username='operator', password_hash='hash',
                    is_admin=True, ativo=True, role='admin'))
            actor = SimpleNamespace(id=1, role='admin', ativo=True, is_admin=True)
            inbox = AIInboxService(SessionLocal, core)
            inbox.assign(conversation.id, actor)
            sent = inbox.send_message(conversation.id, InboxMessageCreate(
                text='Resposta humana segura', idempotency_key='manual-reply-001'), actor)
            assert sent['delivery'] == 'sent'
            assert provider.calls == 0
        """)

    def test_http_session_succeeds_with_ai_enabled_and_provider_disabled(self):
        self.run_case(SETUP + """
            import asyncio
            import httpx
            import os
            from core.config import settings
            settings.AI_ENABLED = True
            settings.AI_PROVIDER = 'disabled'
            settings.AI_MODEL = ''
            settings.AI_API_KEY = ''
            settings.AI_SESSION_HOURS = 24
            settings.AI_TIMEOUT_SECONDS = 8
            os.environ['RATE_LIMIT_DB'] = config.settings.BACKUP_FOLDER + '/optional-rates.sqlite'
            from main import app
            async def check():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post('/ai/chat/session')
                    assert response.status_code == 201, response.text
                    assert response.json()['session_token']
            asyncio.run(check())
        """)

    def test_provider_configuration_is_backward_compatible(self):
        self.run_case(SETUP + """
            from types import SimpleNamespace
            from services.ai_openai_provider import OpenAIProvider
            from services.ai_provider import DisabledProvider
            from services.ai_provider_factory import build_ai_provider, provider_mode
            base = dict(AI_ENABLED=True, AI_TIMEOUT_SECONDS=8, AI_MAX_OUTPUT_TOKENS=1200)
            disabled = SimpleNamespace(**base, AI_PROVIDER='disabled', AI_MODEL='model', AI_API_KEY='secret')
            inferred = SimpleNamespace(**base, AI_PROVIDER='', AI_MODEL='model', AI_API_KEY='secret')
            empty = SimpleNamespace(**base, AI_PROVIDER='', AI_MODEL='', AI_API_KEY='')
            assert provider_mode(disabled) == 'disabled'
            assert isinstance(build_ai_provider(disabled), DisabledProvider)
            assert provider_mode(inferred) == 'openai'
            assert isinstance(build_ai_provider(inferred), OpenAIProvider)
            assert provider_mode(empty) == 'disabled'
        """)

    def test_email_uses_local_reply_or_safe_handoff_without_provider(self):
        self.run_case(SETUP + """
            from services.ai_email_service import AIEmailService
            class EmailTransport:
                sent = []
                def send_reply(self, **payload):
                    self.sent.append(payload)
                    return 'synthetic-email-id'
            transport = EmailTransport()
            email = AIEmailService(core, transport, sender_address='assistente@example.invalid',
                limiter=lambda identity, limit, window: (True, 0))
            def event(key, text):
                return {'type':'email.received', 'data': {
                    'email_id':key, 'from':'cliente@example.invalid',
                    'to':['assistente@example.invalid'], 'subject':'Ajuda',
                    'message_id':f'<{key}@example.invalid>', 'text':text,
                    'created_at':'2026-09-27T12:00:00Z'}}
            assert email.handle(event('faq', 'Quais formas de pagamento?')).status == 'accepted'
            assert len(transport.sent) == 1 and 'proposta' in transport.sent[0]['text']
            unknown = email.handle(event('unknown', 'Crie uma campanha totalmente nova'))
            assert unknown.status == 'accepted' and len(transport.sent) == 1
            assert provider.calls == 0
        """)


if __name__ == '__main__':
    unittest.main()
