"""Opaque site session access and transport projection; decisions stay in the core."""
import hashlib
import re
import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models.ai import AIConversationModel as Conversation
from schemas.ai import ConversationCreate, InboundMessage
from schemas.ai_site import SiteHistory, SiteHistoryMessage, SiteMessage, SiteReply, SiteSession
from services.ai_conversation_service import ConversationError, aware, utcnow
from services.ai_briefing_service import AIBriefingService


def token_reference(token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ConversationError("invalid_session")
    return "site-session:" + hashlib.sha256(token.encode()).hexdigest()


class SiteChannelAdapter:
    def __init__(self, conversation):
        self.conversation = conversation

    def normalize(self, payload, received_at):
        data = SiteMessage.model_validate(payload)
        return InboundMessage(
            channel="site", external_message_id=str(data.message_id), text=data.message,
            external_thread_id=self.conversation.external_thread_id,
            sender_reference=self.conversation.sender_reference, received_at=received_at,
        )

    def send(self, message):
        if message.kind != "reply" or str(message.conversation_id) != self.conversation.id:
            raise ConversationError("invalid_delivery")
        return message.text

    def project(self, result, status):
        text = self.send(result.outbound) if result.outbound and result.action == "reply" else None
        action = "no_action" if result.action == "suggestion" else result.action.value
        return SiteReply(status=status, action=action, text=text, retryable=result.retryable)


class SiteChatService:
    def __init__(self, core, *, session_hours=24, clock=utcnow):
        self.core, self.clock = core, clock
        self.ttl = timedelta(hours=session_hours)

    def create_session(self):
        token = secrets.token_urlsafe(32)
        self.core.create(ConversationCreate(
            channel="site", mode="autonomous", external_thread_id=str(uuid4()),
            sender_reference=token_reference(token),
        ))
        return SiteSession(session_token=token, expires_at=self.clock() + self.ttl)

    def resolve(self, token):
        reference = token_reference(token)
        try:
            with self.core.sessions() as db:
                row = db.scalar(select(Conversation).where(
                    Conversation.channel == "site", Conversation.sender_reference == reference,
                ))
                if row is None or aware(row.created_at) + self.ttl <= self.clock():
                    raise ConversationError("invalid_session")
                db.expunge(row)
                return row
        except SQLAlchemyError:
            raise ConversationError("storage_unavailable") from None

    def history(self, token):
        conversation = self.resolve(token)
        rows = self.core.history(conversation.id, limit=100)
        references = {row.id: row.external_message_id for row in rows if row.direction == "inbound"}
        return SiteHistory(
            status=conversation.status,
            **AIBriefingService(self.core.sessions).public_state(conversation.id),
            awaiting_human=conversation.status == "waiting_human" or conversation.mode == "human",
            messages=[
            SiteHistoryMessage(role=row.role, text=row.content, created_at=aware(row.created_at),
                               message_id=references.get(row.id if row.direction == "inbound" else row.reply_to_id)
                               or (row.id if row.direction == "outbound" else None),
                               sender="client" if row.direction == "inbound" else "human" if row.kind == "message" else "ai")
            for row in rows if row.kind != "suggestion" and row.role in {"user", "assistant"}
            ],
        )

    def message(self, token, payload):
        conversation = self.resolve(token)
        adapter = SiteChannelAdapter(conversation)
        message_id = self.core.receive(conversation.id, adapter.normalize(payload, self.clock()))
        result = self.core.process(conversation.id, message_id, identity_verified=False, source="site")
        reply = adapter.project(result, self.resolve(token).status)
        state = AIBriefingService(self.core.sessions).public_state(conversation.id)
        return reply.model_copy(update=state)
