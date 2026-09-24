"""Resend inbound orchestration for the channel-neutral AI conversation core."""

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
import re
from types import SimpleNamespace

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from core.rate_limit import allow_request
from models import ClienteModel
from models.ai import AIConversationModel as Conversation, AIEmailThreadModel as EmailThread, AIMessageModel as Message
from schemas.ai import ConversationCreate, DecisionAction
from services.ai_conversation_service import ConversationError, ConversationService, utcnow
from services.ai_email_channel import (
    EmailChannelAdapter, ReceivedEmail, auto_reply, looks_automated, normalize_sender,
    thread_key,
)


class AIEmailError(Exception):
    """Stable public error codes; provider and message content never cross this boundary."""


@dataclass(frozen=True)
class EmailOutcome:
    status: str
    duplicate: bool = False
    conversation_id: str | None = None


def _as_datetime(value, fallback):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return fallback


class AIEmailService:
    def __init__(
        self,
        core: ConversationService,
        client,
        *,
        sender_address,
        max_body_chars=8000,
        clock=utcnow,
        limiter=allow_request,
    ):
        sender_address = normalize_sender(sender_address)
        if not sender_address:
            raise AIEmailError("email_not_configured")
        self.core = core
        self.client = client
        self.sender_address = sender_address
        self.clock = clock
        self.limiter = limiter
        self.adapter = EmailChannelAdapter(max_body_chars=max_body_chars)

    @staticmethod
    def _request_id(value):
        value = str(value or "")
        return value if 8 <= len(value) <= 64 and all(char.isalnum() or char in "._-" for char in value) else None

    @staticmethod
    def _event_data(payload):
        if not isinstance(payload, dict) or payload.get("type") != "email.received":
            return None
        data = payload.get("data")
        return data if isinstance(data, dict) else None

    def _received_email(self, data):
        provider_email_id = data.get("email_id")
        if not isinstance(provider_email_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", provider_email_id):
            raise AIEmailError("invalid_payload")
        retrieved = {}
        text = data.get("text")
        html = data.get("html")
        if not (isinstance(text, str) and text.strip()) and not (isinstance(html, str) and html.strip()):
            retrieved = self.client.retrieve_received(provider_email_id)
        received_at = _as_datetime(data.get("created_at"), self.clock())
        try:
            return self.adapter.received(
                data,
                received_at,
                provider_email_id=provider_email_id,
                retrieved=retrieved,
            )
        except ValueError as error:
            raise AIEmailError(str(error)) from None

    def _is_ignored(self, email: ReceivedEmail):
        return email.sender_email == self.sender_address or looks_automated(email.sender_email) or auto_reply(email.headers)

    def _find_duplicate(self, email: ReceivedEmail):
        with self.core.sessions() as db:
            row = db.scalar(select(Message).where(
                Message.channel == "email", Message.external_message_id == email.external_message_id,
            ))
            if row is not None:
                return row.conversation_id, row.id
            thread = db.scalar(select(EmailThread).where(or_(
                EmailThread.root_message_id == email.message_id,
                EmailThread.last_inbound_message_id == email.message_id,
            )))
            if thread is None:
                return None
            row = db.scalar(select(Message).where(
                Message.conversation_id == thread.conversation_id,
                Message.channel == "email", Message.direction == "inbound",
            ).order_by(Message.created_at.desc(), Message.id.desc()))
            return (thread.conversation_id, row.id) if row is not None else None

    def _find_thread(self, email: ReceivedEmail):
        references = tuple(dict.fromkeys((email.in_reply_to,) + email.references))
        references = tuple(item for item in references if item)
        if not references:
            return None
        with self.core.sessions() as db:
            row = db.scalar(select(EmailThread).where(
                or_(EmailThread.root_message_id.in_(references),
                    EmailThread.last_inbound_message_id.in_(references))
            ))
            if row is None or row.sender_email != email.sender_email:
                return None
            conversation = db.get(Conversation, row.conversation_id)
            if conversation is None or conversation.status == "closed":
                return None
            db.expunge(row)
            return row

    def _client_id(self, sender_email):
        with self.core.sessions() as db:
            rows = db.scalars(select(ClienteModel.id).where(
                func.lower(ClienteModel.email) == sender_email,
            )).all()
            return rows[0] if len(rows) == 1 else None

    def _create_thread(self, email: ReceivedEmail):
        root_message_id = email.root_message_id
        key = thread_key(root_message_id)
        with self.core.sessions() as db:
            existing = db.scalar(select(Conversation).where(
                Conversation.channel == "email", Conversation.external_thread_id == key,
            ))
            if existing is not None and existing.status == "closed":
                # A closed conversation is never reopened by an inbound reply.
                root_message_id = email.message_id
                key = thread_key(root_message_id)
        try:
            conversation_id = self.core.create(ConversationCreate(
                channel="email", mode="autonomous", external_thread_id=key,
                sender_reference=email.sender_email, cliente_id=self._client_id(email.sender_email),
            ))
        except ConversationError as error:
            if str(error) != "conversation_identity_conflict":
                raise
            with self.core.sessions() as db:
                conversation_id = db.scalar(select(Conversation.id).where(
                    Conversation.channel == "email", Conversation.external_thread_id == key,
                ))
            if not conversation_id:
                raise AIEmailError("storage_unavailable") from None
        with self.core.sessions() as db, db.begin():
            row = db.get(EmailThread, conversation_id)
            if row is None:
                db.add(EmailThread(
                    conversation_id=conversation_id, sender_email=email.sender_email,
                    subject=email.subject, root_message_id=root_message_id,
                    last_inbound_message_id=None, created_at=self.clock(), updated_at=self.clock(),
                ))
        return self._thread_for_conversation(conversation_id)

    def _thread_for_conversation(self, conversation_id):
        with self.core.sessions() as db:
            row = db.get(EmailThread, str(conversation_id))
            if row is None:
                raise AIEmailError("storage_unavailable")
            db.expunge(row)
            return row

    def _update_thread(self, conversation_id, email: ReceivedEmail):
        with self.core.sessions() as db, db.begin():
            row = db.get(EmailThread, str(conversation_id))
            if row is None or row.sender_email != email.sender_email:
                raise AIEmailError("conversation_identity_mismatch")
            row.last_inbound_message_id = email.message_id
            row.updated_at = self.clock()

    def _send(self, outbound, thread):
        with self.core.sessions() as db:
            existing = db.get(Message, str(outbound.id))
            if existing is None:
                raise AIEmailError("storage_unavailable")
            if existing.external_message_id:
                return existing.external_message_id
        payload = self.adapter.outbound(outbound, thread, sender=self.sender_address)
        try:
            provider_id = self.client.send_reply(**payload)
        except Exception:
            raise AIEmailError("delivery_unavailable") from None
        with self.core.sessions() as db, db.begin():
            existing = db.get(Message, str(outbound.id))
            if existing is None:
                raise AIEmailError("storage_unavailable")
            if existing.external_message_id:
                return existing.external_message_id
            existing.external_message_id = str(provider_id)[:200]
        return str(provider_id)[:200]

    def send_human_message(self, conversation_id, message_id):
        """Deliver a persisted Inbox message using the existing email thread."""
        with self.core.sessions() as db:
            row = db.get(Message, str(message_id))
            thread = db.get(EmailThread, str(conversation_id))
            if (row is None or thread is None or row.conversation_id != str(conversation_id)
                    or row.channel != "email" or row.direction != "outbound" or row.kind != "message"):
                raise AIEmailError("message_not_found")
            if row.external_message_id:
                return row.external_message_id
            outbound = SimpleNamespace(id=row.id, text=row.content)
            db.expunge(thread)
        return self._send(outbound, thread)

    def handle(self, payload, *, request_id=None):
        data = self._event_data(payload)
        if data is None:
            if isinstance(payload, dict) and payload.get("type") != "email.received":
                return EmailOutcome("ignored")
            raise AIEmailError("invalid_payload")
        email = self._received_email(data)
        if self._is_ignored(email):
            return EmailOutcome("ignored")
        duplicate = self._find_duplicate(email)
        if duplicate:
            conversation_id, message_id = duplicate
            thread = self._thread_for_conversation(conversation_id)
            result = self.core.process(conversation_id, message_id, identity_verified=False, source="email")
            if result.action == DecisionAction.REPLY and result.outbound:
                self._send(result.outbound, thread)
            return EmailOutcome("accepted", True, conversation_id)
        root_key = thread_key(email.root_message_id)
        try:
            allowed, _ = self.limiter("ai-email-thread:" + root_key, 5, 600)
            if not allowed:
                return EmailOutcome("ignored")
            allowed, _ = self.limiter("ai-email-sender:" + email.sender_email, 20, 3600)
            if not allowed:
                return EmailOutcome("ignored")
        except (OSError, sqlite3.Error, SQLAlchemyError):
            raise AIEmailError("rate_limit_unavailable") from None
        thread = self._find_thread(email) or self._create_thread(email)
        conversation_id = thread.conversation_id
        incoming = self.adapter.normalize(
            email, thread_key_value=self._conversation_thread_key(conversation_id),
            sender_reference=email.sender_email, request_id=self._request_id(request_id),
        )
        try:
            message_id = self.core.receive(conversation_id, incoming)
            self._update_thread(conversation_id, email)
            result = self.core.process(conversation_id, message_id, identity_verified=False, source="email")
        except ConversationError as error:
            raise AIEmailError(str(error)) from None
        if result.action == DecisionAction.REPLY and result.outbound:
            self._send(result.outbound, self._thread_for_conversation(conversation_id))
        elif result.action == DecisionAction.ERROR and result.retryable:
            raise AIEmailError("processing_retryable")
        return EmailOutcome("accepted", False, conversation_id)

    def _conversation_thread_key(self, conversation_id):
        with self.core.sessions() as db:
            value = db.scalar(select(Conversation.external_thread_id).where(Conversation.id == str(conversation_id)))
            if not value:
                raise AIEmailError("storage_unavailable")
            return value
