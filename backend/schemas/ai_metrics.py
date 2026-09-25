"""Aggregate-only administrative metrics: no contact, content or conversation IDs."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MetricModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OutcomeCount(MetricModel):
    name: str
    result: str
    error_code: str | None = None
    count: int
    latency_ms: float | None = None


class CostSubtotal(MetricModel):
    currency: str
    amount: Decimal
    measured_calls: int


class ChannelMetrics(MetricModel):
    channel: Literal["site", "email"]
    conversations_started: int = 0
    cohort_closed: int = 0
    cohort_handoffs: int = 0
    handoff_rate: float | None = None
    handoff_reasons: dict[str, int] = Field(default_factory=dict)
    autonomous_replies: int = 0
    human_replies: int = 0
    copilot_generated: int = 0
    copilot_used: int = 0
    briefings_started: int = 0
    briefings_submitted: int = 0
    budgets_created: int = 0
    briefing_conversion: float | None = None
    provider_calls: int = 0
    usage_known_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_unknown_calls: int = 0
    costs: list[CostSubtotal] = Field(default_factory=list)
    operations: list[OutcomeCount] = Field(default_factory=list)


class AIMetrics(MetricModel):
    period_start: datetime
    period_end: datetime
    technical_coverage_start: datetime | None = None
    channels: list[ChannelMetrics]
