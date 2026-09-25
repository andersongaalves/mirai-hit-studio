"""Authenticated operational workflows for the unified AI Inbox."""

from datetime import datetime, timezone
from math import ceil
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload

from models.ai import AIConversationModel as Conversation, AIEmailThreadModel as EmailThread, AIMessageModel as Message
from models.cliente import ClienteModel
from schemas.ai import ConversationMode, ConversationStatus
from services.ai_conversation_service import ConversationError, ConversationService
from services.ai_briefing_service import AIBriefingService
from services.ai_email_service import AIEmailError
from services.audit_service import record as audit_record


def utcnow():
    return datetime.now(timezone.utc)


class InboxError(Exception):
    """Stable errors exposed by the admin Inbox."""


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class AIInboxService:
    def __init__(self, sessions, core: ConversationService, email_delivery=None, *, clock=utcnow):
        self.sessions = sessions
        self.core = core
        self.email_delivery = email_delivery
        self.clock = clock

    @staticmethod
    def _operator_can_act(conversation, actor):
        return conversation.assigned_user_id == actor.id

    @staticmethod
    def _message_payload(row):
        delivery = "draft" if row.kind == "suggestion" else (
            "pending" if row.channel == "email" and row.direction == "outbound" and not row.external_message_id
            else "sent"
        )
        return {
            "id": row.id,
            "direction": row.direction,
            "role": row.role,
            "kind": row.kind,
            "content": row.content,
            "created_at": row.created_at,
            "received_at": row.received_at,
            "delivery": delivery,
        }

    @classmethod
    def _detail_payload(cls, conversation, messages, thread=None, has_more=False):
        cliente = conversation.cliente
        messages = sorted(messages, key=lambda item: (item.created_at, item.id))
        return {
            "id": conversation.id,
            "channel": conversation.channel,
            "status": conversation.status,
            "mode": conversation.mode,
            "assigned_user_id": conversation.assigned_user_id,
            "assigned_username": conversation.assigned_user.username if conversation.assigned_user else None,
            "cliente_id": conversation.cliente_id,
            "cliente_nome": cliente.nome if cliente else None,
            "cliente_email": cliente.email if cliente else None,
            "sender_reference": conversation.sender_reference if conversation.channel == "email" else None,
            "email_subject": thread.subject if thread else None,
            "handoff_reason": conversation.handoff_reason,
            "version": conversation.version,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "closed_at": conversation.closed_at,
            "messages": [cls._message_payload(row) for row in messages],
            "has_more_messages": has_more,
            "next_before": messages[0].id if has_more and messages else None,
        }

    def detail(self, conversation_id, *, before=None, limit=100):
        with self.sessions() as db:
            conversation = db.scalar(select(Conversation).options(
                joinedload(Conversation.cliente),
                joinedload(Conversation.assigned_user),
            ).where(Conversation.id == str(conversation_id)))
            if conversation is None:
                raise InboxError("conversation_not_found")
            query = select(Message).where(Message.conversation_id == conversation.id)
            if before:
                cursor = db.get(Message, str(before))
                if cursor is None or cursor.conversation_id != conversation.id:
                    raise InboxError("message_not_found")
                query = query.where(or_(
                    Message.created_at < cursor.created_at,
                    (Message.created_at == cursor.created_at) & (Message.id < cursor.id),
                ))
            rows = db.scalars(query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)).all()
            has_more = len(rows) > limit
            thread = db.get(EmailThread, conversation.id) if conversation.channel == "email" else None
            detail = self._detail_payload(conversation, rows[:limit], thread, has_more)
            detail["briefing"] = AIBriefingService(self.sessions).admin_view(conversation.id)
            return detail

    def list(self, *, page=1, page_size=20, status=None, mode=None, channel=None,
             handoff=False, assigned_user_id=None, unassigned=False, search=None,
             updated_from=None, updated_to=None):
        page = max(1, int(page))
        page_size = min(50, max(1, int(page_size)))
        query = select(Conversation).options(
            joinedload(Conversation.cliente),
            joinedload(Conversation.assigned_user),
        )
        filters = []
        if status:
            filters.append(Conversation.status == status.value)
        if mode:
            filters.append(Conversation.mode == mode.value)
        if channel:
            filters.append(Conversation.channel == channel)
        if handoff:
            filters.append(Conversation.status == ConversationStatus.WAITING_HUMAN.value)
        if assigned_user_id is not None:
            filters.append(Conversation.assigned_user_id == assigned_user_id)
        if unassigned:
            filters.append(Conversation.assigned_user_id.is_(None))
        if updated_from:
            filters.append(Conversation.updated_at >= updated_from)
        if updated_to:
            filters.append(Conversation.updated_at <= updated_to)
        if search:
            term = f"%{search.strip()[:80]}%"
            subject_ids = select(EmailThread.conversation_id).where(EmailThread.subject.ilike(term))
            filters.append(or_(Conversation.id.ilike(term), ClienteModel.nome.ilike(term), Conversation.id.in_(subject_ids)))
            query = query.outerjoin(ClienteModel, ClienteModel.id == Conversation.cliente_id)
        if filters:
            query = query.where(*filters)
        with self.sessions() as db:
            total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
            rows = db.scalars(query.order_by(Conversation.updated_at.desc(), Conversation.id.desc())
                              .offset((page - 1) * page_size).limit(page_size)).unique().all()
            ids = [row.id for row in rows]
            latest_by_conversation = {}
            if ids:
                ranked = select(
                    Message.id,
                    func.row_number().over(
                        partition_by=Message.conversation_id,
                        order_by=(Message.created_at.desc(), Message.id.desc()),
                    ).label("position"),
                ).where(Message.conversation_id.in_(ids), Message.kind != "suggestion").subquery()
                recent = db.scalars(select(Message).join(ranked, ranked.c.id == Message.id)
                                    .where(ranked.c.position == 1)).all()
                for message in recent:
                    latest_by_conversation.setdefault(message.conversation_id, message)
            threads = {row.conversation_id: row for row in db.scalars(select(EmailThread).where(
                EmailThread.conversation_id.in_(ids),
            )).all()} if ids else {}
            items = []
            for conversation in rows:
                last = latest_by_conversation.get(conversation.id)
                thread = threads.get(conversation.id)
                items.append({
                    "id": conversation.id,
                    "channel": conversation.channel,
                    "status": conversation.status,
                    "mode": conversation.mode,
                    "assigned_user_id": conversation.assigned_user_id,
                    "assigned_username": conversation.assigned_user.username if conversation.assigned_user else None,
                    "cliente_id": conversation.cliente_id,
                    "cliente_nome": conversation.cliente.nome if conversation.cliente else None,
                    "email_subject": thread.subject if thread else None,
                    "handoff_reason": conversation.handoff_reason,
                    "last_message_preview": last.content[:180] if last else None,
                    "last_message_at": last.created_at if last else None,
                    "created_at": conversation.created_at,
                    "updated_at": conversation.updated_at,
                })
            return {"items": items, "total": total, "page": page, "page_size": page_size,
                    "pages": ceil(total / page_size) if total else 0}

    def assign(self, conversation_id, actor):
        with self.sessions() as db, db.begin():
            conversation = db.scalar(select(Conversation).where(Conversation.id == str(conversation_id)).with_for_update())
            if conversation is None:
                raise InboxError("conversation_not_found")
            if conversation.status == ConversationStatus.CLOSED.value:
                raise InboxError("conversation_closed")
            if conversation.assigned_user_id not in (None, actor.id):
                raise InboxError("conversation_already_assigned")
            if conversation.assigned_user_id != actor.id:
                conversation.assigned_user_id = actor.id
                conversation.status = ConversationStatus.OPEN.value
                conversation.mode = ConversationMode.HUMAN.value
                conversation.version += 1
                conversation.claim_token = None
                conversation.lease_until = None
                conversation.updated_at = self.clock()
                audit_record(db, actor=actor, action="ai_conversation_assigned", entity_type="ai_conversation",
                             entity_id=conversation.id, metadata={"new_assigned_user_id": actor.id, "new_mode": "human"})
                db.flush()
        return self.detail(conversation_id)

    def set_mode(self, conversation_id, mode: ConversationMode, actor):
        mode = ConversationMode(mode)
        with self.sessions() as db, db.begin():
            conversation = db.scalar(select(Conversation).where(Conversation.id == str(conversation_id)).with_for_update())
            if conversation is None:
                raise InboxError("conversation_not_found")
            if conversation.status == ConversationStatus.CLOSED.value:
                raise InboxError("conversation_closed")
            if not self._operator_can_act(conversation, actor):
                raise InboxError("conversation_not_assigned")
            if mode == ConversationMode.AUTONOMOUS and conversation.mode != mode.value:
                raise InboxError("autonomous_mode_admin_locked")
            old_mode = conversation.mode
            changed_status = conversation.status == ConversationStatus.WAITING_HUMAN.value
            if conversation.status == ConversationStatus.WAITING_HUMAN.value:
                conversation.status = ConversationStatus.OPEN.value
            conversation.mode = mode.value
            if old_mode != mode.value or changed_status:
                conversation.version += 1
                conversation.claim_token = None
                conversation.lease_until = None
                conversation.updated_at = self.clock()
                audit_record(db, actor=actor, action="ai_conversation_mode_changed", entity_type="ai_conversation",
                             entity_id=conversation.id, metadata={"old_mode": old_mode, "new_mode": mode.value})
        return self.detail(conversation_id)

    def suggest(self, conversation_id, actor, message_id=None):
        conversation_id = str(conversation_id)
        target_id = str(message_id) if message_id else None
        with self.sessions() as db:
            conversation = db.get(Conversation, conversation_id)
            if conversation is None:
                raise InboxError("conversation_not_found")
            if not self._operator_can_act(conversation, actor):
                raise InboxError("conversation_not_assigned")
        try:
            suggestion = self.core.suggest(conversation_id, target_id, actor="operator", source="internal")
        except ConversationError as error:
            raise InboxError(str(error)) from None
        return suggestion

    def _find_suggestion(self, db, conversation_id, suggestion_id):
        suggestion = db.get(Message, str(suggestion_id))
        if (suggestion is None or suggestion.conversation_id != str(conversation_id)
                or suggestion.kind != "suggestion" or suggestion.direction != "outbound"):
            raise InboxError("suggestion_not_found")
        return suggestion

    def send_message(self, conversation_id, payload, actor):
        conversation_id = str(conversation_id)
        suggestion_id = str(payload.suggestion_id) if payload.suggestion_id else None
        message_id = None
        created = False
        channel = None
        with self.sessions() as db, db.begin():
            conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id).with_for_update())
            if conversation is None:
                raise InboxError("conversation_not_found")
            if conversation.status == ConversationStatus.CLOSED.value:
                raise InboxError("conversation_closed")
            channel = conversation.channel
            if not self._operator_can_act(conversation, actor):
                raise InboxError("conversation_not_assigned")
            existing = db.scalar(select(Message).where(
                Message.conversation_id == conversation_id,
                Message.direction == "outbound",
                Message.kind == "message",
                Message.request_id == payload.idempotency_key,
            ))
            if existing is not None:
                if existing.content != payload.text:
                    raise InboxError("idempotency_conflict")
                message_id = existing.id
            else:
                suggestion = self._find_suggestion(db, conversation_id, suggestion_id) if suggestion_id else None
                if suggestion is not None:
                    latest_inbound = db.scalar(select(Message).where(
                        Message.conversation_id == conversation_id, Message.direction == "inbound",
                    ).order_by(Message.created_at.desc(), Message.id.desc()))
                    if latest_inbound is None or suggestion.reply_to_id != latest_inbound.id:
                        raise InboxError("stale_suggestion")
                conversation.status = ConversationStatus.OPEN.value
                conversation.mode = (
                    conversation.mode if conversation.mode == ConversationMode.COPILOT.value
                    else ConversationMode.HUMAN.value
                )
                conversation.version += 1
                conversation.claim_token = None
                conversation.lease_until = None
                conversation.updated_at = self.clock()
                message = Message(
                    id=str(uuid4()), conversation_id=conversation_id, direction="outbound", role="assistant",
                    channel=conversation.channel, kind="message", content=payload.text,
                    processing_status="completed", created_at=self.clock(), request_id=payload.idempotency_key,
                )
                db.add(message)
                audit_record(db, actor=actor, action="ai_conversation_message_created", entity_type="ai_conversation",
                             entity_id=conversation_id, metadata={"channel": conversation.channel,
                                                                   "new_mode": conversation.mode})
                db.flush()
                message_id = message.id
                if suggestion is not None:
                    from services.ai_usage_service import record_copilot
                    record_copilot(db, conversation, message, "copilot_used")
                created = True
        if channel == "email" and self.email_delivery is None:
            raise InboxError("delivery_unavailable")
        if channel == "email":
            try:
                self.email_delivery.send_human_message(conversation_id, message_id)
            except AIEmailError:
                raise InboxError("delivery_unavailable") from None
        if created and suggestion_id:
            with self.sessions() as db, db.begin():
                suggestion = db.get(Message, suggestion_id)
                if suggestion and suggestion.kind == "suggestion":
                    db.delete(suggestion)
        with self.sessions() as db:
            message = db.get(Message, message_id)
            return {"message": self._message_payload(message), "delivery": "already_sent" if not created else "sent"}

    def ignore_suggestion(self, conversation_id, suggestion_id, actor):
        with self.sessions() as db, db.begin():
            conversation = db.scalar(select(Conversation).where(Conversation.id == str(conversation_id)).with_for_update())
            if conversation is None:
                raise InboxError("conversation_not_found")
            if not self._operator_can_act(conversation, actor):
                raise InboxError("conversation_not_assigned")
            suggestion = self._find_suggestion(db, conversation.id, suggestion_id)
            db.delete(suggestion)
        return self.detail(conversation_id)

    def retry_message(self, conversation_id, message_id, actor):
        conversation_id = str(conversation_id)
        with self.sessions() as db:
            conversation = db.get(Conversation, conversation_id)
            if conversation is None:
                raise InboxError("conversation_not_found")
            if not self._operator_can_act(conversation, actor):
                raise InboxError("conversation_not_assigned")
            message = db.get(Message, str(message_id))
            if (message is None or message.conversation_id != conversation_id or message.channel != "email"
                    or message.direction != "outbound" or message.kind != "message"):
                raise InboxError("message_not_found")
            if message.external_message_id:
                return {"message": self._message_payload(message), "delivery": "already_sent"}
        if self.email_delivery is None:
            raise InboxError("delivery_unavailable")
        try:
            self.email_delivery.send_human_message(conversation_id, str(message_id))
        except AIEmailError:
            raise InboxError("delivery_unavailable") from None
        with self.sessions() as db:
            return {"message": self._message_payload(db.get(Message, str(message_id))), "delivery": "sent"}

    def close(self, conversation_id, actor):
        with self.sessions() as db, db.begin():
            conversation = db.scalar(select(Conversation).where(Conversation.id == str(conversation_id)).with_for_update())
            if conversation is None:
                raise InboxError("conversation_not_found")
            if not self._operator_can_act(conversation, actor):
                raise InboxError("conversation_not_assigned")
            if conversation.status != ConversationStatus.CLOSED.value:
                conversation.status = ConversationStatus.CLOSED.value
                conversation.closed_at = self.clock()
                conversation.updated_at = self.clock()
                conversation.version += 1
                conversation.claim_token = None
                conversation.lease_until = None
                audit_record(db, actor=actor, action="ai_conversation_closed", entity_type="ai_conversation",
                             entity_id=conversation.id, metadata={"new_status": "closed"})
        return self.detail(conversation_id)
