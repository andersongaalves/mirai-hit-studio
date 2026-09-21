"""A disabled default keeps imports and local runs independent of credentials."""

from typing import Literal, Protocol

from schemas.ai import ProviderInput, ProviderResponse


class ProviderError(Exception):
    def __init__(self, code: Literal["provider_unavailable", "provider_timeout", "provider_invalid_response"]):
        self.code = code if code in {
            "provider_unavailable", "provider_timeout", "provider_invalid_response",
        } else "provider_unavailable"
        super().__init__(self.code)


class AIProvider(Protocol):
    def generate(self, incoming: ProviderInput) -> ProviderResponse: ...


class DisabledProvider:
    def generate(self, incoming: ProviderInput) -> ProviderResponse:
        raise ProviderError("provider_unavailable")
