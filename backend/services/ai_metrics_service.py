"""Bounded aggregate queries; operational records remain authoritative."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, or_, select

from models.ai import AIConversationModel as C, AIMessageModel as M
from models.ai_briefing import AIBriefingModel as B
from models.ai_usage import AIUsageEventModel as U
from schemas.ai_metrics import AIMetrics, ChannelMetrics, CostSubtotal, OutcomeCount


def total(condition):
    return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)


def metrics(sessions, *, days=7, now=None):
    if days not in (7, 30):
        raise ValueError("invalid_metrics_period")
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    channels = []
    with sessions() as db:
        coverage = db.scalar(select(func.min(U.created_at)))
        if coverage and coverage.tzinfo is None:
            coverage = coverage.replace(tzinfo=timezone.utc)
        for channel in ("site", "email"):
            item = ChannelMetrics(channel=channel)
            cohort = (C.channel == channel, C.created_at >= start, C.created_at < end)
            started, closed, handed = db.execute(select(
                func.count(C.id), total(C.status == "closed"), total(C.handoff_reason.is_not(None)),
            ).where(*cohort)).one()
            item.conversations_started, item.cohort_closed, item.cohort_handoffs = started, closed, handed
            item.handoff_rate = handed / started if started else None
            item.handoff_reasons = dict(db.execute(select(C.handoff_reason, func.count(C.id))
                .where(*cohort, C.handoff_reason.is_not(None)).group_by(C.handoff_reason)).all())
            delivered = or_(M.channel == "site", M.external_message_id.is_not(None))
            item.autonomous_replies, item.human_replies = db.execute(select(
                total(M.kind == "reply"), total(M.kind == "message"),
            ).where(M.channel == channel, M.direction == "outbound", delivered,
                    M.created_at >= start, M.created_at < end)).one()
            item.briefings_started, item.briefings_submitted, item.budgets_created = db.execute(select(
                func.count(B.conversation_id), total(B.status == "submitted"), total(B.orcamento_id.is_not(None)),
            ).join(C, C.id == B.conversation_id).where(
                C.channel == channel, B.created_at >= start, B.created_at < end)).one()
            item.briefing_conversion = (item.budgets_created / item.briefings_started
                                       if item.briefings_started else None)
            window = (U.channel == channel, U.created_at >= start, U.created_at < end)
            rows = db.execute(select(U.kind, U.name, U.result, U.error_code, func.count(U.id),
                                     func.avg(U.latency_ms)).where(*window)
                              .group_by(U.kind, U.name, U.result, U.error_code)).all()
            for kind, name, result, code, count, latency in rows:
                if kind == "copilot_generated":
                    item.copilot_generated += count
                elif kind in ("provider", "tool", "turn"):
                    item.operations.append(OutcomeCount(name=name or kind, result=result, error_code=code,
                                                        count=count, latency_ms=latency))
            item.copilot_used = db.scalar(select(func.count(U.id)).join(M, M.id == U.message_id)
                .where(*window, U.kind == "copilot_used", delivered))
            known = U.input_tokens.is_not(None) & U.output_tokens.is_not(None) & U.total_tokens.is_not(None)
            (item.provider_calls, item.usage_known_calls, item.input_tokens, item.output_tokens,
             item.total_tokens, item.cost_unknown_calls) = db.execute(select(
                func.count(U.id), total(known), func.sum(U.input_tokens), func.sum(U.output_tokens),
                func.sum(U.total_tokens), total(U.estimated_cost.is_(None)),
            ).where(*window, U.kind == "provider")).one()
            item.costs = [CostSubtotal(currency=currency, amount=amount, measured_calls=count)
                          for currency, amount, count in db.execute(select(
                              U.currency, func.sum(U.estimated_cost), func.count(U.id),
                          ).where(*window, U.kind == "provider", U.estimated_cost.is_not(None))
                              .group_by(U.currency)).all()]
            channels.append(item)
    return AIMetrics(period_start=start, period_end=end, technical_coverage_start=coverage, channels=channels)
