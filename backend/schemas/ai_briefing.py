"""Allowlisted fields that may be collected from an explicit customer message."""

from datetime import date, datetime
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BriefingContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class BriefingDetails(BriefingContract):
    project_type: str | None = Field(default=None, min_length=2, max_length=100)
    style: str | None = Field(default=None, min_length=2, max_length=100)
    track_count: int | None = Field(default=None, ge=1, le=10000)
    requested_deadline: date | None = None
    goal: str | None = Field(default=None, min_length=2, max_length=500)
    references: list[str] = Field(default_factory=list, max_length=5)
    notes: str | None = Field(default=None, min_length=2, max_length=2000)

    @field_validator("references")
    @classmethod
    def valid_references(cls, values):
        for value in values:
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 300:
                raise ValueError("invalid_reference")
            if "://" in value and not value.lower().startswith(("http://", "https://")):
                raise ValueError("invalid_reference_url")
            if value.lower().startswith(("javascript:", "data:", "file:", "vbscript:")):
                raise ValueError("invalid_reference_url")
        return [value.strip() for value in values]


class BriefingUpdateInput(BriefingContract):
    service_id: int | None = Field(default=None, gt=0)
    interest: str | None = Field(default=None, min_length=2, max_length=100)
    contact_name: str | None = Field(default=None, min_length=2, max_length=120)
    contact_email: EmailStr | None = Field(default=None, max_length=150)
    contact_phone: str | None = Field(default=None, min_length=7, max_length=30)
    details: BriefingDetails | None = None

    @field_validator("contact_phone")
    @classmethod
    def valid_phone(cls, value):
        if value is not None and (not re.fullmatch(r"[+\d\s().-]+", value)
                                  or not 7 <= len(re.sub(r"\D", "", value)) <= 15):
            raise ValueError("invalid_phone")
        return value


class BriefingSubmitInput(BriefingContract):
    pass


class BriefingToolOutput(BriefingContract):
    status: Literal["draft", "submitted"]
    interest: str | None = None
    service_id: int | None = None
    details: BriefingDetails
    missing_fields: tuple[str, ...]
    has_contact_name: bool
    has_contact_email: bool
    has_contact_phone: bool
    submitted: bool


class BriefingAdminOutput(BriefingContract):
    status: Literal["draft", "submitted"]
    interest: str | None
    service_id: int | None
    service_name: str | None
    contact_name: str | None
    contact_email: EmailStr | None
    contact_phone: str | None
    details: BriefingDetails
    missing_fields: tuple[str, ...]
    orcamento_id: int | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
