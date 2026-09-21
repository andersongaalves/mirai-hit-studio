"""Strict public/private contracts exposed to the AI tool boundary."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ListServicesInput(ToolContract):
    query: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=8, ge=1, le=10)


class ServiceDetailsInput(ToolContract):
    service_id: int = Field(gt=0)


class PublicService(ToolContract):
    service_id: int
    name: str = Field(max_length=100)
    subtitle: str = Field(max_length=1000)
    category: str | None = Field(default=None, max_length=100)
    vertical: Literal["artists", "creators", "media_games"] | None = None
    segments: tuple[str, ...] = Field(default=(), max_length=20)
    pricing_mode: Literal["fixed", "starting_at", "custom"] | None = None
    commercial_level: Literal["entry", "launch", "premium", "custom"] | None = None
    active: bool | None = None
    published_base_price: float | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=2000)
    benefits: tuple[str, ...] = Field(default=(), max_length=8)


class ServiceListOutput(ToolContract):
    services: tuple[PublicService, ...] = Field(max_length=10)
    taxonomy_available: bool


class ServiceDetailsOutput(ToolContract):
    service: PublicService
    taxonomy_available: bool
    pricing_note: str


class PortfolioInput(ToolContract):
    vertical: Literal["artists", "creators", "media_games"] | None = None
    limit: int = Field(default=6, ge=1, le=10)


class PublicPortfolioItem(ToolContract):
    project_id: int
    title: str = Field(max_length=150)
    credited_artist: str = Field(max_length=150)
    category: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    vertical: Literal["artists", "creators", "media_games"]
    segments: tuple[str, ...] = Field(max_length=20)
    case_type: Literal["client_case", "demo", "concept_project", "study"]
    audio_url: str = Field(max_length=500)
    cover_url: str = Field(max_length=500)


class PortfolioOutput(ToolContract):
    projects: tuple[PublicPortfolioItem, ...] = Field(max_length=10)


class FAQInput(ToolContract):
    topic: Literal["contracting", "deadlines", "revisions", "rights", "payments"] | None = None


class FAQItem(ToolContract):
    topic: str = Field(max_length=30)
    answer: str = Field(max_length=1000)
    requires_confirmation: bool = False


class FAQOutput(ToolContract):
    items: tuple[FAQItem, ...] = Field(max_length=5)


class BudgetStatusInput(ToolContract):
    budget_id: int = Field(gt=0)


class BudgetStatusOutput(ToolContract):
    reference: str
    status: str
    service: str
    requested_at: datetime | None


class ProposalReferenceInput(ToolContract):
    proposal_number: str = Field(min_length=1, max_length=30)


class ProposalStatusOutput(ToolContract):
    proposal_number: str
    status: str
    sent_at: datetime | None
    approved_at: datetime | None
    checkout_available: bool


class ProductionStatusOutput(ToolContract):
    proposal_number: str
    status: str
    deadline: datetime | None
    current_stage: str | None
    completed_steps: int = Field(ge=0)
    total_steps: int = Field(ge=0)


class PaymentStatusOutput(ToolContract):
    proposal_number: str
    status: str
    currency: Literal["BRL"]
    total: Decimal = Field(ge=0)
    paid: Decimal = Field(ge=0)
    balance: Decimal = Field(ge=0)
    checkout_available: bool
