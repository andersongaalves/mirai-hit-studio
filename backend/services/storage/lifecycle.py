"""Safe lifecycle planning. This module never deletes provider objects."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class LifecycleAction(StrEnum):
    PRESERVE = "preserve"
    REVIEW = "review"
    ELIGIBLE = "eligible"


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    superseded_days: int | None = None

    def __post_init__(self) -> None:
        if self.superseded_days is not None and self.superseded_days < 1:
            raise ValueError("superseded_days deve ser positivo")


@dataclass(frozen=True, slots=True)
class LifecycleDecision:
    record_id: int
    category: str
    action: LifecycleAction
    reason: str


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def plan_production_files(
    files: Iterable,
    *,
    now: datetime,
    policy: RetentionPolicy,
) -> list[LifecycleDecision]:
    rows = list(files)
    superseded_ids = {
        row.substitui_arquivo_id
        for row in rows
        if row.substitui_arquivo_id is not None
    }
    decisions = []
    for row in rows:
        category = f"production_{row.tipo}"
        if row.id not in superseded_ids:
            action = LifecycleAction.PRESERVE
            reason = "active_version"
        elif row.tipo in {"entrega", "comprovante"}:
            action = LifecycleAction.PRESERVE
            reason = "protected_final_or_financial_record"
        elif policy.superseded_days is None:
            action = LifecycleAction.REVIEW
            reason = "retention_deadline_not_approved"
        else:
            age_days = (_aware(now) - _aware(row.created_at)).days
            action = (
                LifecycleAction.ELIGIBLE
                if age_days >= policy.superseded_days
                else LifecycleAction.PRESERVE
            )
            reason = (
                "superseded_retention_elapsed"
                if action == LifecycleAction.ELIGIBLE
                else "superseded_retention_active"
            )
        decisions.append(LifecycleDecision(row.id, category, action, reason))
    return decisions


def summarize(decisions: Iterable[LifecycleDecision]) -> dict[str, int]:
    counts = Counter(
        f"{decision.category}:{decision.action.value}"
        for decision in decisions
    )
    return dict(sorted(counts.items()))
