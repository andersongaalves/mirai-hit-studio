"""Opt-in browser/backend/PostgreSQL journey for I.3 using synthetic transports."""

from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import delete, inspect, select, text
from sqlalchemy.engine import make_url

from commercial_i2_support import local_frontend_server, local_server


POSTGRES_URL = os.getenv("MIRAI_I3_DATABASE_URL", "")
ACK = os.getenv("MIRAI_I3_ALLOW_ACTIVE_DATABASE", "")


@unittest.skipUnless(bool(POSTGRES_URL) and ACK == "I3_SYNTHETIC_FIXTURES_ONLY", "I.3 PostgreSQL opt-in required")
class AIPostgresI3Tests(unittest.TestCase):
    @classmethod
    def _users_digest(cls, exclude_username=None):
        query = "select id, username, password_hash, is_admin, ativo, role, created_at, updated_at from usuarios"
        params = {}
        if exclude_username:
            query += " where username <> :username"
            params["username"] = exclude_username
        query += " order by id"
        with cls.engine.connect() as connection:
            rows = connection.execute(text(query), params).all()
        digest = hashlib.sha256()
        for row in rows:
            digest.update(repr(tuple(row)).encode())
        return f"{len(rows)}:{digest.hexdigest()}"

    @classmethod
    def setUpClass(cls):
        if not make_url(POSTGRES_URL).drivername.startswith("postgresql"):
            raise RuntimeError("I.3 requires PostgreSQL")
        from core.config import settings
        from core.security import get_password_hash
        from database import SessionLocal, engine
        from main import app
        from models import UsuarioModel
        from routers.ai_chat import get_site_chat_service
        from routers.ai_inbox import get_ai_core, get_ai_email_delivery
        from schemas.ai import ConversationCreate, ProviderResponse
        from schemas.ai_site import SiteSession
        from services.ai_conversation_service import ConversationService
        from services.ai_site_service import SiteChatService, token_reference

        configured, actual = make_url(POSTGRES_URL), make_url(str(engine.url))
        def target(url):
            return url.drivername, url.host, url.port, url.database
        if target(configured) != target(actual):
            raise RuntimeError("I.3 app database differs from authorized target")
        with engine.connect() as connection:
            if connection.execute(text("select version_num from alembic_version")).scalar_one() != "93c2cf108202":
                raise RuntimeError("I.3 database is not at expected head")
            required = {"ai_conversations", "ai_messages", "ai_email_threads", "ai_briefings", "ai_usage_events"}
            if not required <= set(inspect(connection).get_table_names()):
                raise RuntimeError("I.3 AI schema is incomplete")

        class FakeGroq:
            available = True
            provider_name = "groq"
            model = "openai/gpt-oss-20b"

            def __init__(self):
                self.calls = []

            def generate(self, incoming):
                self.calls.append(incoming)
                return ProviderResponse(text="I3_TEST resposta generativa sintetica")

        class FixtureSiteService(SiteChatService):
            def create_session(self):
                token = secrets.token_urlsafe(32)
                self.core.create(ConversationCreate(
                    channel="site", mode="autonomous",
                    external_thread_id=f"{cls.prefix}_{uuid4().hex}",
                    sender_reference=token_reference(token),
                ))
                return SiteSession(session_token=token, expires_at=self.clock() + self.ttl)

        cls.engine, cls.SessionLocal, cls.app = engine, SessionLocal, app
        cls.token = uuid4().hex
        cls.prefix = f"i3_{cls.token}"
        cls.username = f"i3op{cls.token[:20]}"
        cls.password = "I3-only-password!"
        cls.users_before = cls._users_digest(exclude_username=cls.username)
        with SessionLocal.begin() as db:
            db.add(UsuarioModel(username=cls.username, password_hash=get_password_hash(cls.password),
                                is_admin=True, role="admin", ativo=True))
        cls.provider = FakeGroq()
        cls.core = ConversationService(SessionLocal, cls.provider)
        cls.site = FixtureSiteService(cls.core)
        cls.site.ai_enabled = True
        app.dependency_overrides[get_site_chat_service] = lambda: cls.site
        app.dependency_overrides[get_ai_core] = lambda: cls.core
        app.dependency_overrides[get_ai_email_delivery] = lambda: None
        settings.AI_ENABLED = True
        cls.temp = tempfile.TemporaryDirectory(prefix="mirai-i3-connected-")
        os.environ["RATE_LIMIT_DB"] = str(Path(cls.temp.name) / "rate.sqlite3")
        cls.stack = ExitStack()
        cls.stack.enter_context(patch("routers.ai_chat.allow_request", return_value=(True, 0)))
        cls.stack.enter_context(patch("routers.ai_inbox.allow_request", return_value=(True, 0)))
        cls.server = cls.stack.enter_context(local_server(app, port=8000))
        root = Path(__file__).resolve().parents[2]
        cls.frontend = cls.stack.enter_context(local_frontend_server(root / "frontend", port=5500))

    @classmethod
    def _conversation_ids(cls):
        from models import AIConversationModel, AIEmailThreadModel
        with cls.SessionLocal() as db:
            site = list(db.scalars(select(AIConversationModel.id).where(
                AIConversationModel.external_thread_id.like(f"{cls.prefix}%"))))
            email = list(db.scalars(select(AIEmailThreadModel.conversation_id).where(
                AIEmailThreadModel.root_message_id.like(f"%{cls.prefix}%"))))
        return list(set(site + email))

    @classmethod
    def _cleanup(cls):
        from models import (AIBriefingModel, AIConversationModel, AIEmailThreadModel,
                            AIMessageModel, AIUsageEventModel, AuditLogModel, ClienteModel,
                            OrcamentoModel, UsuarioModel)
        ids = cls._conversation_ids()
        with cls.SessionLocal.begin() as db:
            if ids:
                db.execute(delete(AuditLogModel).where(
                    AuditLogModel.entity_type == "ai_conversation",
                    AuditLogModel.entity_id.in_([str(item) for item in ids]),
                ))
                for model in (AIUsageEventModel, AIBriefingModel, AIEmailThreadModel, AIMessageModel):
                    db.execute(delete(model).where(model.conversation_id.in_(ids)))
                db.execute(delete(AIConversationModel).where(AIConversationModel.id.in_(ids)))
            db.execute(delete(OrcamentoModel).where(OrcamentoModel.email.like(f"{cls.prefix}%")))
            db.execute(delete(ClienteModel).where(ClienteModel.email.like(f"{cls.prefix}%")))
            user_id = select(UsuarioModel.id).where(UsuarioModel.username == cls.username).scalar_subquery()
            db.execute(delete(AuditLogModel).where(AuditLogModel.actor_user_id == user_id))
            db.execute(delete(UsuarioModel).where(UsuarioModel.username == cls.username))

    @classmethod
    def tearDownClass(cls):
        try:
            cls._cleanup()
            if cls._conversation_ids():
                raise AssertionError("I.3 conversation cleanup incomplete")
            if cls._users_digest() != cls.users_before:
                raise AssertionError("I.3 changed protected users")
        finally:
            cls.app.dependency_overrides.clear()
            cls.stack.close()
            cls.temp.cleanup()
            cls.engine.dispose()

    def test_real_browser_chat_inbox_copilot_and_human_reply(self):
        root = Path(__file__).resolve().parents[2]
        calls_before = len(self.provider.calls)
        env = {**os.environ,
               "NODE_PATH": r"C:\Users\SadBox\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules",
               "I3_PREFIX": self.prefix, "I3_USERNAME": self.username, "I3_PASSWORD": self.password}
        try:
            result = subprocess.run([r"D:\node.exe", str(root / "frontend/tests/ai_postgres_i3.cjs")],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=150)
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or b"") + (error.stderr or b"")
            raise AssertionError(output.decode(errors="replace") if isinstance(output, bytes) else output) from error
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        payload = json.loads(next(line for line in result.stdout.splitlines()
                                  if line.startswith("I3_RESULT ")).removeprefix("I3_RESULT "))
        self.assertTrue(payload["chat"] and payload["inbox"] and payload["copilot"])
        current_calls = self.provider.calls[calls_before:]
        self.assertEqual(len(current_calls), 3, [item.message for item in current_calls])

    def test_connected_email_threading_duplicate_and_provider(self):
        from services.ai_email_service import AIEmailService

        class Transport:
            def __init__(self):
                self.sent = []

            def retrieve_received(self, _email_id):
                raise AssertionError("unexpected retrieval")

            def send_reply(self, **payload):
                self.sent.append(payload)
                return f"{self_prefix}_sent_{len(self.sent)}"

        self_prefix = self.prefix
        transport = Transport()
        service = AIEmailService(self.core, transport, sender_address="assistente@example.invalid",
                                 limiter=lambda _identity, _limit, _window: (True, 0))
        root_id = f"<{self.prefix}@example.invalid>"
        base = {"from": f"{self.prefix}@example.invalid", "to": ["assistente@example.invalid"],
                "subject": "I3_TEST", "created_at": datetime.now(timezone.utc).isoformat()}
        first = {"type": "email.received", "data": {**base, "email_id": f"{self.prefix}_email_1",
                 "message_id": root_id, "text": "Pergunta flexivel sintetica sobre identidade sonora"}}
        initial = service.handle(first, request_id=f"{self.prefix}_request_1")
        duplicate = service.handle(first, request_id=f"{self.prefix}_request_1")
        second = {"type": "email.received", "data": {**base, "email_id": f"{self.prefix}_email_2",
                  "message_id": f"<{self.prefix}-2@example.invalid>", "in_reply_to": root_id,
                  "references": root_id, "text": "Outra pergunta flexivel sintetica"}}
        followup = service.handle(second, request_id=f"{self.prefix}_request_2")
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(initial.conversation_id, followup.conversation_id)
        self.assertEqual(len(transport.sent), 2)
        self.assertTrue(all(item["idempotency_key"].startswith("ai-email/reply/") for item in transport.sent))


if __name__ == "__main__":
    unittest.main()
