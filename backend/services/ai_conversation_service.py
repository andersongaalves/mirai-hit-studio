"""Owns short transactions. Callers supply a session factory, never a live Session.

Every mutation locks the conversation first. Provider calls happen after the claim
transaction closes; a token, version and expiry fence off obsolete completions.
"""

from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import logging
import hashlib
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import ClienteModel, UsuarioModel
from models.ai import AIConversationModel as Conversation, AIMessageModel as Message
from schemas.ai import (
    ConversationCreate, ConversationMode, DecisionAction, HandoffReason, HistoryEntry,
    InboundMessage, OutboundMessage, ProcessingResult, ProviderInput, SafeMetadata,
)
from services.ai_orchestrator import AIOrchestrator, Decision, SYSTEM
from services.ai_knowledge_service import AIKnowledgeService, build_tool_registry
from services.ai_tools import ToolExecutionContext


logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def log_reference(value):
    if value is None:
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


class ConversationError(Exception):
    """Only stable codes, never database/provider exception text, cross this boundary."""


@dataclass(frozen=True)
class Claim:
    conversation_id: str
    message_id: str
    token: str
    version: int
    mode: str
    incoming: ProviderInput
    tool_context: ToolExecutionContext


class ConversationService:
    def __init__(
        self,
        sessions,
        provider=None,
        *,
        registry=None,
        knowledge=None,
        clock=utcnow,
        lease_seconds=60,
        max_attempts=3,
    ):
        if not 1 <= lease_seconds <= 300 or not 1 <= max_attempts <= 5:
            raise ValueError("invalid_processing_limits")
        self.sessions = sessions
        self.knowledge = knowledge or AIKnowledgeService(sessions)
        self.orchestrator = AIOrchestrator(provider, registry or build_tool_registry(sessions))
        self.clock = clock
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    @contextmanager
    def _transaction(self):
        try:
            with self.sessions() as db, db.begin():
                yield db
        except SQLAlchemyError:
            raise ConversationError("storage_unavailable") from None

    @staticmethod
    def _lock(db, conversation_id):
        # An UPDATE locks PostgreSQL rows and serializes SQLite test writers too.
        locked = db.execute(update(Conversation).where(Conversation.id == str(conversation_id))
                            .values(version=Conversation.version))
        if not locked.rowcount:
            raise ConversationError("conversation_not_found")
        return db.get(Conversation, str(conversation_id), populate_existing=True)

    def create(self, data: ConversationCreate) -> str:
        data = ConversationCreate.model_validate(data)
        with self._transaction() as db:
            if data.cliente_id is not None and db.get(ClienteModel, data.cliente_id) is None:
                raise ConversationError("cliente_not_found")
            if data.assigned_user_id is not None:
                user = db.get(UsuarioModel, data.assigned_user_id)
                if user is None or not user.ativo:
                    raise ConversationError("assigned_user_invalid")
            anonymous = data.anonymous_session_id or (uuid4() if data.cliente_id is None else None)
            conversation = Conversation(
                id=str(uuid4()), channel=data.channel, mode=data.mode.value,
                cliente_id=data.cliente_id, assigned_user_id=data.assigned_user_id,
                anonymous_session_id=str(anonymous) if anonymous else None,
                external_thread_id=data.external_thread_id, sender_reference=data.sender_reference,
                created_at=self.clock(), updated_at=self.clock(),
            )
            db.add(conversation)
            try:
                db.flush()
            except IntegrityError:
                raise ConversationError("conversation_identity_conflict") from None
            return conversation.id

    def receive(self, conversation_id, incoming: InboundMessage) -> str:
        incoming = InboundMessage.model_validate(incoming)
        with self._transaction() as db:
            conversation = self._lock(db, conversation_id)
            if conversation.status == "closed":
                raise ConversationError("conversation_closed")
            if (conversation.channel != incoming.channel
                    or conversation.external_thread_id != incoming.external_thread_id
                    or conversation.sender_reference != incoming.sender_reference):
                raise ConversationError("conversation_identity_mismatch")
            existing = db.scalar(select(Message).where(
                Message.conversation_id == conversation.id,
                Message.channel == incoming.channel,
                Message.external_message_id == incoming.external_message_id,
            ))
            if existing:
                if existing.content != incoming.text:
                    raise ConversationError("idempotency_conflict")
                return existing.id
            message = Message(
                id=str(uuid4()), conversation_id=conversation.id, direction="inbound", role="user",
                channel=incoming.channel, external_message_id=incoming.external_message_id,
                content=incoming.text, received_at=incoming.received_at, created_at=self.clock(),
                request_id=str(incoming.metadata.request_id) if incoming.metadata.request_id else None,
            )
            db.add(message)
            conversation.updated_at = self.clock()
            db.flush()
            return message.id

    def history(self, conversation_id, *, limit=20):
        if not 1 <= limit <= 100:
            raise ValueError("invalid_history_limit")
        with self._transaction() as db:
            if db.get(Conversation, str(conversation_id)) is None:
                raise ConversationError("conversation_not_found")
            rows = db.scalars(select(Message).where(Message.conversation_id == str(conversation_id))
                              .order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)).all()
            # Detached read objects are for trusted services; never pass them to a provider.
            db.expunge_all()
            return list(reversed(rows))

    def _result(self, db, message):
        reply = db.scalar(select(Message).where(Message.reply_to_id == message.id))
        outbound = None
        if reply:
            outbound = OutboundMessage(
                id=reply.id, conversation_id=message.conversation_id, text=reply.content,
                reply_to=message.external_message_id, kind=reply.kind,
                metadata=SafeMetadata(request_id=message.request_id),
            )
        return ProcessingResult(
            conversation_id=message.conversation_id, message_id=message.id,
            action=message.result_action or "no_action", outbound=outbound,
            reason=message.reason, error_code=message.error_code,
            retryable=message.processing_status == "failed" and message.attempts < self.max_attempts,
        )

    def _prepare_provider_input(
        self,
        db,
        conversation,
        message,
        *,
        context=(),
        identity_verified=False,
        actor="client",
        source=None,
    ):
        prepared = ProviderInput(system=SYSTEM, message="validate", context=context).context
        knowledge = self.knowledge.context_for(message.content, db=db)
        combined_context = ProviderInput(
            system=SYSTEM,
            message="validate",
            context=tuple(prepared) + tuple(knowledge[:max(0, 8 - len(prepared))]),
        ).context
        previous_inputs = select(Message.id).where(
            Message.conversation_id == conversation.id, Message.direction == "inbound",
            or_(Message.created_at < message.created_at,
                (Message.created_at == message.created_at) & (Message.id < message.id)),
        )
        # A reply may complete after the next inbound; include it through its original input.
        previous = db.scalars(select(Message).where(
            Message.conversation_id == conversation.id,
            Message.kind != "suggestion",
            Message.processing_status == "completed",
            or_(Message.id.in_(previous_inputs), Message.reply_to_id.in_(previous_inputs),
                (Message.direction == "outbound") & Message.reply_to_id.is_(None)
                & (Message.created_at < message.created_at)),
        ).order_by(Message.created_at.desc(), Message.id.desc()).limit(20)).all()
        incoming = ProviderInput(
            system=SYSTEM,
            message=message.content,
            context=combined_context,
            history=tuple(HistoryEntry(role=row.role, text=row.content) for row in reversed(previous)),
        )
        tool_context = ToolExecutionContext(
            conversation_id=conversation.id,
            cliente_id=conversation.cliente_id,
            identity_verified=identity_verified,
            mode=conversation.mode,
            actor=actor,
            source=source or conversation.channel,
            request_id=message.request_id,
        )
        return incoming, tool_context

    def claim(
        self,
        conversation_id,
        message_id,
        *,
        context=(),
        identity_verified=False,
        actor="client",
        source=None,
    ) -> Claim | ProcessingResult:
        # Validate externally prepared context before acquiring a lease.
        prepared = ProviderInput(system=SYSTEM, message="validate", context=context).context
        with self._transaction() as db:
            conversation = self._lock(db, conversation_id)
            message = db.get(Message, str(message_id))
            if message is None or message.conversation_id != conversation.id or message.direction != "inbound":
                raise ConversationError("message_not_found")
            if conversation.status == "closed":
                raise ConversationError("conversation_closed")
            if message.processing_status == "completed":
                result = self._result(db, message)
                if result.outbound and (conversation.status != "open" or (
                        result.action == DecisionAction.REPLY and conversation.mode != "autonomous")):
                    return ProcessingResult(conversation_id=conversation.id, message_id=message.id, action="no_action")
                return result
            if conversation.status != "open" or conversation.mode == "human":
                message.processing_status = "completed"
                message.result_action = "no_action"
                message.error_code = None
                return ProcessingResult(conversation_id=conversation.id, message_id=message.id, action="no_action")
            now = self.clock()
            if conversation.claim_token and conversation.lease_until and aware(conversation.lease_until) > now:
                raise ConversationError("processing_conflict")
            first = db.scalar(select(Message.id).where(
                Message.conversation_id == conversation.id, Message.direction == "inbound",
                Message.processing_status != "completed",
            ).order_by(Message.created_at, Message.id).limit(1))
            if first != message.id:
                raise ConversationError("processing_conflict")
            if message.attempts >= self.max_attempts:
                self._handoff(conversation, HandoffReason.PROVIDER_FAILURE)
                message.processing_status = "completed"
                message.result_action = "handoff"
                message.reason = HandoffReason.PROVIDER_FAILURE.value
                message.error_code = "retry_exhausted"
                return self._result(db, message)
            token = str(uuid4())
            conversation.claim_token = token
            conversation.lease_until = now + timedelta(seconds=self.lease_seconds)
            message.processing_status = "processing"
            message.attempts += 1
            message.error_code = None
            incoming, tool_context = self._prepare_provider_input(
                db, conversation, message, context=prepared,
                identity_verified=identity_verified, actor=actor, source=source,
            )
            return Claim(
                conversation.id,
                message.id,
                token,
                conversation.version,
                conversation.mode,
                incoming,
                tool_context,
            )

    def suggest(self, conversation_id, message_id=None, *, context=(), identity_verified=False,
                actor="operator", source="internal"):
        """Generate or replace one copilot draft for the latest inbound message."""
        with self._transaction() as db:
            conversation = self._lock(db, conversation_id)
            if conversation.status == "closed":
                raise ConversationError("conversation_closed")
            if conversation.status != "open" or conversation.mode != ConversationMode.COPILOT.value:
                raise ConversationError("conversation_not_in_copilot")
            if message_id:
                message = db.get(Message, str(message_id))
            else:
                message = db.scalar(select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.direction == "inbound",
                ).order_by(Message.created_at.desc(), Message.id.desc()))
            if message is None or message.conversation_id != conversation.id or message.direction != "inbound":
                raise ConversationError("message_not_found")
            latest = db.scalar(select(Message.id).where(
                Message.conversation_id == conversation.id, Message.direction == "inbound",
            ).order_by(Message.created_at.desc(), Message.id.desc()))
            if message.id != latest:
                raise ConversationError("stale_suggestion")
            existing = db.scalar(select(Message).where(
                Message.reply_to_id == message.id, Message.kind != "suggestion",
            ))
            if existing is not None:
                raise ConversationError("suggestion_unavailable")
            now = self.clock()
            if conversation.claim_token and conversation.lease_until and aware(conversation.lease_until) > now:
                raise ConversationError("processing_conflict")
            token = str(uuid4())
            version = conversation.version
            target_message_id = message.id
            conversation.claim_token = token
            conversation.lease_until = now + timedelta(seconds=self.lease_seconds)
            incoming, tool_context = self._prepare_provider_input(
                db, conversation, message, context=context,
                identity_verified=identity_verified, actor=actor, source=source,
            )
        decision = self.orchestrator.decide(
            status="open", mode=ConversationMode.COPILOT.value,
            incoming=incoming, tool_context=tool_context,
        )
        if decision.action != DecisionAction.SUGGESTION or not decision.text:
            with self._transaction() as db:
                conversation = self._lock(db, conversation_id)
                if conversation.claim_token == token:
                    conversation.claim_token = None
                    conversation.lease_until = None
            raise ConversationError(decision.error_code or "suggestion_unavailable")
        stale = False
        with self._transaction() as db:
            conversation = self._lock(db, conversation_id)
            message = db.get(Message, target_message_id)
            if (conversation.claim_token != token or conversation.version != version
                    or conversation.status != "open" or conversation.mode != ConversationMode.COPILOT.value
                    or conversation.lease_until is None or aware(conversation.lease_until) <= self.clock()
                    or message is None):
                raise ConversationError("processing_conflict")
            latest = db.scalar(select(Message.id).where(
                Message.conversation_id == conversation.id, Message.direction == "inbound",
            ).order_by(Message.created_at.desc(), Message.id.desc()))
            if message.id != latest:
                stale = True
            else:
                draft = db.scalar(select(Message).where(
                    Message.reply_to_id == message.id, Message.kind == "suggestion",
                ))
                if draft is None:
                    draft = Message(
                        id=str(uuid4()), conversation_id=conversation.id, direction="outbound",
                        role="assistant", channel=conversation.channel, reply_to_id=message.id,
                        kind="suggestion", content=decision.text, processing_status="completed",
                        created_at=self.clock(), request_id=message.request_id,
                    )
                    db.add(draft)
                else:
                    draft.content = decision.text
                    draft.created_at = self.clock()
            conversation.claim_token = None
            conversation.lease_until = None
            conversation.updated_at = self.clock()
            if not stale:
                db.flush()
                result = {
                    "id": draft.id,
                    "conversation_id": conversation.id,
                    "target_message_id": message.id,
                    "text": draft.content,
                    "created_at": draft.created_at,
                }
        if stale:
            raise ConversationError("stale_suggestion")
        return result

    def process(
        self,
        conversation_id,
        message_id,
        *,
        context=(),
        identity_verified=False,
        actor="client",
        source=None,
    ):
        claim = self.claim(
            conversation_id,
            message_id,
            context=context,
            identity_verified=identity_verified,
            actor=actor,
            source=source,
        )
        if isinstance(claim, ProcessingResult):
            return claim
        decision = self.orchestrator.decide(
            status="open",
            mode=claim.mode,
            incoming=claim.incoming,
            tool_context=claim.tool_context,
        )
        return self.complete(claim, decision)

    def complete(self, claim: Claim, decision: Decision):
        with self._transaction() as db:
            conversation = self._lock(db, claim.conversation_id)
            message = db.get(Message, claim.message_id)
            if (conversation.claim_token != claim.token or conversation.version != claim.version
                    or conversation.status != "open" or conversation.mode != claim.mode
                    or conversation.lease_until is None or aware(conversation.lease_until) <= self.clock()):
                raise ConversationError("processing_conflict")
            message.result_action = decision.action.value
            message.reason = decision.reason.value if decision.reason else None
            message.error_code = decision.error_code
            message.processing_status = "failed" if decision.action == DecisionAction.ERROR else "completed"
            if decision.action == DecisionAction.ERROR and message.attempts >= self.max_attempts:
                message.processing_status = "completed"
                message.result_action = "handoff"
                message.reason = HandoffReason.PROVIDER_FAILURE.value
                message.error_code = "retry_exhausted"
                self._handoff(conversation, HandoffReason.PROVIDER_FAILURE)
            elif decision.action == DecisionAction.HANDOFF:
                self._handoff(conversation, decision.reason)
            elif decision.action in (DecisionAction.REPLY, DecisionAction.SUGGESTION):
                db.add(Message(
                    id=str(uuid4()), conversation_id=conversation.id, direction="outbound",
                    role="assistant", channel=conversation.channel, reply_to_id=message.id,
                    kind=decision.action.value, content=decision.text, processing_status="completed",
                    created_at=self.clock(), request_id=message.request_id,
                ))
            conversation.claim_token = None
            conversation.lease_until = None
            conversation.updated_at = self.clock()
            db.flush()
            result = self._result(db, message)
            request_id = message.request_id
        logger.info("ai_processed conversation_id=%s message_id=%s action=%s error_code=%s request_id=%s",
                    claim.conversation_id, claim.message_id, result.action.value,
                    result.error_code, log_reference(request_id))
        return result

    def _handoff(self, conversation, reason):
        if conversation.status == "waiting_human":
            return
        conversation.status = "waiting_human"
        conversation.mode = "human"
        conversation.handoff_reason = HandoffReason(reason).value
        conversation.version += 1
        conversation.claim_token = None
        conversation.lease_until = None
        conversation.updated_at = self.clock()

    def handoff(self, conversation_id, reason: HandoffReason):
        reason = HandoffReason(reason)
        with self._transaction() as db:
            conversation = self._lock(db, conversation_id)
            if conversation.status == "closed":
                raise ConversationError("conversation_closed")
            self._handoff(conversation, reason)
            return HandoffReason(conversation.handoff_reason)

    def set_mode(self, conversation_id, mode: ConversationMode):
        mode = ConversationMode(mode)
        with self._transaction() as db:
            conversation = self._lock(db, conversation_id)
            if conversation.status != "open":
                raise ConversationError("conversation_not_open")
            if conversation.mode != mode.value:
                conversation.mode = mode.value
                conversation.version += 1
                conversation.claim_token = None
                conversation.lease_until = None
                conversation.updated_at = self.clock()

    def close(self, conversation_id):
        with self._transaction() as db:
            conversation = self._lock(db, conversation_id)
            if conversation.status != "closed":
                conversation.status = "closed"
                conversation.closed_at = self.clock()
                conversation.updated_at = self.clock()
                conversation.version += 1
                conversation.claim_token = None
                conversation.lease_until = None
