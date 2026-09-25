"""Optional accounting; missing usage/rates stay unknown and failures stay safe."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import logging
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.exc import SQLAlchemyError

from models.ai_usage import AIUsageEventModel
from schemas.ai_usage import ProviderUsage, UsageRate

logger = logging.getLogger(__name__)
RATE_FILE = Path(__file__).resolve().parents[1] / "ai" / "rates.json"


def estimate(usage, rates, now):
    if usage is None or usage.input_tokens is None or usage.output_tokens is None:
        return {}
    candidates = [rate for rate in rates if rate.provider == usage.provider and rate.model == usage.model
                  and rate.effective_from <= now.date()]
    if not candidates:
        return {}
    rate = max(candidates, key=lambda item: item.effective_from)
    cached = usage.cached_input_tokens
    if cached is None or (cached and rate.cached_input_per_million is None):
        return {}
    amount = ((usage.input_tokens - cached) * rate.input_per_million
              + cached * (rate.cached_input_per_million or Decimal(0))
              + usage.output_tokens * rate.output_per_million) / Decimal(1000000)
    return {"estimated_cost": amount, "currency": rate.currency,
            "rate_snapshot": rate.model_dump(mode="json")}


def reference(value):
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except ValueError:
        return "sha256:" + hashlib.sha256(str(value).encode()).hexdigest()


class UsageRecorder:
    def __init__(self, sessions, context, *, rates=None):
        self.sessions, self.context = sessions, context
        try:
            source = rates if rates is not None else json.loads(RATE_FILE.read_text())
            rates = TypeAdapter(list[UsageRate]).validate_python(source)
            keys = {(rate.provider, rate.model, rate.effective_from) for rate in rates}
            if len(keys) != len(rates):
                raise ValueError("ambiguous_rates")
        except (OSError, ValueError, TypeError):
            logger.warning("ai_rates_unavailable")
            rates = []
        self.rates = rates

    def emit(self, *, kind, result, latency_ms=None, name=None, usage=None, error_code=None, cycle=None):
        if self.context is None:
            return
        now = datetime.now(timezone.utc)
        try:
            usage = ProviderUsage.model_validate(usage) if usage is not None else None
        except (ValueError, TypeError):
            usage = None
        data = usage.model_dump() if usage else {}
        try:
            with self.sessions() as db, db.begin():
                from models.ai import AIConversationModel
                conversation = db.get(AIConversationModel, str(self.context.conversation_id))
                if conversation is None:
                    return
                db.add(AIUsageEventModel(
                    conversation_id=conversation.id, message_id=str(self.context.message_id) if self.context.message_id else None,
                    channel=conversation.channel, kind=kind, result=result, latency_ms=latency_ms,
                    name=name, error_code=error_code, cycle=cycle, created_at=now,
                    request_id=reference(self.context.request_id), **data, **estimate(usage, self.rates, now),
                ))
            logger.info("ai_measurement kind=%s result=%s error_code=%s conversation_id=%s request_id=%s",
                        kind, result, error_code, self.context.conversation_id, reference(self.context.request_id))
        except SQLAlchemyError:
            logger.warning("ai_measurement_storage_failed kind=%s", kind)


def record_copilot(db, conversation, message, kind):
    db.add(AIUsageEventModel(conversation_id=conversation.id, message_id=message.id,
                            channel=conversation.channel, kind=kind, result="success"))
