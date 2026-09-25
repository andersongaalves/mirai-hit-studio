"""Content-free provider accounting contracts."""
from decimal import Decimal
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")
    provider: str = Field(pattern=r"^[a-z0-9_-]{1,30}$")
    model: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._:/-]{1,100}$")
    input_tokens: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    total_tokens: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    cached_input_tokens: int | None = Field(default=None, ge=0, le=2147483647, strict=True)

    @model_validator(mode="after")
    def consistent(self):
        if self.total_tokens is not None and self.input_tokens is not None and self.output_tokens is not None:
            if self.total_tokens != self.input_tokens + self.output_tokens:
                raise ValueError("invalid_total_usage")
        if self.input_tokens is not None and self.cached_input_tokens is not None:
            if self.cached_input_tokens > self.input_tokens:
                raise ValueError("invalid_cached_usage")
        return self


class UsageRate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, revalidate_instances="always")
    version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,50}$")
    provider: str = Field(pattern=r"^[a-z0-9_-]{1,30}$")
    model: str = Field(pattern=r"^[A-Za-z0-9._:/-]{1,100}$")
    effective_from: date
    currency: Literal["USD", "BRL", "EUR"]
    input_per_million: Decimal = Field(ge=0)
    output_per_million: Decimal = Field(ge=0)
    cached_input_per_million: Decimal | None = Field(default=None, ge=0)
